"""Portable file-drop companion used on macOS and Linux.

Windows keeps its Explorer drag monitor. On macOS and Linux, FilePetal cannot
reliably inspect another application's file selection globally, so this small
surface accepts native file drops and opens the same conversion, tools, and
actions wheel for the dropped files.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import i18n, paths, theme


class FileDropSurface(QWidget):
    """Small translucent companion that accepts one or more local files."""

    wheelRequested = Signal(object, str, object)

    def __init__(self, parent=None):
        super().__init__(None)
        self.setObjectName("FilePetalDropSurface")
        self.setWindowTitle(paths.APP_NAME)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setMinimumSize(330, 205)
        self.resize(370, 228)
        self._files: list[str] = []
        self._drag_offset = QPoint()
        self._build_ui()
        theme.add_theme_listener(self._theme_changed)
        self.destroyed.connect(lambda *_: theme.remove_theme_listener(self._theme_changed))

    def _theme_changed(self, _dark):
        self.update()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        self._title = QLabel(paths.APP_NAME)
        self._title.setStyleSheet("font-weight: 700; font-size: 15px; background: transparent;")
        header.addWidget(self._title)
        header.addStretch(1)
        self._close_button = QPushButton("×")
        self._close_button.setFixedSize(28, 28)
        self._close_button.setToolTip(i18n.tr("portable.hide"))
        self._close_button.clicked.connect(self.hide)
        header.addWidget(self._close_button)
        root.addLayout(header)

        self._drop_hint = QLabel(i18n.tr("portable.drop"))
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setMinimumHeight(74)
        self._drop_hint.setWordWrap(True)
        self._drop_hint.setStyleSheet(
            "background: rgba(255,255,255,24); border: 1px dashed rgba(255,255,255,100);"
            "border-radius: 12px; padding: 10px;"
        )
        root.addWidget(self._drop_hint)

        self._status = QLabel(i18n.tr("portable.no_files"))
        self._status.setObjectName("dim")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

        row = QHBoxLayout()
        self._choose_button = QPushButton(i18n.tr("portable.choose"))
        self._choose_button.clicked.connect(self._choose_files)
        row.addWidget(self._choose_button)
        row.addStretch(1)
        self._mode_buttons = []
        for label, mode in (
            (i18n.tr("wheel.convert"), "conversion"),
            (i18n.tr("wheel.tools"), "tools"),
            (i18n.tr("wheel.actions"), "actions"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=mode: self._open_wheel(value))
            row.addWidget(button)
            self._mode_buttons.append((button, mode))
        root.addLayout(row)
        self.setStyleSheet(
            "QPushButton { border-radius: 9px; padding: 6px 9px; }"
            "QLabel#dim { color: palette(mid); background: transparent; font-size: 11px; }"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        color = QColor(28, 30, 36, 224) if theme.is_dark() else QColor(248, 247, 244, 224)
        border = QColor(255, 255, 255, 62) if theme.is_dark() else QColor(25, 25, 25, 44)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.fillPath(path, color)
        painter.setPen(border)
        painter.drawPath(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and Path(url.toLocalFile()).exists()
        ]
        self.set_files(files)
        if files:
            event.acceptProposedAction()
            self._open_wheel("conversion")
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, i18n.tr("portable.choose"))
        self.set_files(files)
        if files:
            self._open_wheel("conversion")

    def set_files(self, files):
        self._files = [str(Path(p).resolve()) for p in files if Path(p).exists()]
        if not self._files:
            self._status.setText(i18n.tr("portable.no_files"))
            self._drop_hint.setText(i18n.tr("portable.drop"))
            return
        count = len(self._files)
        self._status.setText(i18n.tr("portable.ready", n=count))
        names = [Path(p).name for p in self._files[:3]]
        if count > 3:
            names.append(f"and {count - 3} more")
        self._drop_hint.setText("\n".join(names))

    def retranslate(self):
        self._close_button.setToolTip(i18n.tr("portable.hide"))
        self._choose_button.setText(i18n.tr("portable.choose"))
        for button, mode in self._mode_buttons:
            key = {"conversion": "wheel.convert", "tools": "wheel.tools", "actions": "wheel.actions"}[mode]
            button.setText(i18n.tr(key))
        if not self._files:
            self._drop_hint.setText(i18n.tr("portable.drop"))
            self._status.setText(i18n.tr("portable.no_files"))
        else:
            self._status.setText(i18n.tr("portable.ready", n=len(self._files)))

    def _open_wheel(self, mode):
        if self._files:
            self.wheelRequested.emit(list(self._files), mode, QCursor.pos())


class PortableMonitor(QObject):
    """Signal-compatible companion for the Windows-only DragMonitor."""

    wheelShown = Signal(object, object, str)
    wheelMoved = Signal(object)
    wheelHidden = Signal()
    wheelRefreshed = Signal(str)
    keyboardTriggered = Signal(object, object, str)
    stickyTriggered = Signal(object, object, str)
    stickyClicked = Signal(object)
    wheelNavigated = Signal(int)
    wheelKeyActivated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.surface = FileDropSurface()
        self.surface.wheelRequested.connect(self._request_wheel)

    def _request_wheel(self, files, mode, pos):
        self.wheelShown.emit(pos, files, mode)

    def start(self):
        self.surface.show()
        self.surface.raise_()

    def retranslate(self):
        self.surface.retranslate()

    def open_files(self, files):
        self.surface.set_files(files)
        self.surface.show()
        self.surface.raise_()
        if self.surface._files:
            QTimer.singleShot(
                0,
                lambda: self._request_wheel(
                    list(self.surface._files), "conversion", QCursor.pos()
                ),
            )

    def notify_dropped(self):
        pass

    def sticky_release(self):
        pass

    def stop(self):
        self.surface.close()
