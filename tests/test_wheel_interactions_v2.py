import math
import sys
from pathlib import Path
import pytest

if sys.platform != "win32":
    pytest.skip("Explorer drag monitoring is Windows-only", allow_module_level=True)

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QGuiApplication

from tangerine import actions, catalog, i18n
from tangerine.monitor import DragMonitor
from tangerine.progress import ProgressWindow, WINDOW_WIDTH
from tangerine.toast import ToastNotification, show_toast
from tangerine.wheel import FanItem, TangerineWheel, EXTENT, R_IN, R_OUT


def _mime(path: str) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def _petal_point(wheel, index: int, count: int) -> QPoint:
    step = 360.0 / count
    radians = math.radians(-90.0 + (index + 0.5) * step)
    radius = (R_IN + R_OUT) / 2.0
    center_x, center_y = wheel.width() / 2.0, wheel.height() / 2.0
    return QPoint(
        int(center_x + radius * math.cos(radians)),
        int(center_y + radius * math.sin(radians)),
    )


@pytest.fixture
def sample_files(tmp_path):
    jpg = tmp_path / "photo.jpg"
    jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    pages = tmp_path / "document.pages"
    pages.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
    doc = tmp_path / "legacy.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 20)
    return str(jpg), str(pages), str(doc)


# -- 1. Compact geometry & placement tests ------------------------------------

def test_compact_wheel_dimensions(qapp):
    wheel = TangerineWheel()
    assert wheel.width() == 310
    assert wheel.height() == 310
    assert 300 <= wheel.width() <= 320
    assert 300 <= wheel.height() <= 320
    assert R_IN == 84.0
    assert R_OUT == 142.0
    assert wheel.R_IN == 84.0
    assert wheel.R_OUT == 142.0
    wheel.deleteLater()


def test_wheel_placement_beside_cursor_roomy_side(qapp):
    wheel = TangerineWheel()
    screen = QGuiApplication.primaryScreen()
    area = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    # Place near left edge -> roomier side is right
    cursor_left = QPoint(area.left() + 50, area.center().y())
    wheel.place_beside_cursor(cursor_left)
    assert wheel.x() >= cursor_left.x()

    # Place near right edge -> roomier side is left
    cursor_right = QPoint(area.right() - 50, area.center().y())
    wheel.place_beside_cursor(cursor_right)
    assert wheel.x() + wheel.width() <= cursor_right.x()

    # Stays within monitor work area
    assert wheel.x() >= area.left()
    assert wheel.x() + wheel.width() <= area.right() + 1
    assert wheel.y() >= area.top()
    assert wheel.y() + wheel.height() <= area.bottom() + 1
    wheel.deleteLater()


# -- 2. Stable drop target & hover tests --------------------------------------

def test_stable_drop_target_and_no_flicker_on_reenter(qapp, sample_files):
    jpg, _, _ = sample_files
    wheel = TangerineWheel()
    wheel.set_factory(lambda files: [FanItem("png", "PNG"), FanItem("webp", "WEBP")])

    mime = _mime(jpg)
    enter1 = QDragEnterEvent(
        QPoint(wheel.width() // 2, wheel.height() // 2),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragEnterEvent(enter1)
    assert enter1.isAccepted()
    assert len(wheel._items) == 2

    # Move over petal 0
    petal0_pos = _petal_point(wheel, 0, 2)
    move0 = QDragMoveEvent(
        petal0_pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragMoveEvent(move0)
    assert move0.isAccepted()
    assert wheel._hover == 0

    # Same files re-enter (e.g. repeated OLE dragEnter) -> does NOT reset hover or items
    enter2 = QDragEnterEvent(
        petal0_pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragEnterEvent(enter2)
    assert enter2.isAccepted()
    assert wheel._hover == 0  # Still hovered on petal 0!

    # Move over center hub: hover clears but drop action is STILL accepted across the whole window
    center_x = wheel.width() / 2.0
    center_y = wheel.height() / 2.0
    hub_pos = QPoint(int(center_x), int(center_y))
    move_hub = QDragMoveEvent(
        hub_pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragMoveEvent(move_hub)
    assert move_hub.isAccepted()
    assert wheel._hover == -1

    wheel.deleteLater()


# -- 3. Supported vs Unsupported formats & Actions wheel ----------------------

def test_unsupported_formats_and_actions_availability(sample_files):
    jpg, pages, doc = sample_files

    # Supported JPG offers conversions
    jpg_convs = catalog.conversions_for([Path(jpg)])
    assert len(jpg_convs) > 0
    assert any(c.target_ext == "png" for c in jpg_convs)

    # Genuinely unsupported formats return empty from conversions_for
    pages_convs = catalog.conversions_for([Path(pages)])
    assert pages_convs == []

    doc_convs = catalog.conversions_for([Path(doc)])
    assert doc_convs == []

    # But Actions wheel presents all 6 actions for ANY nonempty selection
    for f in [jpg, pages, doc]:
        acts = catalog.actions_for([Path(f)])
        assert len(acts) == 6
        assert [a.id for a in acts] == [
            "act.share", "act.shelf", "act.copy_ref", "act.move", "act.copy_path", "act.terminal"
        ]


# -- 4. Compact progress card & toast notifications --------------------------

def test_compact_progress_card(qapp):
    assert 340 <= WINDOW_WIDTH <= 380


def test_toast_notification(qapp):
    toast = show_toast("Path copied to clipboard", anchor=QPoint(500, 500))
    assert toast.isVisible()
    assert "Path copied" in toast._message
    toast.close()
    toast.deleteLater()
