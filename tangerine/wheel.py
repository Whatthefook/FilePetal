"""The radial conversion/tools wheel (v1.7.0 HUD language).

Geometry and behaviour follow ``docs/PLAN-V1.7.0.md`` §1.1-1.2:

* a 460x460 frameless window; petals are annular wedges between ``R_IN`` and
  ``R_OUT`` with 8 degree gaps and rounded corners;
* every surface is *material*: the blurred desktop behind the wheel plus the
  theme ``wash`` (see :class:`~tangerine.hud.HudBackdrop`), the halo is the
  translucent ``halo`` token and the hub uses the ``hub`` token;
* conversion petals show only the upper-case format name; tool petals show a
  vector line icon plus a small upper-case label;
* hover paints the petal flat ``ACCENT`` with dark content (120 ms animated),
  the hub grows a capsule with the hovered label that slides in from that
  petal (140 ms) and fades out;
* appearance is a staggered 260 ms bloom (radius 0.6R → R with a slight
  overshoot), the farewell shrinks to 0.94 with a fade.

The wheel also keeps the hardened drag-and-drop behaviour (copy-only drags,
highlight sound with a one-way disable, :meth:`file_paths`, :meth:`reset`)
and adds keyboard operation (:meth:`set_keyboard_mode`): arrows rotate the
hover with wrap-around, Enter activates and Escape hides.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QUrl,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import i18n, paths as app_paths, settings, theme
from .hud import HudBackdrop
from .icons import icon_for, paint_icon  # noqa: F401 (icon_for is a re-export)

log = logging.getLogger("tangerine")

# -- geometry (compact ~300x320 window at standard DPI) ---------------------
EXTENT = 155.0
R_OUT = 142.0
R_IN = 84.0
BAND = R_OUT - R_IN
HALO_R = 153.0
HUB_R = 80.0
GAP_DEG = 6.0
CORNER_R = 0.24 * BAND

# -- motion ----------------------------------------------------------------
APPEAR_MS = 190.0            # petal bloom (total ≈ APPEAR_MS + stagger·(n-1))
APPEAR_STAGGER_MS = 16.0
APPEAR_SCALE = 0.6           # petals start at 0.6R
DEPART_MS = 160.0
DEPART_SCALE = 0.94
HOVER_MS = 120.0
HOVER_LIFT = 3.0
CAPSULE_MS = 140.0
CAPSULE_FADE_MS = 100.0
CAPSULE_H = 22.0
CAPSULE_MIN_W = 68.0
CAPSULE_SLIDE = 26.0
HUB_VEIL = 0.45             # hub token alpha share: the disc stays frosted

ICON_SIZE = 20.0
ICON_LABEL_GAP = 2.0
TOOL_LABEL_SIZE = 9
CONVERT_LABEL_SIZE = 15

HOVER_INK = "#2B1608"


@dataclass
class FanItem:
    """One petal: ``kind`` is ``"conversion"`` or ``"tool"``."""

    key: str
    label: str
    icon: str = ""
    kind: str = "conversion"


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def _ease_out(value: float) -> float:
    value = _clamp01(value)
    return 1.0 - (1.0 - value) ** 3


def _ease_out_back(value: float, strength: float = 0.35) -> float:
    """Ease-out with a subtle overshoot (petal bloom)."""
    value = _clamp01(value)
    delta = value - 1.0
    return 1.0 + (strength + 1.0) * delta**3 + strength * delta**2


def _mix(first: QColor, second: QColor, amount: float) -> QColor:
    amount = _clamp01(amount)
    return QColor(
        round(first.red() + (second.red() - first.red()) * amount),
        round(first.green() + (second.green() - first.green()) * amount),
        round(first.blue() + (second.blue() - first.blue()) * amount),
        round(first.alpha() + (second.alpha() - first.alpha()) * amount),
    )


def _wedge_path(
    r_in: float,
    r_out: float,
    a1: float,
    a2: float,
    corner_r: float,
) -> QPainterPath:
    """Annular wedge with rounded corners, ready to clip and fill.

    Angles are degrees in the screen convention of :func:`math.atan2` (0° at
    3 o'clock, growing clockwise).  The marching path is inset by *corner_r*
    so that stroking it with a ``2 * corner_r`` round-capped/round-joined pen
    (and filling it) rounds every corner with that radius.  The two sides are
    inset per radius (``asin(corner / radius)``) so the stroked outline lands
    exactly on the radial gap edges at every radius.
    """
    corner = max(1.5, float(corner_r))
    inner = float(r_in) + corner
    outer = float(r_out) - corner
    if outer - inner < 2.0 * corner:  # degenerate band: keep a slim wedge
        middle = (float(r_in) + float(r_out)) / 2.0
        inner, outer = middle - corner, middle + corner
    inset_out = math.degrees(math.asin(min(1.0, corner / max(1.0, outer))))
    inset_in = math.degrees(math.asin(min(1.0, corner / max(1.0, inner))))
    span = float(a2) - float(a1)
    if span <= inset_out + inset_in + 1.0 or span <= 2.0 * inset_in + 1.0:
        inset_out = inset_in = 0.0
    start_out = a1 + inset_out
    end_out = a2 - inset_out
    start_in = a1 + inset_in
    end_in = a2 - inset_in
    outer_rect = QRectF(-outer, -outer, 2.0 * outer, 2.0 * outer)
    inner_rect = QRectF(-inner, -inner, 2.0 * inner, 2.0 * inner)
    # Qt arcs measure counter-clockwise from 3 o'clock; screen angles flip.
    marching = QPainterPath()
    marching.arcMoveTo(outer_rect, -start_out)
    marching.arcTo(outer_rect, -start_out, -(end_out - start_out))
    marching.lineTo(
        inner * math.cos(math.radians(end_in)),
        inner * math.sin(math.radians(end_in)),
    )
    marching.arcTo(inner_rect, -end_in, end_in - start_in)
    marching.closeSubpath()
    stroker = QPainterPathStroker()
    stroker.setWidth(2.0 * corner)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return stroker.createStroke(marching).united(marching)


class TangerineWheel(QWidget):
    activated = Signal(list, str)
    closed = Signal()

    EXTENT = EXTENT
    R_OUT = R_OUT
    R_IN = R_IN

    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(int(EXTENT * 2), int(EXTENT * 2))

        self._items: list[FanItem] = []
        self._file_paths: list[str] = []
        # Compatibility record of the last drop context (title, subtitle); the
        # hub no longer paints it, `set_prompt` keeps it for older callers.
        self._prompt: tuple[str, str] = ("", "")
        self._mode = "conversion"
        self._factory: Callable[[list[str]], Sequence[FanItem]] | None = None
        self._sound = None
        self._sound_disabled = False
        self._dark = theme.is_dark()

        self._backdrop = HudBackdrop()
        self._material: QImage | None = None
        self._capture_rect = self.frameGeometry()
        self._capture_stamp = 0.0

        self._hover = -1
        self._hover_values: dict[int, float] = {}
        self._capsule_t = 0.0
        self._capsule_label = ""
        self._capsule_dir = QPointF(0.0, -1.0)
        self._appear_ms = 0.0
        self._appear_total = 0.0
        self._depart = 0.0
        self._depart_token = 0
        self._keyboard_mode = False

        self._appear_anim: QVariantAnimation | None = None
        self._hover_anim: QVariantAnimation | None = None
        self._capsule_anim: QVariantAnimation | None = None
        self._depart_anim: QVariantAnimation | None = None

        self._convert_font: QFont | None = None
        self._tool_font: QFont | None = None
        self._capsule_font: QFont | None = None

        theme.add_theme_listener(self._on_theme_change)
        self.destroyed.connect(lambda *_args: theme.remove_theme_listener(self._on_theme_change))

    # -- public API ----------------------------------------------------

    def set_factory(self, factory: Callable[[list[str]], Sequence[FanItem]]) -> None:
        self._factory = factory

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_items(self, items: Sequence[FanItem], animate: bool = False) -> None:
        """Replace the petals; *animate* replays the bloom (mode switches)."""
        previous = len(self._items)
        self._items = list(items)
        self._hover = -1
        self._hover_values = {index: 0.0 for index in range(len(self._items))}
        self._capsule_t = 0.0
        self._capsule_label = ""
        if animate or (self.isVisible() and len(self._items) != previous):
            self.play_appearance()
        elif self._appear_total <= 0.0:
            self._appear_ms = 0.0
        self.update()

    def set_prompt(self, main: str, sub: str = "") -> None:
        """Compatibility no-op: the hub only shows the hovered petal label.

        The subtitle is still recorded so drag hovers keep the historical
        ``_prompt`` contract alive for older callers.
        """
        self._prompt = (str(main), str(sub))

    def place_beside_cursor(self, cursor_pos: QPoint) -> None:
        """Position the compact dial next to the cursor on the roomier side, clamped to the active monitor."""
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        w = self.width()
        h = self.height()
        gap = 20
        if screen is not None:
            area = screen.availableGeometry()
            space_right = area.right() - cursor_pos.x()
            space_left = cursor_pos.x() - area.left()
            if space_right >= w + gap:
                x = cursor_pos.x() + gap
            elif space_left >= w + gap:
                x = cursor_pos.x() - w - gap
            elif space_right >= space_left:
                x = cursor_pos.x() + gap
            else:
                x = cursor_pos.x() - w - gap
            y = cursor_pos.y() - h // 2
            x = max(area.left(), min(x, area.right() - w + 1))
            y = max(area.top(), min(y, area.bottom() - h + 1))
        else:
            x = cursor_pos.x() + gap
            y = cursor_pos.y() - h // 2
        self.move(int(x), int(y))
        self._capture_backdrop()

    def center_at(self, global_pos: QPoint) -> None:
        self.place_beside_cursor(global_pos)

    def update_cursor(self, global_pos: QPoint) -> None:
        if self._keyboard_mode:
            return
        local = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local):
            return
        dx = local.x() - self.width() / 2.0
        dy = local.y() - self.height() / 2.0
        if math.hypot(dx, dy) < HUB_R - 2.0:
            self._set_hover_index(-1)
            return
        idx = self.hit_test(QPointF(local))
        if idx >= 0:
            self._set_hover_index(idx)

    def is_keyboard_mode(self) -> bool:
        return self._keyboard_mode

    def file_paths(self) -> list[str]:
        return list(self._file_paths)

    def set_files(self, files: Sequence[str] | None) -> None:
        """Record the files the wheel acts on (keyboard/selection triggers).

        Real drag-and-drop overwrites this from :meth:`dragEnterEvent`.
        """
        self._file_paths = [str(path) for path in (files or [])]

    def reset(self) -> None:
        self._stop_animations()
        self._items = []
        self._file_paths = []
        self._hover = -1
        self._hover_values = {}
        self._capsule_t = 0.0
        self._capsule_label = ""
        self._appear_ms = 0.0
        self._appear_total = 0.0
        self._depart = 0.0
        self.update()

    def set_keyboard_mode(self, flag: bool) -> None:
        """Keyboard mode takes focus (drag mode never steals it)."""
        flag = bool(flag)
        if flag == self._keyboard_mode:
            return
        self._keyboard_mode = flag
        visible = self.isVisible()
        if flag:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
            self.show()
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.clearFocus()
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            if visible:
                self.show()

    # -- motion ---------------------------------------------------------

    def play_appearance(self) -> None:
        """Staggered bloom: petals 0.6R → R with a fade (plan 1.2)."""
        self._stop_animations()
        self._depart_token += 1
        self._depart = 0.0
        self._hover = -1
        self._hover_values = {index: 0.0 for index in range(len(self._items))}
        self._capsule_t = 0.0
        self._capsule_label = ""
        if not self._items:
            return
        self._appear_total = APPEAR_MS + APPEAR_STAGGER_MS * (len(self._items) - 1)
        self._appear_ms = 0.0
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(float(self._appear_total))
        animation.setDuration(int(round(self._appear_total)))
        animation.setEasingCurve(QEasingCurve.Type.Linear)
        animation.valueChanged.connect(self._on_appear_tick)
        self._appear_anim = animation
        animation.start()

    def dismiss(self) -> None:
        """Farewell (0.94 scale + fade) followed by hide + reset."""
        if not self.isVisible():
            return
        self._depart_token += 1
        token = self._depart_token

        def finished() -> None:
            if token == self._depart_token:
                self.hide()
                self.reset()

        self._animate_depart(finished)

    def cancel_dismiss(self) -> None:
        """Abort a farewell in flight so the wheel stays for this gesture."""
        self._depart_token += 1
        self._depart = 0.0
        if self._depart_anim is not None:
            self._depart_anim.stop()
        self.update()

    def _close(self) -> None:
        """User-dismissed wheel: clear state and announce the close."""
        self.reset()
        self.hide()
        self.closed.emit()

    # -- interaction ---------------------------------------------------

    def hit_test(self, local: QPointF) -> int:
        count = len(self._items)
        if count == 0:
            return -1
        if count == 1 and self._items[0].kind == "info":
            return -1
        dx = local.x() - self.width() / 2.0
        dy = local.y() - self.height() / 2.0
        radius = math.hypot(dx, dy)
        if radius < HUB_R - 2.0 or radius > R_OUT + 16.0:
            return -1
        angle = math.degrees(math.atan2(dy, dx))
        step = 360.0 / count
        for index in range(count):
            target = -90.0 + (index + 0.5) * step
            difference = (angle - target + 540.0) % 360.0 - 180.0
            if abs(difference) <= step / 2.0:
                return index
        return -1

    def is_over_petal(self, local: QPointF) -> bool:
        """True when *local* is physically over an active petal (not in a gap or hub)."""
        count = len(self._items)
        if count == 0:
            return False
        if count == 1 and self._items[0].kind == "info":
            return False
        dx = local.x() - self.width() / 2.0
        dy = local.y() - self.height() / 2.0
        radius = math.hypot(dx, dy)
        if radius < R_IN - 4.0 or radius > R_OUT + 8.0:
            return False
        angle = math.degrees(math.atan2(dy, dx))
        step = 360.0 / count
        half = step / 2.0 - GAP_DEG * 0.35
        for index in range(count):
            target = -90.0 + (index + 0.5) * step
            difference = (angle - target + 540.0) % 360.0 - 180.0
            if abs(difference) <= half:
                return True
        return False

    def _set_hover_index(self, index: int) -> None:
        if index == self._hover:
            return
        self._hover = index
        self._animate_hover()
        count = len(self._items)
        if 0 <= index < count:
            item = self._items[index]
            self._capsule_label = item.label
            step = 360.0 / count
            radians = math.radians(-90.0 + (index + 0.5) * step)
            self._capsule_dir = QPointF(math.cos(radians), math.sin(radians))
            self._animate_capsule(1.0)
            self._play_highlight()
        else:
            self._animate_capsule(0.0)
        self.update()

    def _play_highlight(self) -> None:
        if self._sound_disabled or not settings.get("soundsAndHapticsEnabled"):
            return
        try:
            if self._sound is None:
                from PySide6.QtMultimedia import QSoundEffect

                self._sound = QSoundEffect(self)
                self._sound.setSource(QUrl.fromLocalFile(str(app_paths.highlight_sound())))
                self._sound.setVolume(0.55)
            self._sound.play()
        except Exception:
            self._sound_disabled = True
            log.warning("Highlight sound disabled", exc_info=True)

    def _accept_copy(self, event) -> bool:
        if event.possibleActions() & Qt.CopyAction:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return True
        event.ignore()
        return False

    def _merge_files(self, payload: list[str]) -> list[str]:
        """Keep the full selection when the OLE payload collapsed it."""
        known = self._file_paths
        if known and len(payload) < len(known) and set(payload) <= set(known):
            return list(known)
        return payload

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        files: list[str] = []
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    files.append(url.toLocalFile())
        if not files:
            event.ignore()
            return
        files = self._merge_files(files)
        files_changed = (
            set(files) != set(self._file_paths)
            or len(files) != len(self._file_paths)
            or not self._items
        )
        if files_changed:
            self._file_paths = files
            if self._factory is not None:
                self.set_items(self._factory(files), animate=False)
        else:
            self._file_paths = files
        subtitle = (
            Path(files[0]).name
            if len(files) == 1
            else i18n.tr("wheel.files_count", n=len(files))
        )
        self._prompt = (self._prompt[0], subtitle)
        self._accept_copy(event)
        idx = self.hit_test(event.position())
        if idx >= 0:
            self._set_hover_index(idx)

    def dragMoveEvent(self, event) -> None:
        idx = self.hit_test(event.position())
        if idx >= 0:
            self._set_hover_index(idx)
        else:
            dx = event.position().x() - self.width() / 2.0
            dy = event.position().y() - self.height() / 2.0
            if math.hypot(dx, dy) < HUB_R - 2.0:
                self._set_hover_index(-1)
        self._accept_copy(event)

    def dragLeaveEvent(self, event) -> None:
        pass

    def dropEvent(self, event) -> None:
        if not self._accept_copy(event):
            return
        local = event.position()
        index = self.hit_test(local)
        files = list(self._file_paths)
        if 0 <= index < len(self._items) and self.is_over_petal(local):
            item = self._items[index]
            if item.kind == "info":
                self.reset()
                self.hide()
                return
            key = item.key
            self.reset()
            self.hide()
            self.activated.emit(files, key)
        else:
            self.reset()
            self.hide()

    def mouseMoveEvent(self, event) -> None:
        idx = self.hit_test(event.position())
        if idx >= 0:
            self._set_hover_index(idx)
        else:
            dx = event.position().x() - self.width() / 2.0
            dy = event.position().y() - self.height() / 2.0
            if math.hypot(dx, dy) < HUB_R - 2.0:
                self._set_hover_index(-1)

    def leaveEvent(self, event) -> None:
        if self._file_paths or self._keyboard_mode:
            return
        self._set_hover_index(-1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.hit_test(event.position())
            if 0 <= index < len(self._items):
                key = self._items[index].key
                files = list(self._file_paths)
                self.reset()
                self.hide()
                self.activated.emit(files, key)
            else:
                self._close()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        """Scroll over the wheel moves the hover like the arrow keys."""
        count = len(self._items)
        if count:
            delta = event.angleDelta().y()
            if delta:
                step = 1 if delta < 0 else -1
                if 0 <= self._hover < count:
                    self._set_hover_index((self._hover + step) % count)
                else:
                    self._set_hover_index(0 if step > 0 else count - 1)
            event.accept()
            return
        super().wheelEvent(event)

    def navigate_step(self, step: int) -> None:
        count = len(self._items)
        if count == 0:
            return
        if 0 <= self._hover < count:
            self._set_hover_index((self._hover + step) % count)
        else:
            self._set_hover_index(0 if step > 0 else count - 1)

    def activate_current(self) -> None:
        count = len(self._items)
        if 0 <= self._hover < count:
            key_name = self._items[self._hover].key
            files = list(self._file_paths)
            self.reset()
            self.hide()
            self.activated.emit(files, key_name)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close()
            event.accept()
            return
        count = len(self._items)
        if count == 0:
            super().keyPressEvent(event)
            return
        step = -1 if key in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if 0 <= self._hover < count:
                self._set_hover_index((self._hover + step) % count)
            else:  # first arrow press: land on the first (or last) petal
                self._set_hover_index(0 if step > 0 else count - 1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if 0 <= self._hover < count:
                key_name = self._items[self._hover].key
                files = list(self._file_paths)
                self.reset()
                self.hide()
                self.activated.emit(files, key_name)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    # -- animations -----------------------------------------------------

    def _stop_animations(self) -> None:
        for animation in (
            self._appear_anim,
            self._hover_anim,
            self._capsule_anim,
            self._depart_anim,
        ):
            if animation is not None:
                animation.stop()

    def _on_appear_tick(self, value) -> None:
        self._appear_ms = float(value)
        self.update()

    def _animate_hover(self) -> None:
        if self._hover_anim is not None:
            self._hover_anim.stop()
            self._hover_anim = None
        count = len(self._items)
        start = {index: self._hover_value(index) for index in range(count)}
        target = {index: (1.0 if index == self._hover else 0.0) for index in range(count)}
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(int(HOVER_MS))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def tick(value) -> None:
            factor = float(value)
            self._hover_values = {
                index: start[index] + (target[index] - start[index]) * factor
                for index in start
            }
            self.update()

        animation.valueChanged.connect(tick)
        animation.finished.connect(lambda: self._hover_values.update(target))
        self._hover_anim = animation
        animation.start()

    def _animate_capsule(self, target: float) -> None:
        if self._capsule_anim is not None:
            self._capsule_anim.stop()
            self._capsule_anim = None
        animation = QVariantAnimation(self)
        animation.setStartValue(float(self._capsule_t))
        animation.setEndValue(float(target))
        duration = CAPSULE_MS if target > self._capsule_t else CAPSULE_FADE_MS
        animation.setDuration(int(duration))
        animation.setEasingCurve(QEasingCurve.Type.Linear)
        animation.valueChanged.connect(self._on_capsule_tick)
        self._capsule_anim = animation
        animation.start()

    def _on_capsule_tick(self, value) -> None:
        self._capsule_t = _clamp01(float(value))
        self.update()

    def _animate_depart(self, finished) -> None:
        animation = QVariantAnimation(self)
        animation.setStartValue(float(self._depart))
        animation.setEndValue(1.0)
        animation.setDuration(int(DEPART_MS))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(self._on_depart_tick)
        animation.finished.connect(finished)
        self._depart_anim = animation
        animation.start()

    def _on_depart_tick(self, value) -> None:
        self._depart = _clamp01(float(value))
        self.update()

    # -- appearance hooks ------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._dark = theme.is_dark()
        self._material = None
        self._capture_backdrop()
        if self._items and self._appear_total <= 0.0:
            self.play_appearance()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._capture_backdrop()

    def _capture_backdrop(self) -> None:
        """Re-grab only when the wheel moved or the throttle expired.

        Mirrors :class:`HudBackdrop`'s own throttle so the material composite
        is not rebuilt for every move event during a drag.
        """
        rect = self.frameGeometry()
        now = time.monotonic()
        if rect == self._capture_rect and (now - self._capture_stamp) < 0.25:
            return
        self._capture_rect = rect
        self._capture_stamp = now
        self._material = None
        self._backdrop.capture(rect)

    def _on_theme_change(self, dark: bool) -> None:
        self._dark = bool(dark)
        self._material = None
        self.update()

    # -- painting --------------------------------------------------------

    def _paint_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, float(self.width()), float(self.height()))

    def _material_image(self) -> QImage | None:
        """Cache of "blurred desktop + theme wash" for the petals and hub."""
        if self._material is not None:
            return self._material
        ratio = float(self.devicePixelRatioF() or 1.0)
        image = QImage(
            max(2, int(round(self.width() * ratio))),
            max(2, int(round(self.height() * ratio))),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        if image.isNull():
            return None
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        wash = theme.qcolor(theme.hud(self._dark)["wash"])
        self._backdrop.paint(painter, self._paint_rect(), wash, 0.0)
        painter.end()
        self._material = image
        return image

    def _appear_progress(self, index: int) -> float:
        if self._appear_total <= 0.0:
            return 1.0
        local = (self._appear_ms - index * APPEAR_STAGGER_MS) / APPEAR_MS
        return _clamp01(local)

    def _global_appear(self) -> float:
        if self._appear_total <= 0.0:
            return 1.0
        return _clamp01(self._appear_ms / APPEAR_MS)

    def _hover_value(self, index: int) -> float:
        return _clamp01(float(self._hover_values.get(index, 0.0)))

    def _fonts(self) -> tuple[QFont, QFont, QFont]:
        if self._convert_font is None:
            convert = QFont(self.font())
            convert.setPixelSize(CONVERT_LABEL_SIZE)
            convert.setWeight(QFont.Weight.Bold)
            convert.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108.0)
            self._convert_font = convert
        if self._tool_font is None:
            tool = QFont(self.font())
            tool.setPixelSize(TOOL_LABEL_SIZE)
            tool.setWeight(QFont.Weight.DemiBold)
            tool.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 105.0)
            self._tool_font = tool
        if self._capsule_font is None:
            capsule = QFont(self.font())
            capsule.setPixelSize(10)
            capsule.setWeight(QFont.Weight.Bold)
            capsule.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108.0)
            self._capsule_font = capsule
        return self._convert_font, self._tool_font, self._capsule_font

    def paintEvent(self, event) -> None:
        count = len(self._items)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        tokens = theme.hud(self._dark)
        self._paint_halo(painter, center, tokens)
        if count == 0:
            self._paint_hub(painter, center, tokens)
            painter.end()
            return
        if count == 1 and self._items[0].kind == "info":
            self._paint_hub(painter, center, tokens)
            self._paint_info_card(painter, center, self._items[0].label, tokens)
            painter.end()
            return
        step = 360.0 / count
        for index, item in enumerate(self._items):
            self._paint_petal(painter, center, index, item, step, tokens)
        self._paint_hub(painter, center, tokens)
        self._paint_capsule(painter, center, tokens)
        painter.end()

    def _paint_halo(self, painter: QPainter, center: QPointF, tokens: dict) -> None:
        alpha = _ease_out(self._global_appear()) * (1.0 - self._depart)
        if alpha <= 0.02:
            return
        base = theme.qcolor(tokens["halo"])
        fade = QColor(base)
        fade.setAlpha(0)
        gradient = QRadialGradient(center, HALO_R)
        gradient.setColorAt(0.0, base)
        gradient.setColorAt(0.86, base)
        gradient.setColorAt(1.0, fade)
        painter.save()
        painter.setOpacity(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, HALO_R, HALO_R)
        painter.restore()

    def _paint_petal(
        self,
        painter: QPainter,
        center: QPointF,
        index: int,
        item: FanItem,
        step: float,
        tokens: dict,
    ) -> None:
        progress = self._appear_progress(index)
        if progress <= 0.0:
            return
        grow = _ease_out_back(progress)
        scale = (APPEAR_SCALE + (1.0 - APPEAR_SCALE) * grow) * (
            1.0 - (1.0 - DEPART_SCALE) * self._depart
        )
        alpha = min(1.0, progress * 1.6) * (1.0 - self._depart)
        if alpha <= 0.02:
            return
        hover = self._hover_value(index)
        angle = -90.0 + (index + 0.5) * step
        half = step / 2.0 - GAP_DEG / 2.0
        lift = HOVER_LIFT * hover
        radius_in = R_IN * scale + lift
        radius_out = R_OUT * scale + lift
        corner = max(6.0, CORNER_R * scale)
        path = _wedge_path(radius_in, radius_out, angle - half, angle + half, corner)
        path.translate(center.x(), center.y())

        painter.save()
        painter.setOpacity(alpha)
        painter.setClipPath(path)
        material = self._material_image()
        if material is not None:
            painter.drawImage(self._paint_rect(), material)
        if hover > 0.01:
            painter.setOpacity(alpha * hover)
            painter.fillPath(path, theme.qcolor(theme.ACCENT))
        painter.restore()

        base_ink = theme.qcolor(tokens["icon"])
        ink = _mix(base_ink, theme.qcolor(HOVER_INK), hover)
        painter.save()
        painter.setOpacity(alpha)
        if item.kind in ("tool", "action"):
            self._paint_tool_content(
                painter, center, angle, radius_in, radius_out, item, ink, step, scale
            )
        else:
            self._paint_conversion_content(
                painter, center, angle, radius_in, radius_out, item, ink, step, scale
            )
        painter.restore()

    def _radial_point(
        self, center: QPointF, angle: float, radius: float
    ) -> QPointF:
        radians = math.radians(angle)
        return QPointF(
            center.x() + math.cos(radians) * radius,
            center.y() + math.sin(radians) * radius,
        )

    @staticmethod
    def _chord(radius: float, half_angle: float) -> float:
        return 2.0 * radius * math.sin(math.radians(max(0.0, half_angle)))

    @staticmethod
    def _scaled_font(font: QFont, factor: float) -> QFont:
        """A copy of *font* at *factor* size (petal bloom zoom)."""
        if abs(factor - 1.0) < 0.02:
            return font
        scaled = QFont(font)
        scaled.setPixelSize(max(6, int(round(font.pixelSize() * factor))))
        return scaled

    def _paint_conversion_content(
        self,
        painter: QPainter,
        center: QPointF,
        angle: float,
        radius_in: float,
        radius_out: float,
        item: FanItem,
        ink: QColor,
        step: float,
        scale: float = 1.0,
    ) -> None:
        font, _, _ = self._fonts()
        font = self._scaled_font(font, max(0.62, min(1.0, scale)))
        radius = radius_in + (radius_out - radius_in) * 0.52
        point = self._radial_point(center, angle, radius)
        half = step / 2.0 - GAP_DEG / 2.0
        width = max(24.0, self._chord(radius, half) * 0.92)
        line = max(18.0, font.pixelSize() * 1.35)
        painter.setFont(font)
        painter.setPen(ink)
        painter.drawText(
            QRectF(point.x() - width / 2.0, point.y() - line / 2.0, width, line),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            item.label.upper(),
        )

    def _paint_tool_content(
        self,
        painter: QPainter,
        center: QPointF,
        angle: float,
        radius_in: float,
        radius_out: float,
        item: FanItem,
        ink: QColor,
        step: float,
        scale: float = 1.0,
    ) -> None:
        _, font, _ = self._fonts()
        factor = max(0.55, min(1.0, scale))
        half = step / 2.0 - GAP_DEG / 2.0
        anchor_radius = (radius_in + radius_out) / 2.0
        anchor = self._radial_point(center, angle, anchor_radius)
        icon_size = ICON_SIZE * factor
        width = max(24.0, self._chord(anchor_radius, half) * 0.86)
        label_font = self._scaled_font(font, factor)
        text = item.label.upper()
        metrics = QFontMetricsF(label_font)
        lines = self._wrap(metrics, text, width, 2)
        widest = max(metrics.horizontalAdvance(line) for line in lines)
        if widest > width and label_font.pixelSize() > 7:  # one shrink step, then wrap
            label_font = self._scaled_font(label_font, max(0.62, width / widest))
            metrics = QFontMetricsF(label_font)
            lines = self._wrap(metrics, text, width, 2)
        line_height = max(11.0, label_font.pixelSize() * 1.25)
        block = icon_size + ICON_LABEL_GAP + line_height * len(lines)
        top = anchor.y() - block / 2.0
        paint_icon(
            painter,
            item.key,
            QRectF(
                anchor.x() - icon_size / 2.0,
                top,
                icon_size,
                icon_size,
            ),
            ink,
            2.0,
        )
        painter.setFont(label_font)
        painter.setPen(ink)
        label_top = top + icon_size + ICON_LABEL_GAP
        for index, line in enumerate(lines):
            painter.drawText(
                QRectF(
                    anchor.x() - width / 2.0,
                    label_top + index * line_height,
                    width,
                    line_height,
                ),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                line,
            )

    @staticmethod
    def _wrap(metrics: QFontMetricsF, text: str, width: float, limit: int) -> list[str]:
        words = str(text).split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if metrics.horizontalAdvance(candidate) <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        if len(lines) > limit:
            lines = lines[:limit]
            lines[-1] = lines[-1] + "\u2026"
        return lines

    def _paint_info_card(self, painter: QPainter, center: QPointF, text: str, tokens: dict) -> None:
        painter.save()
        card_w = min(float(self.width() - 20), max(170.0, HUB_R * 2.1))
        card_h = 64.0
        rect = QRectF(center.x() - card_w / 2.0, center.y() - card_h / 2.0, card_w, card_h)

        painter.setPen(QPen(QColor(255, 255, 255, 45 if self._dark else 130), 1.0))
        painter.setBrush(QColor(0, 0, 0, 40 if self._dark else 15))
        painter.drawRoundedRect(rect, 10.0, 10.0)

        # Info icon
        icon_rect = QRectF(rect.center().x() - 9.0, rect.top() + 7.0, 18.0, 18.0)
        painter.setPen(QPen(theme.qcolor(theme.ACCENT), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(icon_rect)
        painter.drawText(icon_rect, int(Qt.AlignmentFlag.AlignCenter), "i")

        # Message text
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(theme.qcolor(tokens["icon"]))
        msg_rect = QRectF(rect.left() + 6, rect.top() + 27, rect.width() - 12, 18)
        painter.drawText(msg_rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), text)

        # Subtitle hint
        sub_font = QFont(self.font())
        sub_font.setPixelSize(9)
        painter.setFont(sub_font)
        hint_color = theme.qcolor(tokens["icon"])
        hint_color.setAlpha(170)
        painter.setPen(hint_color)
        sub_rect = QRectF(rect.left() + 6, rect.top() + 45, rect.width() - 12, 16)
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), i18n.tr("wheel.actions_hint"))
        painter.restore()

    def _paint_hub(self, painter: QPainter, center: QPointF, tokens: dict) -> None:
        grow = _ease_out(self._global_appear())
        alpha = grow * (1.0 - self._depart)
        if alpha <= 0.02:
            return
        radius = HUB_R * (0.72 + 0.28 * grow) * (
            1.0 - (1.0 - DEPART_SCALE) * self._depart
        )
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        painter.save()
        painter.setOpacity(alpha)
        painter.setClipPath(path)
        material = self._material_image()
        if material is not None:
            painter.drawImage(self._paint_rect(), material)
        # The hub token is a near-opaque white meant for the capsule; on the
        # disc it is thinned out so the frosted material keeps showing through
        # (the reference hub is translucent, not a white hole).
        veil = theme.qcolor(tokens["hub"])
        veil.setAlpha(int(round(veil.alpha() * HUB_VEIL)))
        painter.fillPath(path, veil)
        painter.restore()

    def _paint_capsule(self, painter: QPainter, center: QPointF, tokens: dict) -> None:
        if self._capsule_t <= 0.01 or not self._capsule_label:
            return
        alpha = min(1.0, self._capsule_t * 1.8) * (1.0 - self._depart)
        if alpha <= 0.02:
            return
        _, _, font = self._fonts()
        text = self._capsule_label.upper()
        width = max(
            CAPSULE_MIN_W,
            QFontMetricsF(font).horizontalAdvance(text) + 30.0,
        )
        offset = _ease_out(self._capsule_t)
        origin = QPointF(
            center.x() + self._capsule_dir.x() * CAPSULE_SLIDE * (1.0 - offset),
            center.y() + self._capsule_dir.y() * CAPSULE_SLIDE * (1.0 - offset),
        )
        rect = QRectF(
            origin.x() - width / 2.0,
            origin.y() - CAPSULE_H / 2.0,
            width,
            CAPSULE_H,
        )
        painter.save()
        painter.setOpacity(alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 60 if self._dark else 26))
        painter.drawRoundedRect(rect.translated(0.0, 2.0), CAPSULE_H / 2.0, CAPSULE_H / 2.0)
        painter.setBrush(theme.qcolor(tokens["hub"]))
        painter.drawRoundedRect(rect, CAPSULE_H / 2.0, CAPSULE_H / 2.0)
        painter.setFont(font)
        painter.setPen(theme.qcolor(tokens["icon"]))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()
