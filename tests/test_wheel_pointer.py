"""Sticky-wheel pointer and keyboard interactions (v1.8).

A click on a petal applies it and a click outside (or Escape) closes the
sticky wheel through the new ``closed`` signal; the scroll wheel moves the
hover; and an OLE payload that collapsed a multi-selection never shrinks the
file list already known by the wheel.
"""

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QKeyEvent, QMouseEvent, QWheelEvent

from tangerine.wheel import FanItem, TangerineWheel


def _mime(*paths) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
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


def _mouse_press(wheel, point: QPointF) -> None:
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        point,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    wheel.mousePressEvent(event)


def _wheel_event(delta_y: int) -> QWheelEvent:
    return QWheelEvent(
        QPointF(0.0, 0.0),
        QPointF(0.0, 0.0),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


@pytest.fixture
def wheel(qapp, tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0tangerine-fixture")
    second = tmp_path / "second.jpg"
    second.write_bytes(b"\xff\xd8\xff\xe0tangerine-fixture")
    widget = TangerineWheel()
    labels = (("png", "PNG"), ("webp", "WEBP"))
    widget.set_factory(lambda files: [FanItem(key, label) for key, label in labels])
    widget.test_file = str(photo)
    widget.test_second = str(second)
    yield widget
    widget.hide()
    widget.deleteLater()


def test_collapsed_payload_keeps_the_full_selection(wheel):
    _enter(wheel, _mime(wheel.test_file, wheel.test_second))
    assert [Path(path) for path in wheel.file_paths()] == [
        Path(wheel.test_file),
        Path(wheel.test_second),
    ]

    _enter(wheel, _mime(wheel.test_file))  # OLE collapsed to a single file
    assert [Path(path) for path in wheel.file_paths()] == [
        Path(wheel.test_file),
        Path(wheel.test_second),
    ]


def test_click_on_petal_activates_it(wheel):
    captured: list[tuple] = []
    closed: list[bool] = []
    wheel.activated.connect(lambda files, key: captured.append((files, key)))
    wheel.closed.connect(lambda: closed.append(True))
    _enter(wheel, _mime(wheel.test_file))

    _mouse_press(wheel, _petal_point(wheel, 1, 2))

    assert closed == []
    assert len(captured) == 1
    files, key = captured[0]
    assert [Path(path) for path in files] == [Path(wheel.test_file)]
    assert key == "webp"
    assert wheel.file_paths() == []
    assert wheel._items == []


def test_click_outside_closes_the_wheel(wheel):
    captured: list[tuple] = []
    closed: list[bool] = []
    wheel.activated.connect(lambda files, key: captured.append((files, key)))
    wheel.closed.connect(lambda: closed.append(True))
    _enter(wheel, _mime(wheel.test_file))

    center = QPointF(wheel.width() / 2.0, wheel.height() / 2.0)
    _mouse_press(wheel, center)

    assert captured == []
    assert closed == [True]
    assert wheel._items == []
    assert wheel.file_paths() == []


def test_escape_emits_closed(wheel):
    closed: list[bool] = []
    wheel.closed.connect(lambda: closed.append(True))
    wheel.set_items([FanItem("png", "PNG")])

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    wheel.keyPressEvent(event)

    assert event.isAccepted()
    assert closed == [True]
    assert wheel._items == []


def test_scroll_moves_the_hover(wheel):
    wheel.set_items([FanItem("png", "PNG"), FanItem("webp", "WEBP"), FanItem("jpg", "JPG")])

    wheel.wheelEvent(_wheel_event(-120))
    assert wheel._hover == 0
    wheel.wheelEvent(_wheel_event(-120))
    assert wheel._hover == 1
    wheel.wheelEvent(_wheel_event(120))
    assert wheel._hover == 0
    wheel.wheelEvent(_wheel_event(120))
    assert wheel._hover == 2  # wraps backwards from the first petal
