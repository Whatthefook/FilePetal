"""Regression tests for the wheel drag-and-drop path (v1.7.1).

Field case on Windows 11: the monitor shows the wheel before the OLE payload
is readable, so ``dragEnterEvent`` must fill the petals from the mime data and
``dropEvent`` must emit ``activated`` with the dropped files. The monitor's
release debounce relies on ``cancel_dismiss`` keeping the wheel on screen.
"""

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QAbstractAnimation, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from tangerine.wheel import FanItem, TangerineWheel


def _mime(path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def _petal_point(wheel, index: int, count: int) -> QPointF:
    step = 360.0 / count
    radians = math.radians(-90.0 + (index + 0.5) * step)
    radius = (getattr(wheel, 'R_IN', 84.0) + getattr(wheel, 'R_OUT', 142.0)) / 2.0
    center_x, center_y = wheel.width() / 2.0, wheel.height() / 2.0
    return QPointF(
        center_x + radius * math.cos(radians),
        center_y + radius * math.sin(radians),
    )


def _enter(wheel, mime: QMimeData) -> QDragEnterEvent:
    event = QDragEnterEvent(
        QPoint(wheel.width() // 2, wheel.height() // 2),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragEnterEvent(event)
    return event


@pytest.fixture
def wheel(qapp, tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0tangerine-fixture")
    widget = TangerineWheel()
    labels = (("png", "PNG"), ("webp", "WEBP"))
    widget.set_factory(
        lambda files: [FanItem(key, label) for key, label in labels]
    )
    widget.test_file = str(photo)
    yield widget
    widget.hide()
    widget.deleteLater()


def test_drag_enter_fills_petals_and_drop_activates(wheel):
    mime = _mime(wheel.test_file)
    enter = _enter(wheel, mime)
    assert enter.isAccepted()
    assert [Path(path) for path in wheel.file_paths()] == [Path(wheel.test_file)]
    assert [item.key for item in wheel._items] == ["png", "webp"]

    point = _petal_point(wheel, 1, 2)
    move = QDragMoveEvent(
        QPoint(int(point.x()), int(point.y())),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dragMoveEvent(move)
    assert move.isAccepted()
    assert wheel._hover == 1

    captured: list[tuple] = []
    wheel.activated.connect(lambda files, key: captured.append((files, key)))
    drop = QDropEvent(
        point,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dropEvent(drop)

    assert len(captured) == 1
    files, key = captured[0]
    assert [Path(path) for path in files] == [Path(wheel.test_file)]
    assert key == "webp"
    assert wheel.file_paths() == []
    assert wheel._items == []


def test_drop_outside_the_petals_is_a_no_op(wheel):
    mime = _mime(wheel.test_file)
    _enter(wheel, mime)
    captured: list[tuple] = []
    wheel.activated.connect(lambda files, key: captured.append((files, key)))

    center = QPointF(wheel.width() / 2.0, wheel.height() / 2.0)
    drop = QDropEvent(
        center,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel.dropEvent(drop)

    assert captured == []
    assert wheel.file_paths() == []


def test_cancel_dismiss_aborts_the_farewell(wheel, qapp):
    wheel.set_items([FanItem("png", "PNG")])
    wheel.show()
    qapp.processEvents()
    assert wheel.isVisible()

    wheel.dismiss()
    assert wheel._depart_anim is not None
    assert wheel._depart_anim.state() == QAbstractAnimation.State.Running

    wheel.cancel_dismiss()
    assert wheel._depart_anim.state() == QAbstractAnimation.State.Stopped
    assert wheel._depart == 0.0
    assert wheel.isVisible()
