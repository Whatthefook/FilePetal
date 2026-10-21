"""Shared dialog scaffolding and small conversion helpers for tool editors.

Dialogs are drawn as frameless translucent cards that mirror the macOS
"liquid glass" look of the reference video: a captured (and blurred) slice of
what is behind the window, a warm wash on top, rounded corners (22 px), a soft
edge and a custom header with a peach close chip and a bold centred title.

The HUD backdrop helper (``tangerine/hud.py``) and its theme tokens land in
parallel with this file, so both are used defensively: if anything is missing
(or the screen grab fails, as it does offscreen) the card falls back to the
solid theme colour.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import i18n, jobs, progress, theme, tool_defaults


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def pil_to_qimage(img) -> QImage:
    rgba = img if img.mode == "RGBA" else img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    return QImage(
        data, rgba.width, rgba.height, rgba.width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


def pil_to_pixmap(img, max_w: int, max_h: int) -> QPixmap:
    preview = img.copy()
    preview.thumbnail((max_w, max_h))
    return QPixmap.fromImage(pil_to_qimage(preview))


def run_batch(paths, run_one, title=None):
    paths = [Path(p) for p in paths]

    def work(ctx):
        reserved: set[Path] = set()
        outputs = []
        total = len(paths)
        for index, path in enumerate(paths):
            sub = jobs.batch_ctx(ctx, total, index) if total > 1 else ctx
            result = run_one(path, sub, reserved)
            if isinstance(result, list):
                outputs.extend(result)
            elif result is not None:
                outputs.append(result)
        return outputs

    if title is None:
        title = (
            i18n.tr("action.working_on", name=paths[0].name) if len(paths) == 1
            else i18n.tr("action.working_on_many", n=len(paths))
        )
    return progress.run_job(title, work)


# ---------------------------------------------------------------------------
# Theme / HUD helpers (defensive)
# ---------------------------------------------------------------------------

_CHIP_QSS_CACHE: dict[bool, bool] = {}


def hud_tokens(dark: bool | None = None) -> dict:
    """Return the HUD token dict from the theme, or an empty dict."""
    if dark is None:
        dark = theme.is_dark()
    provider = getattr(theme, "hud", None)
    if not callable(provider):
        return {}
    try:
        tokens = provider(dark)
    except Exception:
        return {}
    return dict(tokens) if tokens else {}


def _rgba_tuple(value) -> tuple[int, int, int, int] | None:
    try:
        parts = tuple(int(part) for part in tuple(value))
    except Exception:
        return None
    if len(parts) == 3:
        return parts[0], parts[1], parts[2], 255
    if len(parts) == 4:
        return parts
    return None


def _as_qcolor(value, fallback: tuple[int, int, int, int]) -> QColor:
    if isinstance(value, QColor):
        return QColor(value)
    if isinstance(value, str):
        color = QColor(value)
        if color.isValid():
            return color
        return QColor(*fallback)
    if value is not None:
        parts = _rgba_tuple(value)
        if parts is not None:
            return QColor(*parts)
    return QColor(*fallback)


def _token_to_qss(value) -> str | None:
    """CSS colour text for a theme token (str, tuple or QColor)."""
    if isinstance(value, QColor):
        if value.alpha() >= 255:
            return value.name()
        return "rgba(%d, %d, %d, %d)" % (
            value.red(), value.green(), value.blue(), value.alpha())
    if isinstance(value, str):
        return value
    if value is not None:
        parts = _rgba_tuple(value)
        if parts is not None:
            return "rgba(%d, %d, %d, %d)" % parts
    return None


def card_color(dark: bool) -> QColor:
    return QColor(26, 24, 22, 180) if dark else QColor(250, 248, 245, 195)


def wash_color(dark: bool) -> QColor:
    tokens = hud_tokens(dark)
    fallback = (24, 21, 19, 130) if dark else (255, 248, 242, 135)
    return _as_qcolor(tokens.get("wash"), fallback)


def _border_color(dark: bool) -> QColor:
    return QColor(theme.palette(dark)["border"])


def _shadow_color(dark: bool) -> QColor:
    raw = theme.palette(dark).get("shadow", (0, 0, 0, 70))
    if isinstance(raw, str):
        color = QColor(raw)
        return color if color.isValid() else QColor(0, 0, 0, 70)
    try:
        r, g, b, a = tuple(raw)
        return QColor(int(r), int(g), int(b), int(a))
    except Exception:
        return QColor(0, 0, 0, 70)


def _theme_styles_chips() -> bool:
    """True when the global stylesheet already styles ``QPushButton[chip]``."""
    dark = theme.is_dark()
    cached = _CHIP_QSS_CACHE.get(dark)
    if cached is None:
        try:
            cached = 'chip' in theme.stylesheet(dark)
        except Exception:
            cached = False
        _CHIP_QSS_CACHE[dark] = cached
    return cached


def chip_button(text: str, parent: QWidget | None = None) -> QPushButton:
    """Peach 'chip' button used for secondary actions (Reset, Play, …)."""
    button = QPushButton(text, parent)
    button.setProperty("chip", True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if not _theme_styles_chips():
        dark = theme.is_dark()
        tokens = hud_tokens(dark)
        background = _token_to_qss(tokens.get("peach")) or (
            "#4A392D" if dark else "#F8DCC4")
        foreground = _token_to_qss(tokens.get("icon")) or (
            theme.palette(dark)["text"] if dark else "#3A2416")
        hover = background
        probe = QColor(background)
        if probe.isValid():
            hover = probe.lighter(106).name() if dark else probe.darker(104).name()
        button.setStyleSheet(
            "QPushButton { background: %s; border: none; border-radius: 9px;"
            " padding: 5px 12px; color: %s; font-weight: 600; }"
            "QPushButton:hover { background: %s; }"
            "QPushButton:disabled { color: %s; }"
            % (background, foreground, hover, theme.palette(dark)["text_dim"])
        )
    return button


def section_label(text: str, parent: QWidget | None = None) -> QLabel:
    """Small bold label used for section / field headings."""
    label = QLabel(text, parent)
    font = label.font()
    font.setPixelSize(12)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    return label


def align_form(form) -> None:
    """Right-align the labels of a QFormLayout (label + control rows)."""
    try:
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dialog shell
# ---------------------------------------------------------------------------

class _DialogHeader(QWidget):
    """Draggable header: peach close chip, bold centred title, hairline."""

    HEIGHT = 54

    def __init__(self, title: str, owner: "ToolDialog"):
        super().__init__(owner)
        self._owner = owner
        self._press = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget(self)
        bar.setFixedHeight(self.HEIGHT)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 9, 14, 9)
        row.setSpacing(6)

        self.close_button = QPushButton("\u00d7", bar)
        self.close_button.setFixedSize(36, 36)
        self.close_button.setFlat(True)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setToolTip(i18n.tr("btn.close"))
        self.close_button.clicked.connect(owner.reject)
        self._style_close()
        row.addWidget(self.close_button)

        self.title_label = QLabel(title, bar)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.title_label.font()
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.Bold)
        self.title_label.setFont(font)
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(self.title_label, 1)

        spacer = QWidget(bar)
        spacer.setFixedSize(36, 36)
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(spacer)

        outer.addWidget(bar)

        self.hairline = QFrame(self)
        self.hairline.setFixedHeight(1)
        self.hairline.setFrameShape(QFrame.Shape.NoFrame)
        self.hairline.setStyleSheet(
            "background: %s;" % ("rgba(255, 255, 255, 0.12)" if theme.is_dark() else "rgba(0, 0, 0, 0.08)"))
        outer.addWidget(self.hairline)

    def _style_close(self) -> None:
        dark = theme.is_dark()
        tokens = hud_tokens(dark)
        background = _as_qcolor(
            tokens.get("peach"), (241, 216, 194, 255) if not dark else (74, 57, 45, 255))
        icon = _as_qcolor(
            tokens.get("icon"), (58, 36, 22, 255) if not dark else (242, 237, 231, 255))
        hover = background.lighter(106) if dark else background.darker(104)
        self.close_button.setStyleSheet(
            "QPushButton { background: %s; color: %s; border: none;"
            " border-radius: 18px; font-size: 15px; font-weight: 700;"
            " padding: 0; }"
            "QPushButton:hover { background: %s; }"
            % (background.name(), icon.name(), hover.name())
        )

    # -- window dragging -------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = (
                event.globalPosition().toPoint()
                - self._owner.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._owner.move(event.globalPosition().toPoint() - self._press)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._press = None
        super().mouseReleaseEvent(event)


class ToolDialog(QDialog):
    """Frameless translucent card dialog with a body layout and button row."""

    RADIUS = 22.0
    BACKDROP_THROTTLE_S = 0.3

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizeGripEnabled(True)

        self._backdrop = None
        self._backdrop_ready = False
        self._backdrop_at = 0.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = _DialogHeader(title, self)
        outer.addWidget(self._header)

        self._content = QWidget(self)
        self._body = QVBoxLayout(self._content)
        self._body.setContentsMargins(18, 14, 18, 16)
        self._body.setSpacing(12)
        outer.addWidget(self._content, 1)

    # -- backdrop / painting ---------------------------------------------
    def _backdrop_instance(self):
        if self._backdrop is None:
            try:
                from ..hud import HudBackdrop

                try:
                    self._backdrop = HudBackdrop()
                except TypeError:
                    self._backdrop = HudBackdrop(None)
            except Exception:
                self._backdrop = False
        return self._backdrop or None

    def _capture_backdrop(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._backdrop_at < self.BACKDROP_THROTTLE_S:
            return
        self._backdrop_at = now
        backdrop = self._backdrop_instance()
        if backdrop is None:
            self._backdrop_ready = False
            return
        try:
            backdrop.capture(self.frameGeometry())
            self._backdrop_ready = True
        except Exception:
            self._backdrop_ready = False
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        for combo in self.findChildren(QComboBox):
            combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_to_screen()
        self._capture_backdrop(force=True)
        super().showEvent(event)

    def _fit_to_screen(self) -> None:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            max_w = int(area.width() * 0.90)
            max_h = int(area.height() * 0.90)
            w = min(self.width(), max_w)
            h = min(self.height(), max_h)
            if (w, h) != (self.width(), self.height()):
                self.resize(w, h)

    def moveEvent(self, event) -> None:  # noqa: N802
        self._capture_backdrop()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._capture_backdrop()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        dark = theme.is_dark()

        painted = False
        backdrop = self._backdrop_instance() if self._backdrop_ready else None
        if backdrop is not None:
            try:
                painted = bool(
                    backdrop.paint(painter, rect, wash_color(dark), self.RADIUS))
            except Exception:
                painted = False
        if not painted:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(card_color(dark))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        # Translucent frosted glass highlights & boundary
        if dark:
            highlight = QColor(255, 255, 255, 50)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(1.0, 1.0, -1.0, -1.0), self.RADIUS - 1, self.RADIUS - 1)
            border = QColor(255, 255, 255, 36)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        else:
            highlight = QColor(255, 255, 255, 190)
            painter.setPen(QPen(highlight, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(1.0, 1.0, -1.0, -1.0), self.RADIUS - 1, self.RADIUS - 1)
            border = QColor(0, 0, 0, 32)
            painter.setPen(QPen(border, 1.0))
            painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.end()

    # -- buttons -----------------------------------------------------------
    def add_buttons(self, ok_text: str) -> QPushButton:
        key = getattr(self, "_defaults_key", None)
        if key:
            self.reuse_options = QCheckBox(i18n.tr("defaults.reuse"))
            self.reuse_options.setChecked(tool_defaults.is_enabled(key))
            self.reuse_options.setToolTip(i18n.tr("defaults.hint"))
            self._body.addWidget(self.reuse_options)
        footer = QHBoxLayout()
        footer.setSpacing(9)
        footer.addStretch(1)

        cancel = QPushButton(i18n.tr("btn.cancel"))
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        ok = QPushButton(ok_text)
        ok.setProperty("accent", True)
        ok.setAutoDefault(True)
        ok.setDefault(True)
        ok.clicked.connect(self._accept_clicked)
        footer.addWidget(ok)

        self._body.addLayout(footer)
        self._ok_button = ok
        return ok

    def _accept_clicked(self) -> None:
        self.accept()

    def save_defaults(self) -> None:
        pass

    def configure_defaults(self, key: str) -> dict | None:
        self._defaults_key = key
        return tool_defaults.load_options(key)

    def remember_options(self, options: dict) -> None:
        tool_defaults.remember(self._defaults_key, options, self.reuse_options.isChecked())

    def exec_with_defaults(self):
        key = getattr(self, "_defaults_key", None)
        if key and tool_defaults.can_reuse(key):
            self._accept_clicked()
            return self.result()
        return self.exec()
