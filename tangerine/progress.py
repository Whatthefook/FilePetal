"""Closable mini progress cards with the custom Tangerine orange bar.

The card follows the v1.7.0 HUD language: a translucent frosted surface (the
blurred desktop behind it plus a warm wash), 22 px rounded corners and a soft
shadow.  The header carries a peach close chip and a bold centred title, the
file name sits underneath and a thin orange bar tracks the job.

Closing the card lets the job continue; the Cancel action only appears while
the pointer hovers the card.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import i18n, theme
from .hud import HudBackdrop
from .jobs import Job

log = logging.getLogger("tangerine")

_ACTIVE: set["ProgressWindow"] = set()

WINDOW_WIDTH = 360
CARD_RADIUS = 16.0
SHADOW_MARGIN = 12
CHIP_SIZE = 26
BAR_HEIGHT = 8
ANCHOR_GAP = 18


def _paint_shadow(painter: QPainter, card: QRectF, dark: bool) -> None:
    """Soft drop shadow fading into the transparent card margin."""
    painter.setPen(Qt.PenStyle.NoPen)
    layer_alpha = 16 if dark else 12
    for step in range(SHADOW_MARGIN, 0, -2):
        painter.setBrush(QColor(0, 0, 0, layer_alpha))
        painter.drawRoundedRect(
            card.adjusted(-step, -step + 2, step, step + 4),
            CARD_RADIUS + step * 0.5,
            CARD_RADIUS + step * 0.5,
        )


class OrangeProgressBar(QWidget):
    """Custom-drawn orange progress bar (determinate and marquee)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(BAR_HEIGHT)
        self._value = 0.0
        self._indeterminate = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def set_value(self, value: float) -> None:
        if value < 0:
            self._indeterminate = True
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._indeterminate = False
            self._timer.stop()
        self._value = max(0.0, min(value, 1.0))
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        radius = self.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(theme.hud(theme.is_dark())["track"]))
        painter.drawRoundedRect(rect, radius, radius)
        if self._indeterminate:
            span = self.width() * 0.32
            offset = (self.width() + span) * self._phase - span
            chunk = QRectF(offset, 0, span, self.height())
            painter.setClipRect(rect)
            painter.setBrush(QColor(theme.ACCENT))
            painter.drawRoundedRect(chunk, radius, radius)
        elif self._value > 0:
            chunk = QRectF(0, 0, self.width() * self._value, self.height())
            painter.setBrush(QColor(theme.ACCENT))
            painter.drawRoundedRect(chunk, radius, radius)
        painter.end()


class _CloseChip(QWidget):
    """Round peach chip with a painted ✕; clicking it closes the card."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(CHIP_SIZE, CHIP_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        tokens = theme.hud(theme.is_dark())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(tokens["peach"]))
        painter.drawEllipse(QRectF(0, 0, CHIP_SIZE, CHIP_SIZE))
        pen = QPen(theme.qcolor(tokens["icon"]), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        inset = CHIP_SIZE * 0.36
        painter.drawLine(
            QPointF(inset, inset), QPointF(CHIP_SIZE - inset, CHIP_SIZE - inset))
        painter.drawLine(
            QPointF(CHIP_SIZE - inset, inset), QPointF(inset, CHIP_SIZE - inset))
        painter.end()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _Card(QWidget):
    """Frosted surface: soft shadow, blurred backdrop, wash and hairline."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.backdrop = HudBackdrop()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dark = theme.is_dark()
        card = QRectF(self.rect()).adjusted(
            SHADOW_MARGIN, SHADOW_MARGIN, -SHADOW_MARGIN, -SHADOW_MARGIN)
        _paint_shadow(painter, card, dark)
        wash = theme.qcolor(theme.hud(dark)["wash"])
        self.backdrop.paint(painter, card, wash, CARD_RADIUS)
        edge = QColor(255, 255, 255, 70) if dark else QColor(255, 255, 255, 190)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(edge, 1.0))
        painter.drawRoundedRect(
            card.adjusted(0.5, 0.5, -0.5, -0.5), CARD_RADIUS, CARD_RADIUS)
        painter.end()


class ProgressWindow(QWidget):
    """Rounded mini window; closing it lets the job continue."""

    finished_closed = Signal(object)
    _cascade = [0]

    def __init__(self, title: str, job: Job, parent: QWidget | None = None,
                 anchor: QPoint | None = None):
        super().__init__(parent)
        self.job = job
        self.outputs: list[Path] = []
        self.failed = False
        self._anchor = QPoint(anchor) if anchor is not None else None
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(WINDOW_WIDTH)
        self.setWindowTitle(title)

        palette = theme.palette(theme.is_dark())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = _Card(self)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(
            SHADOW_MARGIN + 18, SHADOW_MARGIN + 18, SHADOW_MARGIN + 18,
            SHADOW_MARGIN + 20)
        layout.setSpacing(10)

        header = QGridLayout()
        header.setContentsMargins(0, 0, 0, 0)
        close_chip = _CloseChip(self.card)
        close_chip.clicked.connect(self.close)
        header.addWidget(close_chip, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            f"font-weight: 700; font-size: 14px; color: {palette['text']};")
        header.addWidget(self.title_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(header)

        self.status_label = QLabel(i18n.tr("progress.starting"))
        self.status_label.setProperty("muted", True)
        self.status_label.setStyleSheet(
            f"color: {palette['text_dim']}; font-size: 13px;")
        self.status_label.setMinimumHeight(20)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.bar = OrangeProgressBar(self.card)
        layout.addWidget(self.bar)

        self.error_view = QPlainTextEdit(self.card)
        self.error_view.setReadOnly(True)
        self.error_view.setVisible(False)
        self.error_view.setFixedHeight(120)
        layout.addWidget(self.error_view)

        self.cancel_btn = QPushButton(i18n.tr("progress.cancel"), self.card)
        self.cancel_btn.setProperty("chip", "true")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self._cancel_clicked)
        self.cancel_btn.setVisible(False)
        policy = self.cancel_btn.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # no layout jump while hovering
        self.cancel_btn.setSizePolicy(policy)
        cancel_row = QHBoxLayout()
        cancel_row.setContentsMargins(0, 0, 0, 0)
        cancel_row.addWidget(self.cancel_btn)
        cancel_row.addStretch(1)
        layout.addLayout(cancel_row)

        self.dismiss_btn = QPushButton(i18n.tr("progress.dismiss"), self.card)
        self.dismiss_btn.setProperty("accent", "true")
        self.dismiss_btn.setVisible(False)
        self.dismiss_btn.clicked.connect(self.close)
        dismiss_row = QHBoxLayout()
        dismiss_row.setContentsMargins(0, 0, 0, 0)
        dismiss_row.addWidget(self.dismiss_btn)
        dismiss_row.addStretch(1)
        layout.addLayout(dismiss_row)

        self._shown_once = False
        self._dismissed = False
        self._job_done = False
        self._position()
        self._capture_backdrop()

        job.progress.connect(self._on_progress)
        job.status.connect(self._on_status)
        job.finished.connect(self._on_finished)
        job.failed.connect(self._on_failed)

    # -- placement ---------------------------------------------------------
    def _position(self) -> None:
        """Anchor the card near the drop point, else cascade around the centre."""
        height = self.sizeHint().height() or self.height()
        if self._anchor is not None:
            screen = (
                QGuiApplication.screenAt(self._anchor) or QGuiApplication.primaryScreen()
            )
            if screen is not None:
                area = screen.availableGeometry()
                # Place near the drop point without covering the drop point or cursor
                x = self._anchor.x() + 24
                y = self._anchor.y() + 24
                if x + self.width() > area.right() - SHADOW_MARGIN:
                    x = self._anchor.x() - self.width() - 24
                if y + height > area.bottom() - SHADOW_MARGIN:
                    y = self._anchor.y() - height - 24
                x = min(max(x, area.left() + SHADOW_MARGIN),
                        max(area.left(), area.right() - self.width() - SHADOW_MARGIN))
                y = min(max(y, area.top() + SHADOW_MARGIN),
                        max(area.top(), area.bottom() - height - SHADOW_MARGIN))
                self.move(int(x), int(y))
                return
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else None
        offset = ProgressWindow._cascade[0] % 6
        ProgressWindow._cascade[0] += 1
        if area is None:
            self.move(offset * 26, offset * 26)
            return
        x = area.center().x() - self.width() // 2 + offset * 26
        y = area.center().y() - height // 2 + offset * 26
        self.move(x, y)

    def _capture_backdrop(self) -> None:
        """Refresh the frosted backdrop for the card's current geometry."""
        self.card.backdrop.capture(self.frameGeometry())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._shown_once:
            self._shown_once = True
            self._position()
        self._capture_backdrop()

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        self._capture_backdrop()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._capture_backdrop()

    # -- hover: reveal the Cancel action -------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        if not self._job_done:
            self.cancel_btn.setVisible(True)

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.cancel_btn.setVisible(False)

    # -- job wiring ----------------------------------------------------------
    def _on_progress(self, value: float) -> None:
        self.bar.set_value(value)

    def _on_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _cancel_clicked(self) -> None:
        self.job.cancel()
        self.status_label.setText(i18n.tr("progress.cancelling"))

    def _on_finished(self, outputs: list) -> None:
        self._job_done = True
        self.cancel_btn.setVisible(False)
        self.outputs = list(outputs)
        check_timer = QTimer(self)
        check_timer.setInterval(300)
        attempts = [0]

        def verify() -> None:
            attempts[0] += 1
            if not self.outputs or all(Path(p).exists() for p in self.outputs):
                check_timer.stop()
                self.bar.set_value(1.0)
                self.close()
            elif attempts[0] >= 50:
                check_timer.stop()
                self.bar.set_value(1.0)
                self.status_label.setText(i18n.tr("progress.output_unconfirmed"))
                self.close()

        check_timer.timeout.connect(verify)
        check_timer.start()

    def _on_failed(self, message: str) -> None:
        self._fail(message)

    def _fail(self, message: str) -> None:
        self.failed = True
        self._job_done = True
        self.cancel_btn.setVisible(False)
        if self._dismissed:
            log.warning("Job failed after the progress window was dismissed: %s", message)
            return
        self.bar.set_value(0.0)
        if self.job.cancel_event.is_set():
            self.status_label.setText(i18n.tr("progress.cancelled"))
        else:
            self.status_label.setText(i18n.tr("progress.operation_failed"))
        self.error_view.setPlainText(message)
        self.error_view.setVisible(True)
        self.dismiss_btn.setVisible(True)
        self.show()
        self.raise_()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._job_done:
            self._dismissed = True
        _ACTIVE.discard(self)
        super().closeEvent(event)
        self.finished_closed.emit(self)


def run_job(title: str, work, parent: QWidget | None = None,
            anchor: QPoint | None = None) -> ProgressWindow:
    """Show a progress card for *work*, optionally anchored at *anchor*."""
    job = Job(work, parent)
    window = ProgressWindow(title, job, parent, anchor)
    _ACTIVE.add(window)
    window.show()
    job.start()
    return window
