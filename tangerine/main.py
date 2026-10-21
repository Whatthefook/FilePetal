from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QThread, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import actions, catalog, i18n, paths, render, settings, theme
if sys.platform == "win32":
    from .monitor import DragMonitor
from .wheel import FanItem, TangerineWheel

log = logging.getLogger("tangerine")


def _write_crash_log(message: str) -> None:
    try:
        with (paths.data_dir() / "crash.log").open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except Exception:
        pass


def _show_error(message: str) -> None:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return
    try:
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, message, "FilePetal", 0x10)
        else:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                QMessageBox.critical(None, paths.APP_NAME, message)
            else:
                print(message, file=sys.stderr)
    except Exception:
        pass


def _install_excepthooks() -> None:
    def handle_exception(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error("Unhandled exception: %s", exc, exc_info=(exc_type, exc, tb))
        _write_crash_log(text)

    def handle_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        text = "".join(
            traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback
            )
        )
        log.error(
            "Unhandled exception in thread %s: %s",
            args.thread.name if args.thread else "?",
            args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        _write_crash_log(text)

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception


def _warm_catalog() -> None:
    try:
        catalog.available_engines()
    except Exception:
        pass
    try:
        render.ensure_ready()
    except Exception:
        pass


class Controller(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._mode = "conversion"
        self._jobs = []
        self._labels = {}
        self._settings_window = None

        self.wheel = TangerineWheel()
        self.wheel.set_factory(self._factory)
        self.wheel.activated.connect(self._activated)

        self._portable = sys.platform != "win32"
        if self._portable:
            from .portable import PortableMonitor
            self.monitor = PortableMonitor(self)
            self.monitor.start()
        else:
            self.monitor = DragMonitor(self)
        self.monitor.wheelShown.connect(self._show_wheel)
        self.monitor.wheelMoved.connect(self._move_wheel)
        self.monitor.wheelHidden.connect(self._hide_wheel)
        self.monitor.wheelRefreshed.connect(self._refresh_wheel)
        self.monitor.keyboardTriggered.connect(self._keyboard_wheel)
        self.monitor.stickyTriggered.connect(self._sticky_wheel)
        self.monitor.stickyClicked.connect(self._sticky_click)
        self.monitor.wheelNavigated.connect(self._nav_wheel)
        self.monitor.wheelKeyActivated.connect(self._key_activate_wheel)
        self.wheel.closed.connect(self.monitor.sticky_release)

        self.tray = QSystemTrayIcon(QIcon(str(paths.icon_path())), self)
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray.setToolTip(i18n.tr("tray.tooltip"))
        self._menu = None
        self._active_menu = None
        self._build_tray_menu()
        self.tray.activated.connect(self._tray_activated)
        if self.tray_available:
            self.tray.show()

        i18n.add_listener(self._language_changed)

    # -- localization ----------------------------------------------------------
    def _build_tray_menu(self):
        menu = QMenu()
        if self._portable:
            companion_action = menu.addAction(i18n.tr("portable.open"))
            companion_action.triggered.connect(self._show_companion)
            menu.addSeparator()
        pdf_action = menu.addAction(i18n.tr("pdf.images.title"))
        pdf_action.triggered.connect(lambda: self.open_images_pdf())
        menu.addSeparator()
        self._active_menu = menu.addMenu(i18n.tr("tray.active"))
        self._active_menu.aboutToShow.connect(self._rebuild_active)
        menu.addSeparator()
        settings_action = menu.addAction(i18n.tr("tray.settings"))
        settings_action.triggered.connect(self.open_settings)
        update_action = menu.addAction(i18n.tr("tray.check_updates"))
        update_action.triggered.connect(self._check_updates)
        menu.addSeparator()
        quit_action = menu.addAction(i18n.tr("tray.quit"))
        quit_action.triggered.connect(self._quit)
        self._menu = menu
        self.tray.setContextMenu(menu)

    def _language_changed(self, code=None):
        try:
            if self.tray_available:
                self.tray.setToolTip(i18n.tr("tray.tooltip"))
            self._build_tray_menu()
            if self._portable:
                self.monitor.retranslate()
            files = self.wheel.file_paths()
            if files:
                self._refresh_wheel(self._mode)
            self.wheel.update()
        except Exception:
            log.exception("Could not refresh the UI after a language change")

    # -- wheel -----------------------------------------------------------------
    def _items_for(self, files, mode):
        file_list = list(files) if files else []
        sources = [Path(f) for f in file_list]
        if mode == "actions":
            items = []
            for action in catalog.actions_for(sources):
                label = i18n.tr(action.id)
                items.append(FanItem(action.id, label, kind="action"))
                self._labels[action.id] = label
            return items
        if mode == "tools":
            items = []
            for tool in catalog.tools_for(sources):
                label = i18n.tr("tool." + tool.id)
                items.append(FanItem(tool.id, label, kind="tool"))
                self._labels[tool.id] = label
            if not items and sources:
                label = i18n.tr("wheel.no_tools")
                return [FanItem("info.no_tools", label, kind="info")]
            return items
        items = []
        for conversion in catalog.conversions_for(sources):
            label = i18n.tr("conv." + conversion.target_ext)
            items.append(FanItem(conversion.target_ext, label, kind="conversion"))
            self._labels[conversion.target_ext] = label
        if not items and sources:
            label = i18n.tr("wheel.no_conversion")
            return [FanItem("info.no_conversion", label, kind="info")]
        return items

    def _factory(self, files):
        return self._items_for(files, self._mode)

    def _show_wheel(self, pos, files, mode):
        self._mode = mode
        self.wheel.set_keyboard_mode(False)
        self.wheel.set_mode(mode)
        if files:
            self.wheel.set_files(files)
            self.wheel.set_items(self._items_for(files, mode))
        elif self.wheel.isVisible():
            self.wheel.cancel_dismiss()
        else:
            self.wheel.set_items(self._items_for(files, mode))
        self.wheel.place_beside_cursor(pos)
        self.wheel.show()

    def _keyboard_wheel(self, pos, files, mode):
        """Shift+Enter on an Explorer selection (plan 1.5): keyboard wheel."""
        self._show_wheel(pos, files, mode)
        self.wheel.set_keyboard_mode(True)

    def _sticky_wheel(self, pos, files, mode):
        """Pinned wheel: shortcuts (Esc/arrows/Enter) and clicks stay live."""
        self._show_wheel(pos, files, mode)
        self.wheel.set_keyboard_mode(True)

    def _nav_wheel(self, step: int):
        self.wheel.navigate_step(step)

    def _key_activate_wheel(self):
        self.wheel.activate_current()

    def _sticky_click(self, pos):
        """A click outside the pinned wheel puts it away."""
        if not self.wheel.isVisible():
            return
        if self.wheel.frameGeometry().contains(pos):
            return
        self.monitor.notify_dropped()
        self.wheel._close()

    def _refresh_wheel(self, mode):
        self._mode = mode
        self.wheel.set_mode(mode)
        files = self.wheel.file_paths()
        if not files:
            return
        old_hover = self.wheel._hover
        self.wheel.set_items(self._items_for(files, mode), animate=False)
        if 0 <= old_hover < len(self.wheel._items):
            self.wheel._set_hover_index(old_hover)
        else:
            from PySide6.QtGui import QCursor
            self.wheel.update_cursor(QCursor.pos())

    def _move_wheel(self, pos):
        if self.wheel.isVisible() and not self.wheel.is_keyboard_mode():
            self.wheel.update_cursor(pos)

    def _hide_wheel(self):
        self.wheel.set_keyboard_mode(False)
        self.wheel.dismiss()

    def _activated(self, files, key):
        self.monitor.notify_dropped()
        if not files:
            return
        from PySide6.QtGui import QCursor
        anchor = QCursor.pos()
        label = self._labels.get(key)
        if self._mode == "actions":
            window = actions.run_action(files, key, None, label, anchor=anchor)
        elif self._mode == "tools":
            subset = [
                str(p)
                for p in catalog.tool_paths(key, [Path(f) for f in files])
            ]
            if not subset:
                return
            window = actions.run_tool(subset, key, None, label, anchor=anchor)
        else:
            subset = [
                str(p)
                for p in catalog.conversion_paths(key, [Path(f) for f in files])
            ]
            if not subset:
                return
            window = actions.run_conversions(subset, key, None, None, anchor=anchor)
        self._track(window)

    def _track(self, window):
        if window is None:
            return
        if hasattr(window, "job_windows"):
            for job_window in window.job_windows:
                self._track(job_window)
            return
        if not hasattr(window, "job"):
            if hasattr(window, "job_window"):
                self._track(window.job_window)
                window.finished.connect(lambda *_: self._track(window.job_window))
            return
        if window in self._jobs or getattr(window, "_job_done", False):
            return
        self._jobs.append(window)
        window.job.finished.connect(lambda *_a, w=window: self._forget(w))
        window.job.failed.connect(lambda *_a, w=window: self._forget(w))

    def _forget(self, window):
        if window in self._jobs:
            self._jobs.remove(window)

    def _rebuild_active(self):
        self._active_menu.clear()
        if not self._jobs:
            self._active_menu.addAction(i18n.tr("tray.nothing_active")).setEnabled(False)
            return
        for window in list(self._jobs):
            action = self._active_menu.addAction(
                window.windowTitle() or i18n.tr("tray.working"))
            action.triggered.connect(lambda _=False, w=window: self._raise(w))

    @staticmethod
    def _raise(window):
        window.show()
        window.raise_()

    # -- tray ------------------------------------------------------------------
    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self._portable:
                self._show_companion()
            else:
                self.open_settings()

    def _show_companion(self):
        if self._portable:
            self.monitor.start()
            self.monitor.surface.activateWindow()

    def open_settings(self):
        if self._settings_window is not None and self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return self._settings_window
        try:
            from . import settings_window

            self._settings_window = settings_window.open_settings(pdf_callback=self.open_images_pdf)
        except ImportError:
            QMessageBox.warning(None, i18n.tr("app.name"), i18n.tr("tray.settings_unavailable"))
            self._settings_window = None
        return self._settings_window

    def open_images_pdf(self, files=None, order=None):
        from .editors.pdf import open_images_pdf
        try:
            window = open_images_pdf(files, order=order)
            self._track(window)
            return window
        except Exception as exc:
            log.exception("Could not open image PDF editor")
            QMessageBox.warning(None, i18n.tr("app.name"), str(exc))
            return None

    def handle_request(self, request):
        if request["action"] == "open-files":
            files = [str(Path(p).expanduser().resolve()) for p in request["paths"] if Path(p).expanduser().exists()]
            if self._portable:
                self.monitor.open_files(files)
            elif files:
                from PySide6.QtGui import QCursor
                self._show_wheel(QCursor.pos(), files, "conversion")
            return
        from .image_pdf import PdfOptions, is_pdf_image
        from . import engines, progress
        from PySide6.QtGui import QCursor
        files = [Path(p) for p in request["paths"]]
        if not files:
            self.open_images_pdf(order=request["order"])
            return
        if not all(is_pdf_image(p) and p.is_file() for p in files):
            QMessageBox.warning(None, i18n.tr("app.name"), i18n.tr("pdf.images.invalid"))
            return
        log.info("Image PDF request: count=%d order=%s quick=%s", len(files), request["order"], request["quick"])
        if request["quick"]:
            options = PdfOptions(order=request["order"])
            window = progress.run_job(i18n.tr("action.creating_pdf"),
                lambda ctx: [engines.images_to_pdf(files, ctx, set(), options)], anchor=QCursor.pos())
            self._track(window)
        else:
            self.open_images_pdf(files, request["order"])

    def _check_updates(self):
        QMessageBox.information(
            None,
            i18n.tr("app.name"),
            i18n.tr("tray.update_message", version=paths.APP_VERSION),
        )

    def _quit(self):
        if self._jobs:
            choice = QMessageBox.question(
                None,
                i18n.tr("app.name"),
                i18n.tr("tray.quit_running"),
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
        for window in list(self._jobs):
            job = getattr(window, "job", None)
            if job is not None:
                job.cancel()
        self.monitor.stop()
        self.app.quit()

    def notify_welcome(self):
        if self.tray_available:
            self.tray.showMessage(
                i18n.tr("app.name"),
                i18n.tr("tray.welcome"),
                QSystemTrayIcon.MessageIcon.Information,
                9000,
            )
        settings.set("welcomeShown", True)
        settings.save()


def _already_running(app):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.information(None, paths.APP_NAME, i18n.tr("tray.already_running"))
        return 1
    tray = QSystemTrayIcon(QIcon(str(paths.icon_path())))
    tray.show()
    tray.showMessage(
        i18n.tr("app.name"),
        i18n.tr("tray.already_running"),
        QSystemTrayIcon.MessageIcon.Information,
        5000,
    )
    QTimer.singleShot(5200, app.quit)
    app.exec()
    return 1


def _run():
    from .requests import RequestServer, forward_request, parse_request
    request = parse_request(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName(paths.APP_NAME)
    app.setApplicationVersion(paths.APP_VERSION)
    app.setOrganizationName(paths.APP_NAME)
    app.setWindowIcon(QIcon(str(paths.icon_path())))
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    theme.apply_app_theme()

    if request is not None and forward_request(request, 300):
        return 0

    lock = QLockFile(str(paths.data_dir() / "filepetal.lock"))
    if not lock.tryLock(0):
        if request is not None:
            # Another launch may hold the lock while its local pipe is starting.
            for _ in range(6):
                if forward_request(request, 500):
                    return 0
                # A missing pipe fails immediately; allow the lock owner time
                # to finish starting its server before the next attempt.
                QThread.msleep(150)
            log.error("The running FilePetal instance did not accept the image PDF request")
            _show_error(i18n.tr("pdf.instance.old"))
            return 2
        return _already_running(app)

    server = RequestServer(app)
    if not server.listen():
        raise RuntimeError(server.server.errorString())
    controller = Controller(app)
    server.received.connect(controller.handle_request)
    if request is not None:
        QTimer.singleShot(0, lambda: controller.handle_request(request))
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        def register():
            try:
                from .shell_integration import register_shell
                register_shell()
            except Exception:
                log.exception("Could not update Explorer integration")
        QTimer.singleShot(0, register)
    QTimer.singleShot(700, _warm_catalog)
    if not settings.get("welcomeShown"):
        controller.notify_welcome()
    return app.exec()


def main():
    logging.basicConfig(
        filename=str(paths.log_file()),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # comtypes logs an INFO line per generated module on every selection read.
    logging.getLogger("comtypes").setLevel(logging.WARNING)
    _install_excepthooks()
    try:
        return _run()
    except Exception as exc:
        text = (
            f"FilePetal failed to start: {exc}\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )
        log.error("FilePetal failed to start: %s", exc, exc_info=True)
        _write_crash_log(text)
        _show_error(text)
        return 1
