"""Qt event and render coverage for the crop and annotation canvases."""

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QInputDialog

from tangerine import theme
from tangerine.editors.images import (
    AnnotateDialog,
    CropImageDialog,
    render_annotations,
)
from tangerine.editors.ui.canvas import AnnotateCanvas, CropCanvas


@pytest.fixture
def source_image(tmp_path: Path) -> Path:
    path = tmp_path / "canvas.png"
    Image.new("RGB", (240, 160), (100, 120, 140)).save(path)
    return path


def _show(canvas, qapp):
    canvas.resize(480, 320)
    canvas.show()
    qapp.processEvents()
    canvas._layout()


def _point(canvas, x, y) -> QPoint:
    point = canvas.to_widget(x, y)
    return QPoint(round(point.x()), round(point.y()))


def _render(canvas, qapp) -> QImage:
    qapp.processEvents()
    image = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    canvas.render(painter, QPoint())
    painter.end()
    return image


def _different_pixels(before: QImage, after: QImage) -> int:
    return sum(before.pixel(x, y) != after.pixel(x, y)
               for y in range(before.height()) for x in range(before.width()))


def test_annotate_canvas_renders_source_and_each_of_seven_tools(
        qapp, source_image, monkeypatch):
    canvas = AnnotateCanvas(source_image)
    try:
        _show(canvas, qapp)
        base = _render(canvas, qapp)
        assert not canvas.pixmap.isNull()
        assert base.pixelColor(240, 160).red() == 100  # actual source pixels rendered
        assert callable(canvas.width) and canvas.width() == 480
        assert canvas.stroke_width == 3
        canvas.stroke_width = 5

        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Test note", True))
        tools = ("arrow", "pen", "rect", "ellipse", "text", "highlight", "callout")
        for index, tool in enumerate(tools):
            canvas.tool = tool
            start = _point(canvas, 35 + index * 5, 40 + index * 4)
            end = _point(canvas, 160 + index * 3, 115 - index * 2)
            before = _render(canvas, qapp)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
            if tool not in ("text", "callout"):
                QTest.mouseMove(canvas, end)
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
            else:
                QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=start)
            after = _render(canvas, qapp)
            assert canvas.ops, f"{tool} did not create an annotation"
            assert _different_pixels(before, after) > 0, f"{tool} did not render"
            output = render_annotations(source_image, list(canvas.ops))
            with Image.open(source_image) as original, Image.open(output) as saved:
                assert saved.size == original.size
                difference = ImageChops.difference(
                    original.convert("RGB"), saved.convert("RGB"))
                assert difference.getbbox(), f"{tool} missing from saved render"
        assert {op["type"] for op in canvas.ops} == set(tools)
        assert all(op.get("width") == 5 for op in canvas.ops if "width" in op)
        before_undo = len(canvas.ops)
        canvas.undo()
        assert len(canvas.ops) == before_undo - 1
        canvas.reset_ops()
        assert canvas.ops == [] and canvas._counter == 1
    finally:
        canvas.close()


def test_annotate_size_slider_preserves_qwidget_width(qapp, source_image):
    dialog = AnnotateDialog(source_image)
    try:
        dialog.width_slider.setValue(7)
        assert dialog.canvas.stroke_width == 7
        assert callable(dialog.canvas.width) and dialog.canvas.width() == 520
    finally:
        dialog.close()


def test_crop_aspect_selector_wires_ratio_and_free_clears_it(qapp, source_image):
    dialog = CropImageDialog(source_image)
    try:
        dialog.aspect.setCurrentIndex(2)
        assert dialog.canvas.aspect_ratio == pytest.approx(1.5)
        dialog.aspect.setCurrentIndex(0)
        assert dialog.canvas.aspect_ratio is None
    finally:
        dialog.close()


def test_crop_numeric_resize_keeps_ratio_when_origin_is_near_image_edge(
        qapp, source_image):
    dialog = CropImageDialog(source_image)
    try:
        dialog.aspect.setCurrentIndex(2)
        dialog.canvas.rect = [120.0, 0.0, 120.0, 80.0]
        dialog.w_spin.blockSignals(True)
        dialog.h_spin.blockSignals(True)
        dialog.w_spin.setValue(120)
        dialog.h_spin.setValue(80)
        dialog.w_spin.blockSignals(False)
        dialog.h_spin.blockSignals(False)
        dialog.w_spin.setValue(240)
        x, y, w, h = dialog.canvas.rect
        assert x >= 0 and y >= 0 and x + w <= 240 and y + h <= 160
        assert w / h == pytest.approx(1.5, abs=0.02)
    finally:
        dialog.close()


def test_crop_exposes_eight_resize_handles_and_directional_cursors(
        qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        canvas.rect = [40.0, 30.0, 150.0, 100.0]
        handles = canvas._handles()
        assert set(handles) == {"tl", "tm", "tr", "rm", "br", "bm", "bl", "lm"}

        expected = {
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
            "tm": Qt.CursorShape.SizeVerCursor,
            "bm": Qt.CursorShape.SizeVerCursor,
            "lm": Qt.CursorShape.SizeHorCursor,
            "rm": Qt.CursorShape.SizeHorCursor,
        }
        for name, point in handles.items():
            QTest.mouseMove(canvas, QPoint(round(point.x()), round(point.y())))
            assert canvas.cursor().shape() == expected[name]
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton,
                             pos=QPoint(round(point.x()), round(point.y())))
            assert canvas.cursor().shape() == expected[name]
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton,
                               pos=QPoint(round(point.x()), round(point.y())))
    finally:
        canvas.close()


def test_full_frame_crop_grips_are_inside_widget_and_interactive(qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        handles = canvas._handles()
        expected_names = {"tl", "tm", "tr", "rm", "br", "bm", "bl", "lm"}
        assert set(handles) == expected_names
        assert canvas.offset.x() >= canvas.HANDLE_PADDING - 0.5
        assert canvas.offset.y() >= canvas.HANDLE_PADDING - 0.5
        right = canvas.offset.x() + canvas.pixmap.width() * canvas.scale
        bottom = canvas.offset.y() + canvas.pixmap.height() * canvas.scale
        assert right <= canvas.width() - canvas.HANDLE_PADDING + 0.5
        assert bottom <= canvas.height() - canvas.HANDLE_PADDING + 0.5

        for name, center in handles.items():
            extent = 6.0 if name in ("tm", "bm", "lm", "rm") else 4.5
            assert center.x() - extent >= 0 and center.x() + extent <= canvas.width()
            assert center.y() - extent >= 0 and center.y() + extent <= canvas.height()
            pos = QPoint(round(center.x()), round(center.y()))
            QTest.mouseMove(canvas, pos)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=pos)
            assert canvas._mode == name
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=pos)
    finally:
        canvas.close()


def test_crop_side_handle_resizes_and_clamps_to_image(qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        canvas.rect = [40.0, 30.0, 150.0, 100.0]
        right = _point(canvas, 190, 80)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=right)
        assert canvas._mode == "rm"
        QTest.mouseMove(canvas, _point(canvas, 225, 80))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 225, 80))
        assert canvas.rect == pytest.approx([40.0, 30.0, 185.0, 100.0], abs=2.0)

        right = _point(canvas, 225, 80)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=right)
        QTest.mouseMove(canvas, _point(canvas, 300, 80))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_point(canvas, 300, 80))
        assert canvas.rect[0] + canvas.rect[2] <= 240.0
    finally:
        canvas.close()


def test_crop_all_eight_handles_resize_in_the_expected_direction(qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        start_rect = [50.0, 40.0, 120.0, 80.0]
        drags = {
            "tl": (-10, -10, (-10, -10, 10, 10)),
            "tm": (0, -10, (0, -10, 0, 10)),
            "tr": (10, -10, (0, -10, 10, 10)),
            "rm": (10, 0, (0, 0, 10, 0)),
            "br": (10, 10, (0, 0, 10, 10)),
            "bm": (0, 10, (0, 0, 0, 10)),
            "bl": (-10, 10, (-10, 0, 10, 10)),
            "lm": (-10, 0, (-10, 0, 10, 0)),
        }
        for name, (dx, dy, expected_delta) in drags.items():
            canvas.rect = list(start_rect)
            center = canvas._handles()[name]
            start = QPoint(round(center.x()), round(center.y()))
            end = _point(canvas, canvas.to_image(center)[0] + dx,
                         canvas.to_image(center)[1] + dy)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
            assert canvas._mode == name
            QTest.mouseMove(canvas, end)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
            actual_delta = tuple(round(a - b) for a, b in zip(canvas.rect, start_rect))
            assert actual_delta == expected_delta, name
            x, y, w, h = canvas.rect
            assert x >= 0 and y >= 0 and x + w <= 240 and y + h <= 160
    finally:
        canvas.close()


def test_crop_drag_preserves_ratio_mapping_and_renders_grips(qapp, source_image):
    canvas = CropCanvas(source_image)
    old_stylesheet = qapp.styleSheet()
    try:
        _show(canvas, qapp)
        canvas.rect = [40.0, 30.0, 120.0, 80.0]
        canvas.aspect_ratio = 1.5
        before = _render(canvas, qapp)
        start = _point(canvas, 160, 70)  # right side handle
        end = _point(canvas, 190, 70)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        assert canvas._mode == "rm"
        QTest.mouseMove(canvas, end)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

        x, y, w, h = canvas.rect
        assert w / h == pytest.approx(1.5, abs=0.02)
        assert x == pytest.approx(40, abs=2)
        mapped = canvas.to_image(canvas.to_widget(100.0, 60.0))
        assert mapped == pytest.approx((100.0, 60.0), abs=0.5)
        for dark in (False, True):
            qapp.setStyleSheet(theme.stylesheet(dark))
            rendered_canvas = _render(canvas, qapp)
            assert _different_pixels(before, rendered_canvas) > 0
            # Each of the eight grips is drawn with clear contrast in both themes.
            for center in canvas._handles().values():
                rendered = rendered_canvas.pixelColor(round(center.x()), round(center.y()))
                assert rendered.red() > 220 and rendered.green() > 220 and rendered.blue() > 220
    finally:
        qapp.setStyleSheet(old_stylesheet)
        canvas.close()


def test_ratio_resizes_from_every_handle_without_leaving_image(qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        original = [50.0, 40.0, 120.0, 80.0]
        canvas.aspect_ratio = 1.5
        for name, (sx, sy) in canvas._HANDLE_DIRECTIONS.items():
            canvas.rect = list(original)
            center = canvas._handles()[name]
            start = QPoint(round(center.x()), round(center.y()))
            start_x, start_y = canvas.to_image(center)
            end = _point(canvas, start_x + sx * 18, start_y + sy * 12)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
            assert canvas._mode == name
            QTest.mouseMove(canvas, end)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
            x, y, w, h = canvas.rect
            assert w / h == pytest.approx(1.5, abs=0.02), name
            assert x >= 0 and y >= 0 and x + w <= 240 and y + h <= 160, name
    finally:
        canvas.close()


def test_full_frame_ratio_drag_from_each_handle_stays_inside_image(qapp, source_image):
    canvas = CropCanvas(source_image)
    try:
        _show(canvas, qapp)
        full = [0.0, 0.0, 240.0, 160.0]
        canvas.aspect_ratio = 1.5
        for name, (sx, sy) in canvas._HANDLE_DIRECTIONS.items():
            canvas.rect = list(full)
            center = canvas._handles()[name]
            image_x, image_y = canvas.to_image(center)
            start = QPoint(round(center.x()), round(center.y()))
            end = _point(canvas, image_x - sx * 12, image_y - sy * 12)
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
            assert canvas._mode == name
            QTest.mouseMove(canvas, end)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
            x, y, w, h = canvas.rect
            assert w / h == pytest.approx(1.5, abs=0.02), name
            assert x >= 0 and y >= 0 and x + w <= 240 and y + h <= 160, name
            assert w < 240 or h < 160, name
    finally:
        canvas.close()
