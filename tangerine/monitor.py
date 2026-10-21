"""Drag-modifier monitoring, mirroring the macOS DragGestureMonitor.

The monitor samples public state only: pointer button, modifier keys, the
foreground window and the OLE drag clipboard. No input hooks are installed.
"""

from __future__ import annotations

import ctypes
import math
import os
import threading
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, QPoint, QTimer, Signal

from . import context, dragfiles, selection, settings

user32 = ctypes.windll.user32

VK_LBUTTON = 0x01
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C

MODIFIER_KEYS = {
    "ctrl": (VK_CONTROL,),
    "alt": (VK_MENU,),
    "shift": (VK_SHIFT,),
    "win": (VK_LWIN, VK_RWIN),
}

FOREGROUND_ALLOWLIST = {
    "CabinetWClass",
    "ExploreWClass",
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "XamlExplorerHostIslandWindow",
}

IDLE_INTERVAL_MS = 100
ACTIVE_INTERVAL_MS = 16
MOVEMENT_THRESHOLD = 8.0
DROP_COOLDOWN_S = 0.6
LONG_PRESS_S = 0.7
BUTTON_RELEASE_SAMPLES = 4  # consecutive "up" reads before a release counts
SELECTION_SNAPSHOT_INTERVAL_S = 0.8
SELECTION_SNAPSHOT_MAX_AGE_S = 4.0
STICKY_TIMEOUT_S = 15.0  # a pinned wheel fades out after this much time


def _is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _key_vk(name: str) -> int | None:
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name == "space":
        return 0x20
    if name.startswith("f") and name[1:].isdigit():
        number = int(name[1:])
        if 1 <= number <= 12:
            return 0x70 + number - 1
    return None


class DragMonitor(QObject):
    wheelShown = Signal(object, object, str)
    wheelMoved = Signal(object)
    wheelHidden = Signal()
    wheelRefreshed = Signal(str)
    keyboardTriggered = Signal(object, object, str)
    stickyTriggered = Signal(object, object, str)
    stickyClicked = Signal(object)
    wheelNavigated = Signal(int)
    wheelKeyActivated = Signal()

    _selectionReady = Signal(object, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(IDLE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._button_down = False
        self._button_up_ticks = 0
        self._anchor: QPoint | None = None
        self._visible = False
        self._cooldown_until = 0.0
        self._last_clip_check = 0.0
        self._last_files: list[str] | None = None
        self._mode: str | None = None
        self._enter_down = False
        self._selection_busy = False
        self._press_started = 0.0
        self._long_press_fired = False
        self._touch_mode = False
        self._snapshot: tuple[int, list[str], float] | None = None
        self._snapshot_pending = False
        self._last_snapshot_poll = 0.0
        self._mods_prev: set[str] = set()
        self._esc_down = False
        self._left_down = False
        self._right_down = False
        self._enter_key_down = False
        self._sticky = False
        self._sticky_since = 0.0
        self._toggle_down = False
        self._toggle_pending = False
        self._selectionReady.connect(self.keyboardTriggered)

    def stop(self) -> None:
        self._timer.stop()

    def notify_dropped(self) -> None:
        self._visible = False
        self._mode = None
        self._last_files = None
        self._sticky = False
        self._set_active(False)
        self._cooldown_until = time.monotonic() + DROP_COOLDOWN_S

    def sticky_release(self) -> None:
        """The sticky wheel closed itself (petal click or click outside)."""
        if not self._sticky:
            return
        self._sticky = False
        self._set_active(False)
        self._visible = False

    # -- polling -------------------------------------------------------

    def _cursor(self) -> QPoint:
        from PySide6.QtGui import QCursor
        return QCursor.pos()

    def _set_active(self, active: bool) -> None:
        interval = ACTIVE_INTERVAL_MS if active else IDLE_INTERVAL_MS
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    def _held_modifiers(self) -> set[str]:
        return {
            name
            for name, vks in MODIFIER_KEYS.items()
            if any(_is_down(vk) for vk in vks)
        }

    def _mode_for_current_modifiers(self) -> str | None:
        held = self._held_modifiers()
        if not held:
            return None
        masks = [
            ("actions", settings.parse_mask(settings.get("actionsWheelDragModifierMask", "ctrl+shift"))),
            ("tools", settings.parse_mask(settings.get("toolsWheelDragModifierMask", "alt+shift"))),
            ("conversion", settings.parse_mask(settings.get("conversionWheelDragModifierMask", "shift"))),
        ]
        masks.sort(key=lambda item: len(item[1]) if item[1] else 0, reverse=True)
        for mode_name, mask in masks:
            if mask and mask <= held:
                return mode_name
        return None

    def _drag_files(self) -> list[str] | None:
        now = time.monotonic()
        if now - self._last_clip_check < 0.2:
            return self._last_files
        self._last_clip_check = now
        self._last_files = dragfiles.current_drag_files()
        if self._last_files is None and self._foreground_allows():
            # Some Windows builds do not publish the InShellDragLoop format
            # during a real Explorer drag; with the button held and an
            # allowlisted foreground, a plain CF_HDROP read is the drag
            # payload (same behaviour the app shipped with before the gate).
            self._last_files = dragfiles.current_drag_files(require_drag_loop=False)
        return self._last_files

    def _foreground_allows(self) -> bool:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value in FOREGROUND_ALLOWLIST

    def _maybe_snapshot(self, button: bool, forced: bool = False) -> None:
        """Rolling copy of the Explorer selection.

        Explorer collapses a multi-selection when Shift is held for the
        mousedown (Shift+click semantics), so the OLE payload can carry a
        single file. The snapshot lets the wheel restore the full selection.
        """
        if button or self._snapshot_pending:
            return
        now = time.monotonic()
        if (
            not forced
            and now - self._last_snapshot_poll < SELECTION_SNAPSHOT_INTERVAL_S
        ):
            return
        self._last_snapshot_poll = now
        hwnd = selection.foreground_explorer_hwnd()
        if hwnd is None:
            return
        self._snapshot_pending = True

        def worker() -> None:
            try:
                files = selection.explorer_selection(hwnd)
            except Exception:
                files = []
            finally:
                self._snapshot_pending = False
            if files:
                self._snapshot = (hwnd, files, time.monotonic())

        threading.Thread(
            target=worker, name="tangerine-selection-snapshot", daemon=True
        ).start()

    def _hydrate_from_snapshot(self, files: list[str] | None) -> list[str] | None:
        """Replace a collapsed drag payload with the Explorer selection."""
        snapshot = self._snapshot
        if not snapshot:
            return files
        hwnd, snap_files, stamp = snapshot
        if not snap_files:
            return files
        if time.monotonic() - stamp > SELECTION_SNAPSHOT_MAX_AGE_S:
            return files
        if selection.foreground_explorer_hwnd() != hwnd:
            return files
        if files is None:
            return list(snap_files)
        if len(files) == 1 and len(snap_files) > 1 and set(files) <= set(snap_files):
            return list(snap_files)
        return files

    def _tick(self) -> None:
        down = _is_down(VK_LBUTTON)
        if down:
            self._button_up_ticks = 0
        else:
            self._button_up_ticks += 1
        if (
            not down
            and self._button_down
            and self._button_up_ticks < BUTTON_RELEASE_SAMPLES
        ):
            # Windows 11 reports the left button as up for isolated samples
            # while Explorer services the OLE drag loop; swallowing those
            # keeps the wheel on screen instead of hiding it and re-blooming
            # with the petals emptied a tick later.
            return
        button = down
        self._poll_keyboard(button)
        self._poll_toggle()
        if self._sticky:
            cursor = self._cursor()
            new_press = button and not self._button_down
            self._button_down = button
            if time.monotonic() - self._sticky_since > STICKY_TIMEOUT_S:
                self._sticky = False
                self._set_active(False)
                if self._visible:
                    self._visible = False
                    self.wheelHidden.emit()
                return
            if self._visible and not context.wheel_allowed():
                self._sticky = False
                self._set_active(False)
                self._visible = False
                self._mode = None
                self.wheelHidden.emit()
                return
            if new_press:
                self.stickyClicked.emit(cursor)
            return
        if button and not self._button_down:
            self._button_down = True
            self._anchor = self._cursor()
            self._last_files = None
            self._last_clip_check = 0.0
            self._mode = None
            self._press_started = time.monotonic()
            self._long_press_fired = False
            self._touch_mode = False
            self._set_active(True)
        if not button:
            if self._button_down:
                self._maybe_snapshot(False, forced=True)
                self._button_down = False
                self._button_up_ticks = 0
                self._anchor = None
                self._mode = None
                self._long_press_fired = False
                self._touch_mode = False
                self._set_active(False)
            held = self._held_modifiers()
            if held and held != self._mods_prev:
                self._maybe_snapshot(False, forced=True)
            self._mods_prev = held
            self._maybe_snapshot(False)
            self._esc_down = False
            self._left_down = False
            self._right_down = False
            self._enter_key_down = False
            if self._visible:
                self._visible = False
                self.wheelHidden.emit()
            return

        cursor = self._cursor()
        if self._anchor is None:
            self._anchor = cursor
            return

        if self._visible:
            # Handle keyboard navigation while the wheel is showing during drag
            esc = _is_down(VK_ESCAPE)
            if esc and not self._esc_down:
                self._visible = False
                self._mode = None
                self.wheelHidden.emit()
                self.notify_dropped()
                return
            self._esc_down = esc

            left = _is_down(VK_LEFT) or _is_down(VK_UP)
            if left and not self._left_down:
                self.wheelNavigated.emit(-1)
            self._left_down = left

            right = _is_down(VK_RIGHT) or _is_down(VK_DOWN)
            if right and not self._right_down:
                self.wheelNavigated.emit(1)
            self._right_down = right

            ret = _is_down(VK_RETURN)
            if ret and not self._enter_key_down:
                self.wheelKeyActivated.emit()
                self.notify_dropped()
                return
            self._enter_key_down = ret

            if not context.wheel_allowed():
                self._visible = False
                self._mode = None
                self.wheelHidden.emit()
                return
            self.wheelMoved.emit(cursor)
            mode = self._mode_for_current_modifiers()
            if mode is None and self._touch_mode:
                mode = "conversion"
            # Releasing modifier keys while dragging keeps the current wheel open
            # until mouse release or Escape. Switching modifiers switches modes cleanly.
            if mode is not None and mode != self._mode:
                self._mode = mode
                self.wheelRefreshed.emit(mode)
            return

        if self._maybe_touch_long_press(cursor):
            return

        if time.monotonic() < self._cooldown_until:
            return
        distance = math.hypot(
            cursor.x() - self._anchor.x(), cursor.y() - self._anchor.y()
        )
        if distance < MOVEMENT_THRESHOLD:
            return
        mode = self._mode_for_current_modifiers()
        if mode is None:
            return
        if not context.wheel_allowed():
            return
        files = self._hydrate_from_snapshot(self._drag_files())
        # The OLE drag payload is not readable on every Windows build while
        # a drag is in flight (observed on this Windows 11: neither the
        # InShellDragLoop format nor a plain CF_HDROP read returns anything),
        # and the foreground window is not always an allowlisted Explorer
        # surface mid-drag. The wheel therefore shows as soon as the held
        # gesture matches; its dragEnter handler fills the petals from the
        # drop payload as the pointer enters the wheel window.
        self._mode = mode
        self._visible = True
        self.wheelShown.emit(cursor, files, mode)

    # -- keyboard / touch triggers --------------------------------------

    def _poll_keyboard(self, button: bool) -> None:
        """Shift+Enter with an Explorer selection opens the wheel (plan 1.5)."""
        enter = _is_down(VK_RETURN)
        pressed = enter and not self._enter_down
        self._enter_down = enter
        if not pressed or button or self._button_down or self._selection_busy:
            return
        hwnd = selection.foreground_explorer_hwnd()
        if hwnd is None:
            return
        mode = self._mode_for_current_modifiers()
        if mode is None:
            return
        cursor = self._cursor()
        self._selection_busy = True

        def worker() -> None:
            try:
                files = selection.explorer_selection(hwnd)
            except Exception:
                files = []
            finally:
                self._selection_busy = False
            if files:
                self._selectionReady.emit(cursor, files, mode)

        threading.Thread(
            target=worker, name="tangerine-enter-selection", daemon=True
        ).start()

    def _poll_toggle(self) -> None:
        """Configurable hotkey: open (or pin) a sticky wheel for the gesture."""
        combo = settings.parse_hotkey(settings.get("wheelToggleHotkey", ""))
        if combo is None:
            self._toggle_down = False
            self._toggle_pending = False
            return
        mask, key_name = combo
        vk = _key_vk(key_name)
        if vk is None:
            self._toggle_down = False
            self._toggle_pending = False
            return
        down = _is_down(vk) and mask <= self._held_modifiers()
        if down and not self._toggle_down:
            # Latch the press: a single keystroke must never be dropped just
            # because a COM read happens to be in flight this tick.
            self._toggle_pending = True
        self._toggle_down = down
        if not self._toggle_pending:
            return
        if self._sticky:
            self._toggle_pending = False
            self._sticky = False
            self._set_active(False)
            self._esc_down = False
            self._left_down = False
            self._right_down = False
            self._enter_key_down = False
            if self._visible:
                self._visible = False
                self.wheelHidden.emit()
            return
        if self._visible:
            # Already showing for this gesture: keep it on screen instead of
            # waiting for the keys to be released (the real "hold it" flow).
            self._toggle_pending = False
            self._sticky = True
            self._sticky_since = time.monotonic()
            self._set_active(True)
            return
        if self._selection_busy:
            return
        self._toggle_pending = False
        hwnd = selection.foreground_explorer_hwnd()
        if hwnd is None:
            return
        mode = self._mode_for_current_modifiers() or "conversion"
        cursor = self._cursor()
        self._sticky = True
        self._sticky_since = time.monotonic()
        self._set_active(True)
        self._selection_busy = True

        def worker() -> None:
            try:
                files = selection.explorer_selection(hwnd)
            except Exception:
                files = []
            finally:
                self._selection_busy = False
            if files:
                self._visible = True
                self.stickyTriggered.emit(cursor, files, mode)
            elif self._sticky:
                self._sticky = False
                self._set_active(False)

        threading.Thread(
            target=worker, name="tangerine-sticky-selection", daemon=True
        ).start()

    def _maybe_touch_long_press(self, cursor: QPoint) -> bool:
        """Touch mode: hold a drag for >=700 ms without modifiers → wheel."""
        if self._long_press_fired or self._visible:
            return False
        if not bool(settings.get("touchLongPressEnabled")):
            return False
        if self._held_modifiers():
            return False
        if not context.wheel_allowed():
            return False
        if time.monotonic() < self._cooldown_until:
            return False
        if time.monotonic() - self._press_started < LONG_PRESS_S:
            return False
        files = self._hydrate_from_snapshot(self._drag_files())
        if not files:
            return False
        self._long_press_fired = True
        self._touch_mode = True
        self._mode = "conversion"
        self._visible = True
        self.wheelShown.emit(cursor, files, "conversion")
        return True
