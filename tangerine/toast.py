"""Lightweight frosted toast notification for immediate actions.

Displays a compact frosted pill near the cursor / drop location to acknowledge
quick operations (Copy Path, Copy Files, Terminal, Move) without opening an empty
progress window.
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QLabel, QWidget

from . import theme
from .hud import HudBackdrop

log = logging.getLogger("tangerine")

_ACTIVE_TOASTS: set[ToastNotification] = set()


class ToastNotification(QWidget):
    """Compact translucent notification pill that fades in, waits, and fades out."""

    def __init__(self, message: str, parent: QWidget | None = None, anchor: QPoint | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._message = message
        self._anchor = QPoint(anchor) if anchor is not None else None
        self._opacity = 0.0
        self._backdrop = HudBackdrop()
        self._anim: QVariantAnimation | None = None

        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

        # Size based on text
        metrics = self.fontMetrics()
        text_w = metrics.horizontalAdvance(message)
        w = max(240, text_w + 50)
        h = 38
        self.resize(w, h)
        self._position()

        # Fade in
        self._fade_to(1.0, 160, self._start_hold_timer)

    def _position(self) -> None:
        screen = None
        if self._anchor is not None:
            screen = QGuiApplication.screenAt(self._anchor)
        if screen is None:
            screen = QGuiApplication.primaryScreen()

        area = screen.availableGeometry() if screen is not None else None
        w, h = self.width(), self.height()

        if self._anchor is not None and area is not None:
            x = self._anchor.x() + 20
            y = self._anchor.y() + 20
            if x + w > area.right():
                x = self._anchor.x() - w - 20
            if y + h > area.bottom():
                y = self._anchor.y() - h - 20
            x = max(area.left() + 10, min(x, area.right() - w - 10))
            y = max(area.top() + 10, min(y, area.bottom() - h - 10))
        elif area is not None:
            x = area.right() - w - 24
            y = area.bottom() - h - 48
        else:
            x, y = 100, 100

        self.move(int(x), int(y))

    def _fade_to(self, target: float, duration_ms: int, on_done=None) -> None:
        if self._anim is not None:
            self._anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(float(self._opacity))
        anim.setEndValue(float(target))
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic if target > self._opacity else QEasingCurve.Type.InCubic)

        def on_tick(v):
            self._opacity = float(v)
            self.setWindowOpacity(self._opacity)
            self.update()

        anim.valueChanged.connect(on_tick)
        if on_done:
            anim.finished.connect(on_done)
        self._anim = anim
        anim.start()

    def _start_hold_timer(self) -> None:
        QTimer.singleShot(1800, self._fade_out)

    def _fade_out(self) -> None:
        self._fade_to(0.0, 240, self.close)

    def showEvent(self, event) -> None:
        self._backdrop.capture(self.frameGeometry())
        super().showEvent(event)

    def moveEvent(self, event) -> None:
        self._backdrop.capture(self.frameGeometry())
        super().moveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dark = theme.is_dark()
        tokens = theme.hud(dark)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0

        # Backing wash
        wash = theme.qcolor(tokens["wash"])
        painted = self._backdrop.paint(painter, rect, wash, radius)
        if not painted:
            fallback = QColor(26, 24, 22, 180) if dark else QColor(250, 248, 245, 195)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fallback)
            painter.drawRoundedRect(rect, radius, radius)

        # Frosted glass highlight and border
        if dark:
            highlight = QColor(255, 255, 255, 55)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), radius - 1, radius - 1)
            border = QColor(255, 255, 255, 40)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, radius, radius)
        else:
            highlight = QColor(255, 255, 255, 190)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), radius - 1, radius - 1)
            border = QColor(0, 0, 0, 32)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, radius, radius)

        # Accent checkmark pill
        check_rect = QRectF(rect.left() + 8, rect.top() + (rect.height() - 20) / 2.0, 20, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawEllipse(check_rect)

        # Checkmark icon
        painter.setPen(QPen(QColor("#2B1608"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        cx = check_rect.center().x()
        cy = check_rect.center().y()
        painter.drawLine(QPoint(int(cx - 4), int(cy)), QPoint(int(cx - 1), int(cy + 3)))
        painter.drawLine(QPoint(int(cx - 1), int(cy + 3)), QPoint(int(cx + 4), int(cy - 3)))

        # Text
        text_rect = QRectF(rect.left() + 36, rect.top(), rect.width() - 44, rect.height())
        painter.setPen(theme.qcolor(tokens["icon"]))
        painter.setFont(self.font())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._message)

        painter.end()

    def closeEvent(self, event) -> None:
        _ACTIVE_TOASTS.discard(self)
        super().closeEvent(event)


def show_toast(message: str, anchor: QPoint | None = None) -> ToastNotification:
    """Show a transient toast notification near anchor or bottom-right."""
    toast = ToastNotification(message, anchor=anchor)
    _ACTIVE_TOASTS.add(toast)
    toast.show()
    return toast
