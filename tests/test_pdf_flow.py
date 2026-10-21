"""Integrated image PDF editor, progress lifecycle and single-instance transport."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from PIL import Image
from pypdf import PdfReader
import pytest

from tangerine import actions, catalog, paths, requests, theme
from tangerine.editors.pdf import ImagesPdfDialog


@pytest.fixture
def images(tmp_path):
    result = [tmp_path / f"Page {n} ñ.png" for n in (10, 2, 1)]
    for i, path in enumerate(result):
        Image.new("RGB", (100 + i * 20, 90), (255, 100, 20)).save(path)
    return result


def pump(qapp, condition, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not condition():
        qapp.processEvents()
        time.sleep(0.01)
    assert condition()


def test_editor_manual_starts_from_visible_order(qapp, images):
    dialog = ImagesPdfDialog(images, order="name")
    assert dialog.selected_paths() == list(reversed(images))
    dialog.order.setCurrentIndex(dialog.order.findData("manual"))
    dialog.files.setCurrentRow(0)
    dialog.move_item(1)
    assert dialog.selected_paths() == [images[1], images[2], images[0]]
    dialog.order.setCurrentIndex(dialog.order.findData("received"))
    assert dialog.selected_paths() == images
    dialog.close()


def test_editor_creates_pdf_with_shared_progress_and_autoclose(qapp, images):
    dialog = ImagesPdfDialog(images, order="name")
    dialog._accept_clicked()
    window = dialog.job_window
    assert window is not None
    # Image decoding/PDF writes can take longer on hosted Windows runners than
    # the Linux and macOS runners; leave enough time for the real worker and
    # progress-card auto-close lifecycle to finish.
    pump(qapp, lambda: window._job_done, seconds=20)
    assert not window.failed, window.error_view.toPlainText()
    assert not window.isVisible()
    pdf = PdfReader(window.outputs[0])
    widths = [float(page.mediabox.width) for page in pdf.pages]
    assert widths == sorted(widths, reverse=True)


def test_editor_refuses_existing_output(qapp, images, tmp_path):
    existing = tmp_path / "keep.pdf"
    existing.write_bytes(b"original")
    dialog = ImagesPdfDialog(images)
    dialog.output.setText(str(existing))
    dialog._accept_clicked()
    assert dialog.job_window is None and dialog.error.text()
    assert existing.read_bytes() == b"original"
    dialog.close()


def test_settings_pdf_action_uses_controller_callback(qapp):
    from tangerine.settings_window import SettingsWindow
    calls = []
    window = SettingsWindow(pdf_callback=lambda: calls.append("pdf"))
    assert window.objectName() == "SettingsRoot"
    window._open_images_pdf()
    assert calls == ["pdf"]
    window.close()


def test_wheel_tool_and_conversion_share_editor(qapp, images):
    for dialog in (actions.run_tool(images, "img.pdf"), actions.run_conversions(images, "pdf")):
        assert isinstance(dialog, ImagesPdfDialog)
        dialog.close()


@pytest.mark.parametrize("extension", [".jpe", ".jfif", ".dib", ".ico", ".gif"])
def test_supported_pdf_images_are_reachable_in_tools_wheel(extension):
    image = Path("sample" + extension)
    assert "img.pdf" in {tool.id for tool in catalog.tools_for([image])}
    batch = [image, Path("photo.png")]
    assert catalog.tool_paths("img.pdf", batch) == batch
    assert "img.pdf" in {tool.id for tool in catalog.tools_for([image, image])}


def test_cli_manifest_unicode_cleanup_and_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    queue = tmp_path / "request-queue"
    queue.mkdir()
    manifest = queue / "selection-test.json"
    files = [str(tmp_path / "Page ñ 🧪.png")]
    manifest.write_text(json.dumps(files), encoding="utf-8-sig")
    request = requests.parse_request(["--images-to-pdf", "--selection-manifest", str(manifest), "--pdf-order", "received", "--pdf-quick"])
    assert request["paths"] == files and request["quick"] and not manifest.exists()
    foreign = tmp_path / "selection-foreign.json"
    foreign.write_text("[]")
    with pytest.raises(ValueError):
        requests.parse_request(["--images-to-pdf", "--selection-manifest", str(foreign)])
    assert foreign.exists()


class _TrackedRequestServer(requests.RequestServer):
    """Expose accepted-socket destruction for the IPC test's teardown."""

    def __init__(self):
        self.accepted_sockets = []
        self.destroyed_sockets = []
        super().__init__()

    def _read(self, socket):
        if not any(socket is accepted for accepted in self.accepted_sockets):
            index = len(self.accepted_sockets)
            self.accepted_sockets.append(socket)
            destroyed_sockets = self.destroyed_sockets
            socket.destroyed.connect(
                lambda *_args, i=index, seen=destroyed_sockets: seen.append(i)
            )
        super()._read(socket)


def test_local_pipe_delivers_once_to_existing_instance(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    import shiboken6

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    server = _TrackedRequestServer()
    assert server.listen()
    received = []
    server.received.connect(received.append)
    request = {"id": uuid.uuid4().hex, "action": "images-to-pdf", "paths": ["C:/Page ñ.png"], "order": "name", "quick": True}
    code = "from PySide6.QtCore import QCoreApplication; from tangerine import requests,paths; from pathlib import Path; import json,sys; app=QCoreApplication([]); paths.data_dir=lambda:Path(sys.argv[1]); r=json.loads(sys.argv[2]); sys.exit(0 if requests.forward_request(r) and requests.forward_request(r) else 1)"
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), json.dumps(request)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        pump(qapp, lambda: child.poll() is not None, 10)
        out, error = child.communicate(timeout=1)
        assert child.returncode == 0, (out, error)
        pump(qapp, lambda: len(received) == 1)
        assert received == [request]
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        server.server.close()
        accepted_sockets = list(server.accepted_sockets)
        destroyed_sockets = server.destroyed_sockets
        for socket in accepted_sockets:
            if shiboken6.isValid(socket):
                socket.abort()
                socket.deleteLater()
        server.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert set(destroyed_sockets) == set(range(len(accepted_sockets)))
        assert not shiboken6.isValid(server)


@pytest.mark.parametrize("dark", [False, True])
def test_pdf_editor_renders_with_app_theme(qapp, images, tmp_path, dark, monkeypatch):
    monkeypatch.setattr(theme, "is_dark", lambda: dark)
    theme.apply_app_theme()
    dialog = ImagesPdfDialog(images)
    dialog.show()
    qapp.processEvents()
    assert dialog.files.count() == 3 and dialog._ok_button.isVisible()
    assert dialog.grab().save(str(tmp_path / ("pdf-dark.png" if dark else "pdf-light.png")))
    dialog.close()
