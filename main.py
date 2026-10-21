import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _prepare_frozen_qt_webengine() -> Path | None:
    """Point frozen Windows builds at the Qt WebEngine files in their bundle."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return None

    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    pyside_dir = bundle_dir / "PySide6"
    helper = pyside_dir / "QtWebEngineProcess.exe"
    if not helper.is_file():
        return None

    os.environ["QTWEBENGINEPROCESS_PATH"] = str(helper)
    resources = pyside_dir / "resources"
    if resources.is_dir():
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(resources)
    locales = pyside_dir / "translations" / "qtwebengine_locales"
    if locales.is_dir():
        os.environ["QTWEBENGINE_LOCALES_PATH"] = str(locales)

    bundled_paths = [str(pyside_dir), str(bundle_dir)]
    existing = os.environ.get("PATH", "").split(os.pathsep)
    bundled_keys = {path.rstrip("\\/").casefold() for path in bundled_paths}
    os.environ["PATH"] = os.pathsep.join(
        bundled_paths
        + [entry for entry in existing if entry.rstrip("\\/").casefold() not in bundled_keys]
    )
    return helper


def _smoke_webengine() -> int:
    """Load a local page in the bundled WebEngine and return a process status."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    helper = _prepare_frozen_qt_webengine()
    _write_webengine_smoke_log(f"Started: helper={helper}")
    if helper is None:
        return 2
    try:
        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineCore import QWebEnginePage

        app = QApplication([sys.argv[0]])
        page = QWebEnginePage()
        loop = QEventLoop()
        result: list[bool] = []
        terminated: list[str] = []
        page.loadFinished.connect(lambda ok: (result.append(bool(ok)), loop.quit()))
        page.renderProcessTerminated.connect(
            lambda status, code: terminated.append(f"{status}: {code}")
        )
        page.setHtml("<!doctype html><html><body>filepetal-webengine-smoke</body></html>", QUrl("about:blank"))
        QTimer.singleShot(20_000, loop.quit)
        loop.exec()
        page.deleteLater()
        app.processEvents()
        if result and result[0]:
            _write_webengine_smoke_log(f"OK: helper={helper}; local page loaded")
            return 0
        _write_webengine_smoke_log(
            f"Load failed or timed out. helper={helper}; result={result}; "
            f"renderer_terminated={terminated}"
        )
        return 3
    except Exception:
        _write_webengine_smoke_log(traceback.format_exc())
        return 4


def _write_webengine_smoke_log(message: str) -> None:
    """Keep diagnostics for the windowless packaged smoke command."""
    try:
        temp_dir = Path(os.environ.get("TEMP") or Path.home() / "AppData/Local/Temp")
        (temp_dir / "FilePetal-webengine-smoke.log").write_text(
            message, encoding="utf-8"
        )
        (temp_dir / "Tangerine-webengine-smoke.log").write_text(
            message, encoding="utf-8"
        )
    except Exception:
        pass


if "--version" in sys.argv:
    try:
        from tangerine.paths import APP_NAME, APP_VERSION

        print(f"{APP_NAME} {APP_VERSION}")
    except Exception:
        print("FilePetal (version unknown)")
    raise SystemExit(0)

if "--smoke-webengine" in sys.argv:
    raise SystemExit(_smoke_webengine())

if "--smoke-image-pdf" in sys.argv:
    _prepare_frozen_qt_webengine()
    from tangerine.smoke import image_pdf_smoke
    raise SystemExit(image_pdf_smoke())

if "--smoke-editors" in sys.argv:
    from tangerine.editor_smoke import editors_smoke
    raise SystemExit(editors_smoke())

if "--register-shell" in sys.argv or "--unregister-shell" in sys.argv:
    try:
        from tangerine.shell_integration import register_shell, unregister_shell
        if "--register-shell" in sys.argv:
            register_shell()
        else:
            unregister_shell()
    except Exception:
        try:
            (Path(os.environ.get("TEMP", ".")) / "FilePetal-shell-registration.log").write_text(
                traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise SystemExit(1)
    raise SystemExit(0)

_prepare_frozen_qt_webengine()

try:
    from tangerine.main import main
except Exception as exc:
    message = f"FilePetal failed to start: {exc}\n\n{traceback.format_exc()}"
    try:
        crash = Path(os.environ.get("APPDATA", "")) / "FilePetal" / "crash.log"
        crash.parent.mkdir(parents=True, exist_ok=True)
        with crash.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except Exception:
        pass
    try:
        import ctypes

        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            ctypes.windll.user32.MessageBoxW(None, message, "FilePetal", 0x10)
    except Exception:
        pass
    raise SystemExit(1)

if __name__ == "__main__":
    sys.exit(main())
