"""Image display and interaction canvases for the photo editors."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageOps

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QInputDialog, QWidget

from ... import i18n, tools
from ..base import pil_to_qimage

DISPLAY_MAX = 1600


class ImageCanvas(QWidget):
    """Displays an image scaled to fit, with image-pixel coordinate mapping."""

    def __init__(self, path: Path, parent: QWidget | None = None,
                 max_size: tuple[int, int] = (520, 350)):
        super().__init__(parent)
        self._max_size = max_size
        self.image = None
        self.image_size = (0, 0)
        self.display_scale = 1.0
        self.pixmap = QPixmap()
        self.scale = 1.0
        self.offset = QPointF(0.0, 0.0)
        self.setMinimumSize(360, 240)
        self.resize(*max_size)
        self.setMouseTracking(True)
        self.load(path)

    def load(self, path: Path) -> None:
        full = tools.load_image(Path(path))
        if full.getexif().get(274, 1) != 1:
            full = ImageOps.exif_transpose(full)
        width, height = full.size
        self.image_size = (width, height)
        longest = max(width, height)
        if longest > DISPLAY_MAX:
            self.display_scale = longest / DISPLAY_MAX
            display_size = (max(1, round(width / self.display_scale)),
                            max(1, round(height / self.display_scale)))
            if full.mode in ("P", "PA"):
                full = full.convert("RGBA")
            display = full.resize(display_size, Image.LANCZOS)
        else:
            self.display_scale = 1.0
            display = full
        self.image = display.convert("RGBA")
        self.pixmap = QPixmap.fromImage(pil_to_qimage(self.image))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(*self._max_size)

    def _layout(self) -> None:
        if self.pixmap.isNull():
            return
        w = max(self.width(), 40)
        h = max(self.height(), 40)
        self.scale = min(w / self.pixmap.width(), h / self.pixmap.height())
        draw_w = self.pixmap.width() * self.scale
        draw_h = self.pixmap.height() * self.scale
        self.offset = QPointF((w - draw_w) / 2.0, (h - draw_h) / 2.0)

    def to_image(self, pos: QPointF) -> tuple[float, float]:
        self._layout()
        if self.scale <= 0:
            return 0.0, 0.0
        return (
            (pos.x() - self.offset.x()) / self.scale * self.display_scale,
            (pos.y() - self.offset.y()) / self.scale * self.display_scale,
        )

    def to_widget(self, x: float, y: float) -> QPointF:
        self._layout()
        return QPointF(
            self.offset.x() + x / self.display_scale * self.scale,
            self.offset.y() + y / self.display_scale * self.scale,
        )

    def clamp_box(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        img_w, img_h = self.image_size
        x = max(0.0, min(x, img_w - 1.0))
        y = max(0.0, min(y, img_h - 1.0))
        w = max(1.0, min(w, img_w - x))
        h = max(1.0, min(h, img_h - y))
        return x, y, w, h

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._layout()
        target = QRectF(self.offset.x(), self.offset.y(),
                        self.pixmap.width() * self.scale, self.pixmap.height() * self.scale)
        painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        painter.end()
        self.paint_overlay()


class CropCanvas(ImageCanvas):
    HANDLE_PADDING = 12.0

    def __init__(self, path: Path, parent=None):
        super().__init__(path, parent)
        self.rect = [0.0, 0.0, float(self.image_size[0]), float(self.image_size[1])]
        self._mode = None
        self._start = QPointF(0.0, 0.0)
        self._start_rect = list(self.rect)
        self.changed = None
        # The dialog owning this canvas may set this from its aspect selector.
        self.aspect_ratio: float | None = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    HANDLE = 14.0
    MIN_CROP = 8.0
    _HANDLE_DIRECTIONS = {
        "tl": (-1, -1), "tm": (0, -1), "tr": (1, -1),
        "rm": (1, 0), "br": (1, 1), "bm": (0, 1),
        "bl": (-1, 1), "lm": (-1, 0),
    }

    def _layout(self) -> None:
        """Fit the preview inside a small gutter so full-frame grips stay visible."""
        if self.pixmap.isNull():
            return
        padding = self.HANDLE_PADDING
        w = max(self.width() - 2 * padding, 40)
        h = max(self.height() - 2 * padding, 40)
        self.scale = min(w / self.pixmap.width(), h / self.pixmap.height())
        draw_w = self.pixmap.width() * self.scale
        draw_h = self.pixmap.height() * self.scale
        self.offset = QPointF((self.width() - draw_w) / 2.0,
                              (self.height() - draw_h) / 2.0)

    def _handles(self) -> dict[str, QPointF]:
        x, y, w, h = self.rect
        return {
            "tl": self.to_widget(x, y), "tm": self.to_widget(x + w / 2, y),
            "tr": self.to_widget(x + w, y), "rm": self.to_widget(x + w, y + h / 2),
            "br": self.to_widget(x + w, y + h), "bm": self.to_widget(x + w / 2, y + h),
            "bl": self.to_widget(x, y + h), "lm": self.to_widget(x, y + h / 2),
        }

    def _handle_at(self, pos: QPointF) -> str | None:
        # Hit targets remain comfortable even when a large source image is fit
        # into a small preview.
        for name, center in self._handles().items():
            if math.hypot(pos.x() - center.x(), pos.y() - center.y()) <= self.HANDLE:
                return name
        return None

    @staticmethod
    def _cursor_for_handle(handle: str) -> Qt.CursorShape:
        if handle in ("tl", "br"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("tr", "bl"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("tm", "bm"):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeHorCursor

    def _image_point(self, pos: QPointF) -> tuple[float, float]:
        x, y = self.to_image(pos)
        return (max(0.0, min(x, float(self.image_size[0]))),
                max(0.0, min(y, float(self.image_size[1]))))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        self._layout()
        self._start = pos
        self._start_rect = list(self.rect)
        handle = self._handle_at(pos)
        if handle is not None:
            self._mode = handle
            self.setCursor(self._cursor_for_handle(handle))
            return
        x, y = self._image_point(pos)
        rx, ry, rw, rh = self.rect
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            self._mode = "move"
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self._mode = None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._layout()
        if self._mode is None:
            handle = self._handle_at(event.position())
            if handle is not None:
                self.setCursor(self._cursor_for_handle(handle))
            else:
                x, y = self._image_point(event.position())
                rx, ry, rw, rh = self.rect
                self.setCursor(Qt.CursorShape.SizeAllCursor if
                               rx <= x <= rx + rw and ry <= y <= ry + rh
                               else Qt.CursorShape.ArrowCursor)
            return
        rx, ry, rw, rh = self._start_rect
        px, py = self._image_point(event.position())
        sx, sy = self._image_point(self._start)
        dx, dy = px - sx, py - sy
        if self._mode == "move":
            nx = max(0.0, min(rx + dx, self.image_size[0] - rw))
            ny = max(0.0, min(ry + dy, self.image_size[1] - rh))
            self.rect = [nx, ny, rw, rh]
        else:
            self.rect = self._resized_rect(rx, ry, rw, rh, dx, dy, self._mode)
        if self.changed:
            self.changed(self.rect)
        self.update()

    def _resized_rect(self, x: float, y: float, w: float, h: float,
                      dx: float, dy: float, handle: str) -> list[float]:
        """Resize from one of eight edges while keeping the opposite edge fixed."""
        sx, sy = self._HANDLE_DIRECTIONS[handle]
        right, bottom = x + w, y + h
        min_size = self.MIN_CROP
        max_w, max_h = float(self.image_size[0]), float(self.image_size[1])

        if self.aspect_ratio and self.aspect_ratio > 0:
            ratio = float(self.aspect_ratio)
            ratio_max_w = min(max_w, max_h * ratio)
            ratio_max_h = min(max_h, max_w / ratio)
            if sx and sy:
                # Keep the diagonally opposite corner anchored; use the pointer
                # movement that best matches the requested ratio.
                dw, dh = dx * sx, dy * sy
                width_delta = (dw * ratio * ratio + dh * ratio) / (ratio * ratio + 1)
                new_w = w + width_delta
                new_w = max(min(min_size, ratio_max_w), min(new_w, ratio_max_w))
                new_h = new_w / ratio
                nx = right - new_w if sx < 0 else x
                ny = bottom - new_h if sy < 0 else y
            elif sx:
                new_w = max(min(min_size, ratio_max_w), min(w + dx * sx, ratio_max_w))
                new_h = new_w / ratio
                cy = y + h / 2
                nx, ny = (right - new_w if sx < 0 else x), cy - new_h / 2
            else:
                new_h = max(min(min_size, ratio_max_h), min(h + dy * sy, ratio_max_h))
                new_w = new_h * ratio
                cx = x + w / 2
                nx, ny = cx - new_w / 2, (bottom - new_h if sy < 0 else y)
            # Clamp the whole crop to the image, shifting only when needed.
            nx = max(0.0, min(nx, max_w - new_w))
            ny = max(0.0, min(ny, max_h - new_h))
            return [nx, ny, new_w, new_h]

        nx, ny, nr, nb = x, y, right, bottom
        if sx < 0:
            nx = max(0.0, min(x + dx, right - min(min_size, max_w)))
        elif sx > 0:
            nr = min(max_w, max(right + dx, x + min(min_size, max_w)))
        if sy < 0:
            ny = max(0.0, min(y + dy, bottom - min(min_size, max_h)))
        elif sy > 0:
            nb = min(max_h, max(bottom + dy, y + min(min_size, max_h)))
        return [nx, ny, nr - nx, nb - ny]

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._mode = None
        handle = self._handle_at(event.position())
        if handle is not None:
            self.setCursor(self._cursor_for_handle(handle))
        else:
            x, y = self._image_point(event.position())
            rx, ry, rw, rh = self.rect
            self.setCursor(Qt.CursorShape.SizeAllCursor if
                           rx <= x <= rx + rw and ry <= y <= ry + rh
                           else Qt.CursorShape.ArrowCursor)
        self.update()

    def paint_overlay(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x, y, w, h = self.rect
        top_left = self.to_widget(x, y)
        bottom_right = self.to_widget(x + w, y + h)
        selection = QRectF(top_left, bottom_right)

        shade = QColor(0, 0, 0, 110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shade)
        full = QRectF(self.offset.x(), self.offset.y(),
                      self.pixmap.width() * self.scale, self.pixmap.height() * self.scale)
        for region in (
            QRectF(full.left(), full.top(), full.width(), selection.top() - full.top()),
            QRectF(full.left(), selection.bottom(), full.width(), full.bottom() - selection.bottom()),
            QRectF(full.left(), selection.top(), selection.left() - full.left(), selection.height()),
            QRectF(selection.right(), selection.top(), full.right() - selection.right(), selection.height()),
        ):
            painter.drawRect(region)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.6))
        painter.drawRect(selection)
        painter.setPen(QPen(QColor("#000000"), 1.0, Qt.PenStyle.DashLine))
        painter.drawRect(selection)
        # Corner brackets plus eight compact grips make every resize direction
        # visible without obscuring the selected image.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#111111"), 4.0, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.SquareCap))
        arm = min(18.0, max(8.0, min(selection.width(), selection.height()) * 0.08))
        for corner, sx, sy in ((selection.topLeft(), 1, 1),
                               (selection.topRight(), -1, 1),
                               (selection.bottomLeft(), 1, -1),
                               (selection.bottomRight(), -1, -1)):
            painter.drawLine(corner, QPointF(corner.x() + sx * arm, corner.y()))
            painter.drawLine(corner, QPointF(corner.x(), corner.y() + sy * arm))
        painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
        for name, center in self._handles().items():
            if name in ("tm", "bm"):
                grip = QRectF(center.x() - 6, center.y() - 3, 12, 6)
            elif name in ("lm", "rm"):
                grip = QRectF(center.x() - 3, center.y() - 6, 6, 12)
            else:
                grip = QRectF(center.x() - 4.5, center.y() - 4.5, 9, 9)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(grip, 2, 2)
        painter.end()


class RedactCanvas(ImageCanvas):
    def __init__(self, path: Path, parent=None):
        super().__init__(path, parent)
        self.boxes: list[dict] = []
        self.selected = -1
        self.mode = "solid"
        self._drag = None
        self._start = (0.0, 0.0)
        self.changed = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self.to_image(event.position())
        self._start = (x, y)
        self._drag = "new"
        self.selected = -1
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is None:
            return
        x, y = self.to_image(event.position())
        x1, y1 = self._start
        box = self.clamp_box(min(x1, x), min(y1, y), abs(x - x1), abs(y - y1))
        if len(self.boxes) > self.selected and self.selected >= 0:
            self.boxes[self.selected].update({"x": box[0], "y": box[1], "w": box[2], "h": box[3]})
        else:
            self.boxes.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3]})
            self.selected = len(self.boxes) - 1
        if self.changed:
            self.changed()
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag = None
        if self.selected >= 0 and self.boxes[self.selected]["w"] < 4:
            self.boxes.pop(self.selected)
            self.selected = -1
            if self.changed:
                self.changed()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected >= 0:
            self.boxes.pop(self.selected)
            self.selected = -1
            if self.changed:
                self.changed()
            self.update()

    def paint_overlay(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for index, box in enumerate(self.boxes):
            top_left = self.to_widget(box["x"], box["y"])
            bottom_right = self.to_widget(box["x"] + box["w"], box["y"] + box["h"])
            rect = QRectF(top_left, bottom_right)
            fill = QColor(box.get("color", "#000000"))
            fill.setAlpha(150)
            if self.mode == "pixelate":
                self._paint_mosaic(painter, rect, fill)
            else:
                painter.fillRect(rect, fill)
            if index == self.selected:
                painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
            else:
                painter.setPen(QPen(QColor("#F87800"), 1.4, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
        painter.end()

    @staticmethod
    def _paint_mosaic(painter: QPainter, rect: QRectF, fill: QColor) -> None:
        step = 10.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        row = 0
        y = rect.top()
        while y < rect.bottom():
            column = 0
            x = rect.left()
            while x < rect.right():
                if (row + column) % 2 == 0:
                    painter.drawRect(QRectF(
                        x, y,
                        min(step, rect.right() - x),
                        min(step, rect.bottom() - y)))
                x += step
                column += 1
            y += step
            row += 1


class AnnotateCanvas(ImageCanvas):
    def __init__(self, path: Path, parent=None):
        super().__init__(path, parent)
        self.ops: list[dict] = []
        self.tool = "arrow"
        self.color = "#F87800"
        self.stroke_width = 3
        self.font_size = 22
        self._draft = None
        self._start = (0.0, 0.0)
        self._counter = 1

    MAX_OPS = 400

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self.to_image(event.position())
        x = max(0.0, min(x, self.image_size[0] - 1.0))
        y = max(0.0, min(y, self.image_size[1] - 1.0))
        self._start = (x, y)
        if self.tool == "text":
            text, ok = QInputDialog.getText(
                self, i18n.tr("dlg.annotate.text_title"),
                i18n.tr("dlg.annotate.text_prompt"))
            if ok and text.strip():
                self.ops.append({"type": "text", "x": x, "y": y, "text": text.strip(),
                                 "color": self.color, "size": self.font_size})
                self.update()
            return
        if self.tool == "callout":
            self.ops.append({"type": "callout", "x": x, "y": y,
                             "n": self._counter, "color": "#F87800"})
            self._counter += 1
            self.update()
            return
        if self.tool == "pen":
            self._draft = {"type": "pen", "points": [(x, y)], "color": self.color,
                           "width": self.stroke_width}
        else:
            self._draft = {"type": self.tool, "x1": x, "y1": y, "x2": x, "y2": y,
                           "color": self.color, "width": self.stroke_width}
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._draft is None:
            return
        x, y = self.to_image(event.position())
        x = max(0.0, min(x, self.image_size[0] - 1.0))
        y = max(0.0, min(y, self.image_size[1] - 1.0))
        if self._draft["type"] == "pen":
            self._draft["points"].append((x, y))
        else:
            self._draft["x2"], self._draft["y2"] = x, y
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._draft is None:
            return
        draft = self._draft
        self._draft = None
        if len(self.ops) >= self.MAX_OPS:
            self.ops.pop(0)
        if draft["type"] == "pen":
            if len(draft["points"]) >= 2:
                self.ops.append({**draft, "points": list(draft["points"])})
        elif abs(draft["x2"] - draft["x1"]) > 3 or abs(draft["y2"] - draft["y1"]) > 3:
            self.ops.append(draft)
        self.update()

    def undo(self) -> None:
        if self.ops:
            self.ops.pop()
            self.update()

    def reset_ops(self) -> None:
        self.ops.clear()
        self._counter = 1
        self.update()

    def paint_overlay(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        scale = self.scale / self.display_scale
        for op in self.ops:
            _draw_op(painter, op, scale, self.offset)
        if self._draft is not None:
            _draw_op(painter, self._draft, scale, self.offset)
        painter.end()


def _draw_op(painter: QPainter, op: dict, scale: float, offset: QPointF) -> None:
    def point(x: float, y: float) -> QPointF:
        return QPointF(offset.x() + x * scale, offset.y() + y * scale)

    color = QColor(op.get("color", "#F87800"))
    width = max(1.0, float(op.get("width", 3)) * scale)
    kind = op["type"]
    pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
               Qt.PenJoinStyle.RoundJoin)

    if kind == "arrow":
        start = point(op["x1"], op["y1"])
        end = point(op["x2"], op["y2"])
        painter.setPen(pen)
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        head = max(10.0, width * 4.2)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        left = QPointF(end.x() - head * math.cos(angle - 0.42),
                       end.y() - head * math.sin(angle - 0.42))
        right = QPointF(end.x() - head * math.cos(angle + 0.42),
                        end.y() - head * math.sin(angle + 0.42))
        painter.drawPolygon(QPolygonF([end, left, right]))
    elif kind == "pen":
        painter.setPen(pen)
        points = [point(x, y) for x, y in op["points"]]
        for first, second in zip(points, points[1:]):
            painter.drawLine(first, second)
    elif kind in ("rect", "ellipse", "highlight"):
        rect = QRectF(point(op["x1"], op["y1"]), point(op["x2"], op["y2"])).normalized()
        if kind == "highlight":
            fill = QColor("#F8E400")
            fill.setAlpha(90)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRect(rect)
        else:
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if kind == "rect":
                painter.drawRect(rect)
            else:
                painter.drawEllipse(rect)
    elif kind == "text":
        font = QFont("Segoe UI")
        font.setPixelSize(max(9, int(op.get("size", 22) * scale)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        position = point(op["x"], op["y"])
        metrics = painter.fontMetrics()
        text_rect = metrics.boundingRect(op["text"])
        background = QRectF(position.x() - 4, position.y() - text_rect.height() + 2,
                            text_rect.width() + 10, text_rect.height() + 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawRoundedRect(background, 5, 5)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QPointF(position.x(), position.y()), op["text"])
    elif kind == "callout":
        center = point(op["x"], op["y"])
        radius = max(10.0, 15.0 * scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(op.get("color", "#F87800")))
        painter.drawEllipse(center, radius, radius)
        font = QFont("Segoe UI")
        font.setPixelSize(max(9, int(radius * 1.25)))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
            int(Qt.AlignmentFlag.AlignCenter), str(op.get("n", 1)))
