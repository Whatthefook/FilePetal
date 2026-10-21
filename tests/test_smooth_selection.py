"""Tests for smooth, glitch-free petal selection, hit testing, and hover stability."""

import math
import sys
from pathlib import Path
import pytest

if sys.platform != "win32":
    pytest.skip("Explorer drag monitoring is Windows-only", allow_module_level=True)

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QCursor

from tangerine.wheel import FanItem, TangerineWheel, EXTENT, R_IN, R_OUT, HUB_R, GAP_DEG
from tangerine.monitor import DragMonitor


def _mime(path: str) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def _radial_point(wheel: TangerineWheel, angle_deg: float, radius: float) -> QPointF:
    rad = math.radians(angle_deg)
    cx = wheel.width() / 2.0
    cy = wheel.height() / 2.0
    return QPointF(cx + radius * math.cos(rad), cy + radius * math.sin(rad))


def test_smooth_gap_transition_no_reset(qapp):
    """Moving along the arc between adjacent petals transitions seamlessly without dropping to -1."""
    wheel = TangerineWheel()
    wheel.set_items([
        FanItem("png", "PNG"),
        FanItem("webp", "WEBP"),
        FanItem("jpg", "JPG"),
        FanItem("pdf", "PDF"),
    ])
    radius = (R_IN + R_OUT) / 2.0  # Mid-band radius

    # For count=4, step=90°:
    # Petal 0: center = -45°, span = [-90°, 0°]
    # Petal 1: center = +45°, span = [0°, +90°]
    # Boundary is at 0° (right / 3 o'clock)
    # Sweep angle from -20° (Petal 0) through 0° (boundary) to +20° (Petal 1)
    seen_indices = []
    for angle_tenth in range(-200, 200, 5):
        angle = angle_tenth / 10.0
        pt = _radial_point(wheel, angle, radius)
        idx = wheel.hit_test(pt)
        seen_indices.append(idx)

    # All sampled points must map to either Petal 0 or Petal 1. None should drop to -1!
    assert -1 not in seen_indices, "Hit test dropped to -1 while traversing between petals!"
    assert 0 in seen_indices
    assert 1 in seen_indices
    wheel.deleteLater()


def test_hub_and_outer_deadzones(qapp):
    """Inside the hub or far outside the outer ring, hit_test returns -1."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])

    # Center of hub
    center = QPointF(wheel.width() / 2.0, wheel.height() / 2.0)
    assert wheel.hit_test(center) == -1

    # Inner hub radius (< HUB_R - 2.0)
    hub_pt = _radial_point(wheel, 0.0, HUB_R - 10.0)
    assert wheel.hit_test(hub_pt) == -1

    # Far outer point
    outer_pt = _radial_point(wheel, 0.0, R_OUT + 30.0)
    assert wheel.hit_test(outer_pt) == -1
    wheel.deleteLater()


def test_is_over_petal_distinguishes_gaps_for_drop(qapp):
    """is_over_petal returns False on visual gaps and hub, True on petal body."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])
    radius = (R_IN + R_OUT) / 2.0

    # For count=2:
    # Petal 0 center is 0° (East).
    # Petal 1 center is 180° (West).
    # The visual gaps are at -90° (North) and +90° (South).

    # Center of petal 0 (0°)
    pt_petal = _radial_point(wheel, 0.0, radius)
    assert wheel.is_over_petal(pt_petal) is True

    # Exactly in the visual gap between the two petals (-90°)
    pt_gap = _radial_point(wheel, -90.0, radius)
    assert wheel.is_over_petal(pt_gap) is False

    # Center hub
    center = QPointF(wheel.width() / 2.0, wheel.height() / 2.0)
    assert wheel.is_over_petal(center) is False
    wheel.deleteLater()


def test_drop_on_gap_does_not_activate(qapp, tmp_path):
    """Dropping in the visual gap cancels cleanly without activating."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])
    activated_calls = []
    wheel.activated.connect(lambda files, key: activated_calls.append((files, key)))

    dummy_file = tmp_path / "test.png"
    dummy_file.write_text("dummy")
    mime = _mime(str(dummy_file))

    # Drop in the visual gap between petals (for count=2, gap is at -90°)
    gap_pt = _radial_point(wheel, -90.0, (R_IN + R_OUT) / 2.0).toPoint()
    drop_event = QDropEvent(
        gap_pt,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    wheel.dropEvent(drop_event)
    assert len(activated_calls) == 0, "Activation should not occur when dropped in a visual gap"
    wheel.deleteLater()


def test_reentry_at_window_border_preserves_hover(qapp, tmp_path):
    """Entering the window at the outer margin does not clear the currently selected petal."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])

    # Select petal 0
    wheel._set_hover_index(0)
    assert wheel._hover == 0

    dummy_file = tmp_path / "test.png"
    dummy_file.write_text("dummy")
    mime = _mime(str(dummy_file))

    # Drag enter at the very corner of the window (outside the ring, e.g. (5, 5))
    corner_pt = QPoint(5, 5)
    assert wheel.hit_test(QPointF(corner_pt)) == -1

    enter_event = QDragEnterEvent(
        corner_pt,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragEnterEvent(enter_event)
    # Hover must still be 0!
    assert wheel._hover == 0, "Hover should not be wiped to -1 when entering at window border"
    wheel.deleteLater()


def test_keyboard_mode_immune_to_external_mouse_updates(qapp):
    """update_cursor ignores mouse positions when keyboard navigation mode is active."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])
    wheel.set_keyboard_mode(True)

    # User navigates with keyboard to petal 1
    wheel._set_hover_index(1)
    assert wheel._hover == 1

    # External timer or mouse tries to update cursor at petal 0's coordinates (0°)
    pt_petal0 = _radial_point(wheel, 0.0, (R_IN + R_OUT) / 2.0).toPoint()
    global_pt = wheel.mapToGlobal(pt_petal0)
    wheel.update_cursor(global_pt)

    # Hover must remain 1!
    assert wheel._hover == 1, "Keyboard mode selection must not be overridden by mouse update"
    wheel.deleteLater()


def test_hover_animation_cancels_previous(qapp):
    """Rapid hover changes do not leave unstopped animations running."""
    wheel = TangerineWheel()
    wheel.set_items([FanItem("png", "PNG"), FanItem("jpg", "JPG")])

    wheel._set_hover_index(0)
    anim1 = wheel._hover_anim
    assert anim1 is not None

    wheel._set_hover_index(1)
    anim2 = wheel._hover_anim
    assert anim2 is not None
    assert anim2 is not anim1
    assert anim1.state() == anim1.State.Stopped
    wheel.deleteLater()


def test_monitor_cursor_uses_logical_coordinates(qapp):
    """DragMonitor._cursor() returns QCursor.pos() in Qt logical space."""
    monitor = DragMonitor()
    monitor.stop()
    cursor = monitor._cursor()
    assert isinstance(cursor, QPoint)
    assert cursor == QCursor.pos()
