"""FilePetal Shelf: a floating, pin-able shelf for dragging, staging and holding files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo, QPoint, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import i18n, naming, theme
from .hud import HudBackdrop

_SHELF_INSTANCE: FilePetalShelf | None = None


def open_shelf(files: list[str | Path] | None = None, parent: QWidget | None = None) -> FilePetalShelf:
    global _SHELF_INSTANCE
    if _SHELF_INSTANCE is None:
        _SHELF_INSTANCE = FilePetalShelf()
    if files:
        _SHELF_INSTANCE.add_files(files)
    _SHELF_INSTANCE.show()
    _SHELF_INSTANCE.raise_()
    _SHELF_INSTANCE.activateWindow()
    return _SHELF_INSTANCE


class ShelfListWidget(QListWidget):
    """List widget supporting drag-out of files to Explorer or other apps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 8px;
                background: transparent;
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 6px;
                padding: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: rgba(255, 140, 0, 0.15);
            }
            QListWidget::item:selected {
                background: rgba(255, 140, 0, 0.35);
                color: palette(text);
            }
        """)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        items = self.selectedItems()
        if not items:
            items = [self.item(i) for i in range(self.count())]
        urls = []
        paths = []
        for item in items:
            p = item.data(Qt.ItemDataRole.UserRole)
            if p and Path(p).exists():
                urls.append(QUrl.fromLocalFile(str(p)))
                paths.append(str(p))
        if not urls:
            return
        drag = QDrag(self)
        from PySide6.QtCore import QMimeData

        drag_mime = QMimeData()
        drag_mime.setUrls(urls)
        drag_mime.setText("\n".join(paths))
        drag.setMimeData(drag_mime)
        drag.exec_(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local and Path(local).exists():
                    paths.append(local)
            if paths:
                window = self.window()
                if isinstance(window, FilePetalShelf):
                    window.add_files(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class FilePetalShelf(QWidget):
    """Floating, pin-able shelf for staging files with drag-out support."""

    RADIUS = 18.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(None)
        self.setObjectName("FilePetalShelf")
        self.setWindowTitle(i18n.tr("shelf.title"))
        self.resize(340, 420)
        self.setMinimumSize(280, 300)
        self._pinned = True
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | (Qt.WindowType.WindowStaysOnTopHint if self._pinned else Qt.WindowType.Widget)
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._icon_provider = QFileIconProvider()
        self._files: list[Path] = []
        self._drag_pos = QPoint()
        self._backdrop = HudBackdrop()
        self._press_pos: QPoint | None = None

        self._build_ui()
        theme.add_theme_listener(self._apply_theme)
        self.destroyed.connect(lambda *_args: theme.remove_theme_listener(self._apply_theme))
        self._apply_theme()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._press_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:
        self._backdrop.capture(self.frameGeometry())
        super().showEvent(event)

    def moveEvent(self, event) -> None:
        self._backdrop.capture(self.frameGeometry())
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        self._backdrop.capture(self.frameGeometry())
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        dark = theme.is_dark()
        tokens = theme.hud(dark)
        wash = theme.qcolor(tokens["wash"])

        painted = self._backdrop.paint(painter, rect, wash, self.RADIUS)
        if not painted:
            fallback = QColor(26, 24, 22, 180) if dark else QColor(250, 248, 245, 195)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fallback)
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        # Translucent glass specular highlight & border
        if dark:
            highlight = QColor(255, 255, 255, 50)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), self.RADIUS - 1, self.RADIUS - 1)
            border = QColor(255, 255, 255, 36)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        else:
            highlight = QColor(255, 255, 255, 190)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), self.RADIUS - 1, self.RADIUS - 1)
            border = QColor(0, 0, 0, 32)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.end()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Header with Title, Pin Toggle, and Close
        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel(i18n.tr("shelf.title"))
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        title_label.setFont(font)
        header.addWidget(title_label)

        header.addStretch(1)

        self.pin_btn = QPushButton("📌" if self._pinned else "📍")
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setToolTip(i18n.tr("shelf.pin_tooltip"))
        self.pin_btn.clicked.connect(self._toggle_pin)
        header.addWidget(self.pin_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setToolTip(i18n.tr("action.done"))
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        root.addLayout(header)

        # Subtitle / Hint
        self.hint_label = QLabel(i18n.tr("shelf.hint"))
        self.hint_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        # File List
        self.list_widget = ShelfListWidget(self)
        self.list_widget.itemDoubleClicked.connect(self._open_file)
        root.addWidget(self.list_widget, 1)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.setSpacing(8)

        copy_btn = QPushButton(i18n.tr("shelf.copy_files"))
        copy_btn.clicked.connect(self._copy_all)
        footer.addWidget(copy_btn)

        clear_btn = QPushButton(i18n.tr("shelf.clear"))
        clear_btn.clicked.connect(self.clear_files)
        footer.addWidget(clear_btn)

        root.addLayout(footer)

    def _apply_theme(self) -> None:
        dark = theme.is_dark()
        text = "#f0f0f5" if dark else "#1a1a24"
        self.setStyleSheet(f"""
            QWidget#FilePetalShelf {{
                background: transparent;
                color: {text};
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 4px 10px;
                background: rgba(128, 128, 128, 0.18);
                color: {text};
            }}
            QPushButton:hover {{
                background: rgba(255, 140, 0, 0.35);
            }}
        """)
        self.update()

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
        self.pin_btn.setText("📌" if self._pinned else "📍")
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | (Qt.WindowType.WindowStaysOnTopHint if self._pinned else Qt.WindowType.Widget)
        )
        self.setWindowFlags(flags)
        self.show()

    def add_files(self, paths: list[str | Path]) -> None:
        for p in paths:
            path_obj = Path(p).resolve()
            if path_obj in self._files:
                continue
            if not path_obj.exists():
                continue
            self._files.append(path_obj)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(path_obj))
            qfi = QFileInfo(str(path_obj))
            icon = self._icon_provider.icon(qfi)
            item.setIcon(icon)
            size_str = naming.human_size(path_obj.stat().st_size) if path_obj.is_file() else ""
            item.setText(f"{path_obj.name}  ({size_str})" if size_str else path_obj.name)
            item.setToolTip(str(path_obj))
            self.list_widget.addItem(item)
        self._update_hint()

    def clear_files(self) -> None:
        self._files.clear()
        self.list_widget.clear()
        self._update_hint()

    def _update_hint(self) -> None:
        count = len(self._files)
        if count == 0:
            self.hint_label.setText(i18n.tr("shelf.empty_hint"))
        else:
            self.hint_label.setText(i18n.tr("shelf.count_hint", count=count))

    def _open_file(self, item: QListWidgetItem) -> None:
        p = item.data(Qt.ItemDataRole.UserRole)
        if p and Path(p).exists():
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _copy_all(self) -> None:
        from PySide6.QtCore import QMimeData

        urls = [QUrl.fromLocalFile(str(p)) for p in self._files if p.exists()]
        if not urls:
            return
        mime = QMimeData()
        mime.setUrls(urls)
        mime.setText("\n".join(str(p) for p in self._files))
        QApplication.clipboard().setMimeData(mime)
