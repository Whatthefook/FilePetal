"""Small frozen-runtime checks; no desktop automation and no registry writes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import traceback
import subprocess
import sys
import time


def _request_smoke(app, root, files):
    """Exercise the real CLI in a second process against the local pipe."""
    from pypdf import PdfReader
    from . import paths, requests
    from .main import Controller

    if sys.platform == "win32":
        data_root = root / "appdata"
        child_data_env = {"APPDATA": str(data_root)}
    elif sys.platform == "darwin":
        home = root / "home"
        data_root = home / "Library" / "Application Support"
        child_data_env = {"HOME": str(home)}
    else:
        data_root = root / "xdg-config"
        child_data_env = {"XDG_CONFIG_HOME": str(data_root)}

    queue = data_root / paths.APP_NAME / "request-queue"
    queue.mkdir(parents=True)
    original_data_dir = paths.data_dir
    paths.data_dir = lambda: queue.parent
    server = requests.RequestServer()
    windows = []
    received = []

    class Receiver:
        def _track(self, window):
            windows.append(window)

    receiver = Receiver()

    def handle(request):
        received.append(request)
        Controller.handle_request(receiver, request)

    server.received.connect(handle)
    try:
        assert server.listen(), server.server.errorString()
        prefix = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(paths.app_root() / "main.py")]
        for index, selection in enumerate(([files[0]], files)):
            args = ["--images-to-pdf", "--pdf-order", "name", "--pdf-quick"]
            manifest = None
            if index:
                manifest = queue / "selection-smoke.json"
                manifest.write_text(json.dumps([str(p) for p in selection], ensure_ascii=False), encoding="utf-8")
                args += ["--selection-manifest", str(manifest)]
            else:
                args += [str(selection[0])]
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            env.update(child_data_env)
            if not getattr(sys, "frozen", False):
                # APPDATA isolation also changes Python's user-site location.
                env["PYTHONPATH"] = os.pathsep.join(sys.path)
            child_log = root / f"child-{index}.log"
            log_handle = child_log.open("w", encoding="utf-8")
            child = subprocess.Popen(prefix + args, env=env, stdout=log_handle, stderr=log_handle,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            deadline = time.monotonic() + 15
            try:
                while time.monotonic() < deadline:
                    app.processEvents()
                    if (child.poll() is not None and len(windows) > index
                            and windows[index]._job_done and not windows[index].isVisible()):
                        break
                    time.sleep(0.01)
                if child.poll() != 0:
                    log_handle.flush()
                    detail = child_log.read_text(encoding="utf-8", errors="replace")[-4000:]
                    for filename in ("crash.log", "tangerine.log", "filepetal.log"):
                        diagnostic = queue.parent / filename
                        if diagnostic.exists():
                            detail += diagnostic.read_text(encoding="utf-8", errors="replace")[-4000:]
                    raise AssertionError(f"CLI child did not acknowledge request {index}: {child.poll()}; {detail}")
                assert len(windows) == index + 1 and len(received) == index + 1
                window = windows[index]
                assert window._job_done and not window.failed and not window.isVisible()
                assert len(PdfReader(window.outputs[0]).pages) == len(selection)
                assert manifest is None or not manifest.exists()
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                log_handle.close()
        return {"ipc_requests": len(received), "single_pages": 1, "multiple_pages": len(files), "manifest_cleanup": True}
    finally:
        server.server.close()
        paths.data_dir = original_data_dir


def image_pdf_smoke() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    result_path = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "Tangerine-image-pdf-smoke.json"
    result = {}
    try:
        from PIL import Image
        from pypdf import PdfReader
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
        from . import engines, paths, progress, theme
        from .editors.pdf import ImagesPdfDialog
        from .image_pdf import PdfOptions
        app = QApplication.instance() or QApplication([])
        theme.apply_app_theme()
        with tempfile.TemporaryDirectory(prefix="Tangerine-pdf-smoke-") as folder:
            root = Path(folder)
            files = [root / f"Page {n} ñ.png" for n in (10, 2, 1)]
            for i, file in enumerate(files):
                Image.new("RGBA", (160 + i * 20, 100), (255, 125, 25, 128)).save(file)
            editor = ImagesPdfDialog(files, order="name")
            assert [p.name for p in editor.selected_paths()] == [files[2].name, files[1].name, files[0].name]
            editor.order.setCurrentIndex(editor.order.findData("manual"))
            editor.files.setCurrentRow(0)
            editor.move_item(1)
            assert editor.selected_paths()[0] == files[1]
            editor.close()
            loop = QEventLoop()
            window = progress.run_job("PDF smoke", lambda ctx: [engines.images_to_pdf(files, ctx, set(), PdfOptions(order="name"))])
            window.finished_closed.connect(loop.quit)
            QTimer.singleShot(20000, loop.quit)
            loop.exec()
            assert not window.failed and window.outputs and not window.isVisible()
            output = Path(window.outputs[0])
            assert len(PdfReader(output).pages) == 3
            transport = _request_smoke(app, root, files)
            result = {"ok": True, "version": paths.APP_VERSION, "pages": 3, "editor_order": True,
                      "progress_autoclose": True, "assets": paths.icon_path().is_file(), **transport}
            assert result["assets"], "Packaged icon not found"
        status = 0
    except Exception:
        result = {"ok": False, "error": traceback.format_exc()}
        status = 1
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return status
