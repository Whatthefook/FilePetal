"""CLI requests and a per-user local pipe for the existing Tangerine instance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from . import paths

MAX_REQUEST_BYTES = 8 * 1024 * 1024


def server_name() -> str:
    key = os.path.normcase(str(paths.data_dir().resolve())).encode("utf-8")
    return f"{paths.APP_NAME}-" + hashlib.sha256(key).hexdigest()[:24]


def parse_request(arguments: list[str]) -> dict | None:
    parser = argparse.ArgumentParser(prog=paths.APP_NAME)
    parser.add_argument("--images-to-pdf", action="store_true")
    parser.add_argument("--pdf-order", choices=("name", "received", "manual"), default="name")
    parser.add_argument("--pdf-quick", action="store_true")
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(arguments)
    if not args.images_to_pdf:
        if args.files or args.selection_manifest or args.pdf_quick:
            parser.error("Use --images-to-pdf with image files.")
        return None
    files = args.files
    if args.selection_manifest is not None:
        manifest = args.selection_manifest.resolve()
        queue = (paths.data_dir() / "request-queue").resolve()
        if manifest.parent != queue or not manifest.name.startswith("selection-") or manifest.suffix != ".json":
            raise ValueError("Selection manifest must belong to FilePetal's request queue.")
        if manifest.stat().st_size > MAX_REQUEST_BYTES:
            raise ValueError("Selection manifest is too large.")
        loaded = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, list) or not all(isinstance(p, str) for p in loaded):
            raise ValueError("Invalid selection manifest.")
        files = loaded + files
        manifest.unlink()
    return validate_request({"id": uuid.uuid4().hex, "action": "images-to-pdf", "paths": files,
                             "order": args.pdf_order, "quick": args.pdf_quick})


def validate_request(request: object) -> dict:
    if not isinstance(request, dict) or request.get("action") != "images-to-pdf":
        raise ValueError("Unknown Tangerine action.")
    files = request.get("paths")
    if not isinstance(files, list) or len(files) > 10000 or not all(isinstance(p, str) and p and "\0" not in p for p in files):
        raise ValueError("Invalid image selection.")
    if request.get("order") not in ("name", "received", "manual") or not isinstance(request.get("quick"), bool):
        raise ValueError("Invalid PDF options.")
    identifier = request.get("id")
    if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
        raise ValueError("Invalid request ID.")
    return {"id": identifier, "action": "images-to-pdf", "paths": files,
            "order": request["order"], "quick": request["quick"]}


def forward_request(request: dict, timeout_ms: int = 1500) -> bool:
    payload = json.dumps(validate_request(request), ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Image selection is too large.")
    socket = QLocalSocket()
    socket.connectToServer(server_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    socket.write(payload)
    if socket.bytesToWrite() and not socket.waitForBytesWritten(timeout_ms):
        socket.abort()
        return False
    response = bytearray()
    while b"\n" not in response:
        if not socket.bytesAvailable() and not socket.waitForReadyRead(timeout_ms):
            socket.abort()
            return False
        response.extend(bytes(socket.readAll()))
        if len(response) > 1024:
            socket.abort()
            return False
    socket.disconnectFromServer()
    return bytes(response).split(b"\n", 1)[0] == b"OK"


class RequestServer(QObject):
    received = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        self._buffers = {}
        self._seen: dict[str, None] = {}

    def listen(self) -> bool:
        # The caller owns Tangerine's QLockFile before removing a stale endpoint.
        QLocalServer.removeServer(server_name())
        return self.server.listen(server_name())

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._discard(s))
            QTimer.singleShot(10000, socket, socket.disconnectFromServer)
            if socket.bytesAvailable():
                self._read(socket)

    def _discard(self, socket):
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def _read(self, socket):
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > MAX_REQUEST_BYTES:
            socket.abort()
            return
        if b"\n" not in buffer:
            return
        try:
            request = validate_request(json.loads(buffer.split(b"\n", 1)[0]))
        except (ValueError, UnicodeError):
            socket.write(b"ERROR\n")
        else:
            if request["id"] not in self._seen:
                self._seen[request["id"]] = None
                if len(self._seen) > 512:
                    self._seen.pop(next(iter(self._seen)))
                # Queue UI work so the pipe acknowledgement is never blocked by a dialog.
                QTimer.singleShot(0, self, lambda r=request: self.received.emit(r))
            socket.write(b"OK\n")
        self._buffers.pop(socket, None)
        socket.disconnectFromServer()
