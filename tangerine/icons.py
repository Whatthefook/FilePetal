"""Vector line icons (no emoji) for conversion formats and file tools.

Every glyph is drawn in a normalised unit square with a single round-capped,
round-joined stroke, in the spirit of the SF Symbols used by the macOS app.
:func:`paint_icon` is the drawing entry point; :func:`has_icon` answers
whether a key is known and :func:`icon_for` keeps returning the *logical*
name of the glyph for a key (never an emoji, never a character).

The wheel only uses icons for tool petals; conversion petals show just the
format name.  ``icon_for`` is kept because it is part of the public surface
(``from .wheel import icon_for``, ``tests/test_imports.py``).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

__all__ = ["paint_icon", "has_icon", "icon_for", "GLYPH_KEYS"]


# --------------------------------------------------------------------------
# glyph painters (unit square: (0, 0) top-left, (1, 1) bottom-right)
# --------------------------------------------------------------------------

def _g_compress(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.84, 0.16)
    path.lineTo(0.58, 0.42)
    path.moveTo(0.58, 0.42)
    path.lineTo(0.74, 0.42)
    path.moveTo(0.58, 0.42)
    path.lineTo(0.58, 0.26)
    path.moveTo(0.16, 0.84)
    path.lineTo(0.42, 0.58)
    path.moveTo(0.42, 0.58)
    path.lineTo(0.26, 0.58)
    path.moveTo(0.42, 0.58)
    path.lineTo(0.42, 0.74)
    p.drawPath(path)


def _g_crop(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.16, 0.34)
    path.lineTo(0.16, 0.16)
    path.lineTo(0.34, 0.16)
    path.moveTo(0.66, 0.16)
    path.lineTo(0.84, 0.16)
    path.lineTo(0.84, 0.34)
    path.moveTo(0.84, 0.66)
    path.lineTo(0.84, 0.84)
    path.lineTo(0.66, 0.84)
    path.moveTo(0.34, 0.84)
    path.lineTo(0.16, 0.84)
    path.lineTo(0.16, 0.66)
    p.drawPath(path)


def _g_edit(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.20, 0.80)
    path.lineTo(0.28, 0.54)
    path.lineTo(0.66, 0.16)
    path.lineTo(0.84, 0.34)
    path.lineTo(0.46, 0.72)
    path.lineTo(0.20, 0.80)
    path.moveTo(0.28, 0.54)
    path.lineTo(0.46, 0.72)
    p.drawPath(path)


def _g_annotate(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.26, 0.58)
    path.lineTo(0.60, 0.24)
    path.moveTo(0.40, 0.72)
    path.lineTo(0.74, 0.38)
    path.moveTo(0.26, 0.58)
    path.lineTo(0.40, 0.72)
    path.moveTo(0.60, 0.24)
    path.lineTo(0.74, 0.38)
    path.moveTo(0.14, 0.88)
    path.lineTo(0.86, 0.88)
    p.drawPath(path)


def _g_background(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.10, 0.16, 0.56, 0.56), 0.10, 0.10)
    path.moveTo(0.78, 0.50)
    path.cubicTo(0.92, 0.68, 0.92, 0.88, 0.78, 0.88)
    path.cubicTo(0.64, 0.88, 0.64, 0.68, 0.78, 0.50)
    p.drawPath(path)


def _g_redact(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.50, 0.12)
    path.lineTo(0.82, 0.24)
    path.lineTo(0.82, 0.48)
    path.lineTo(0.50, 0.88)
    path.lineTo(0.18, 0.48)
    path.lineTo(0.18, 0.24)
    path.closeSubpath()
    p.drawPath(path)


def _g_metadata(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.54, 0.14)
    path.lineTo(0.86, 0.14)
    path.lineTo(0.86, 0.46)
    path.lineTo(0.46, 0.86)
    path.lineTo(0.14, 0.54)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(p.pen().color())
    p.drawEllipse(QPointF(0.70, 0.30), 0.055, 0.055)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _page(x0: float, y0: float, width: float, height: float) -> QPainterPath:
    """A page outline with a folded top-right corner."""
    fold = min(width, height) * 0.30
    path = QPainterPath()
    path.moveTo(x0, y0)
    path.lineTo(x0 + width - fold, y0)
    path.lineTo(x0 + width, y0 + fold)
    path.lineTo(x0 + width, y0 + height)
    path.lineTo(x0, y0 + height)
    path.closeSubpath()
    path.moveTo(x0 + width - fold, y0)
    path.lineTo(x0 + width - fold, y0 + fold)
    path.lineTo(x0 + width, y0 + fold)
    return path


def _g_document(p: QPainter) -> None:
    path = _page(0.20, 0.12, 0.60, 0.76)
    path.moveTo(0.32, 0.60)
    path.lineTo(0.68, 0.60)
    path.moveTo(0.32, 0.74)
    path.lineTo(0.56, 0.74)
    p.drawPath(path)


def _g_doc_compress(p: QPainter) -> None:
    path = _page(0.20, 0.10, 0.60, 0.78)
    path.moveTo(0.30, 0.52)
    path.lineTo(0.70, 0.52)
    path.moveTo(0.50, 0.62)
    path.lineTo(0.50, 0.76)
    path.moveTo(0.43, 0.69)
    path.lineTo(0.50, 0.62)
    path.lineTo(0.57, 0.69)
    path.moveTo(0.50, 0.86)
    path.lineTo(0.50, 0.72)
    path.moveTo(0.43, 0.79)
    path.lineTo(0.50, 0.86)
    path.lineTo(0.57, 0.79)
    p.drawPath(path)


def _g_pdf_create(p: QPainter) -> None:
    path = _page(0.14, 0.14, 0.54, 0.72)
    path.moveTo(0.78, 0.60)
    path.lineTo(0.78, 0.84)
    path.moveTo(0.66, 0.72)
    path.lineTo(0.90, 0.72)
    p.drawPath(path)


def _g_collage(p: QPainter) -> None:
    path = QPainterPath()
    for x, y in ((0.12, 0.12), (0.52, 0.12), (0.12, 0.52), (0.52, 0.52)):
        path.addRoundedRect(QRectF(x, y, 0.36, 0.36), 0.08, 0.08)
    p.drawPath(path)


def _g_qr(p: QPainter) -> None:
    for x, y in ((0.12, 0.12), (0.58, 0.12), (0.12, 0.58)):
        p.drawRect(QRectF(x, y, 0.30, 0.30))
        p.drawRect(QRectF(x + 0.09, y + 0.09, 0.12, 0.12))
    p.setBrush(p.pen().color())
    for x, y, size in ((0.60, 0.60, 0.10), (0.74, 0.60, 0.08),
                       (0.60, 0.74, 0.08), (0.74, 0.74, 0.10)):
        p.drawRect(QRectF(x, y, size, size))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _g_qr_scan(p: QPainter) -> None:
    for x, y in ((0.10, 0.10), (0.58, 0.10), (0.10, 0.58)):
        p.drawRect(QRectF(x, y, 0.26, 0.26))
        p.drawRect(QRectF(x + 0.08, y + 0.08, 0.10, 0.10))
    p.drawEllipse(QPointF(0.70, 0.70), 0.16, 0.16)
    path = QPainterPath()
    path.moveTo(0.82, 0.82)
    path.lineTo(0.92, 0.92)
    p.drawPath(path)


def _g_normalize(p: QPainter) -> None:
    path = QPainterPath()
    for x in (0.28, 0.50, 0.72):
        path.moveTo(x, 0.24)
        path.lineTo(x, 0.72)
    path.moveTo(0.16, 0.84)
    path.lineTo(0.84, 0.84)
    p.drawPath(path)


def _g_visualizer(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.10, 0.50)
    path.cubicTo(0.19, 0.16, 0.33, 0.16, 0.42, 0.50)
    path.cubicTo(0.51, 0.84, 0.65, 0.84, 0.74, 0.50)
    path.cubicTo(0.79, 0.32, 0.83, 0.26, 0.90, 0.30)
    p.drawPath(path)


def _g_channels(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.34, 0.14)
    path.lineTo(0.34, 0.86)
    path.moveTo(0.66, 0.14)
    path.lineTo(0.66, 0.86)
    path.moveTo(0.16, 0.36)
    path.lineTo(0.52, 0.36)
    path.moveTo(0.48, 0.66)
    path.lineTo(0.84, 0.66)
    p.drawPath(path)


def _g_mute(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.14, 0.38)
    path.lineTo(0.32, 0.38)
    path.lineTo(0.50, 0.20)
    path.lineTo(0.50, 0.80)
    path.lineTo(0.32, 0.62)
    path.lineTo(0.14, 0.62)
    path.closeSubpath()
    path.moveTo(0.62, 0.38)
    path.lineTo(0.88, 0.64)
    path.moveTo(0.88, 0.38)
    path.lineTo(0.62, 0.64)
    p.drawPath(path)


def _g_bleep(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.12, 0.38)
    path.lineTo(0.28, 0.38)
    path.lineTo(0.44, 0.20)
    path.lineTo(0.44, 0.80)
    path.lineTo(0.28, 0.62)
    path.lineTo(0.12, 0.62)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(p.pen().color())
    p.drawRoundedRect(QRectF(0.56, 0.42, 0.34, 0.16), 0.05, 0.05)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _g_trim(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.32, 0.14)
    path.lineTo(0.16, 0.14)
    path.lineTo(0.16, 0.86)
    path.lineTo(0.32, 0.86)
    path.moveTo(0.68, 0.14)
    path.lineTo(0.84, 0.14)
    path.lineTo(0.84, 0.86)
    path.lineTo(0.68, 0.86)
    path.moveTo(0.38, 0.50)
    path.lineTo(0.62, 0.50)
    p.drawPath(path)


def _g_speed(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.30, 0.26)
    path.lineTo(0.52, 0.50)
    path.lineTo(0.30, 0.74)
    path.moveTo(0.52, 0.26)
    path.lineTo(0.74, 0.50)
    path.lineTo(0.52, 0.74)
    p.drawPath(path)


def _g_camera(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.12, 0.32)
    path.lineTo(0.30, 0.32)
    path.lineTo(0.38, 0.20)
    path.lineTo(0.62, 0.20)
    path.lineTo(0.70, 0.32)
    path.lineTo(0.88, 0.32)
    path.lineTo(0.88, 0.84)
    path.lineTo(0.12, 0.84)
    path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QPointF(0.50, 0.58), 0.16, 0.16)


def _g_split(p: QPainter) -> None:
    body = QPainterPath()
    body.addRoundedRect(QRectF(0.12, 0.24, 0.76, 0.52), 0.08, 0.08)
    p.drawPath(body)
    path = QPainterPath()
    for y in (0.30, 0.42, 0.54, 0.66):
        path.moveTo(0.50, y)
        path.lineTo(0.50, y + 0.06)
    for y in (0.34, 0.50, 0.66):
        path.moveTo(0.20, y)
        path.lineTo(0.26, y)
        path.moveTo(0.74, y)
        path.lineTo(0.80, y)
    p.drawPath(path)


def _g_join(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.10, 0.38, 0.42, 0.24), 0.12, 0.12)
    path.addRoundedRect(QRectF(0.48, 0.38, 0.42, 0.24), 0.12, 0.12)
    path.moveTo(0.36, 0.50)
    path.lineTo(0.64, 0.50)
    p.drawPath(path)


def _g_merge(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.12, 0.20)
    path.lineTo(0.48, 0.50)
    path.moveTo(0.12, 0.80)
    path.lineTo(0.48, 0.50)
    path.moveTo(0.48, 0.50)
    path.lineTo(0.82, 0.50)
    path.moveTo(0.70, 0.38)
    path.lineTo(0.82, 0.50)
    path.lineTo(0.70, 0.62)
    p.drawPath(path)


def _g_text(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.16, 0.30)
    path.lineTo(0.16, 0.16)
    path.lineTo(0.30, 0.16)
    path.moveTo(0.70, 0.16)
    path.lineTo(0.84, 0.16)
    path.lineTo(0.84, 0.30)
    path.moveTo(0.84, 0.70)
    path.lineTo(0.84, 0.84)
    path.lineTo(0.70, 0.84)
    path.moveTo(0.30, 0.84)
    path.lineTo(0.16, 0.84)
    path.lineTo(0.16, 0.70)
    path.moveTo(0.34, 0.36)
    path.lineTo(0.66, 0.36)
    path.moveTo(0.50, 0.36)
    path.lineTo(0.50, 0.68)
    p.drawPath(path)


def _g_extract(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.16, 0.50)
    path.lineTo(0.16, 0.86)
    path.lineTo(0.84, 0.86)
    path.lineTo(0.84, 0.50)
    path.moveTo(0.16, 0.50)
    path.lineTo(0.34, 0.50)
    path.moveTo(0.66, 0.50)
    path.lineTo(0.84, 0.50)
    path.moveTo(0.50, 0.66)
    path.lineTo(0.50, 0.16)
    path.moveTo(0.38, 0.28)
    path.lineTo(0.50, 0.16)
    path.lineTo(0.62, 0.28)
    p.drawPath(path)


def _g_image(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.10, 0.18, 0.80, 0.64), 0.10, 0.10)
    path.moveTo(0.14, 0.70)
    path.lineTo(0.38, 0.44)
    path.lineTo(0.58, 0.66)
    path.lineTo(0.70, 0.54)
    path.lineTo(0.86, 0.70)
    p.drawPath(path)
    p.setBrush(p.pen().color())
    p.drawEllipse(QPointF(0.32, 0.36), 0.065, 0.065)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _g_music(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.42, 0.74)
    path.lineTo(0.42, 0.20)
    path.lineTo(0.82, 0.12)
    path.lineTo(0.82, 0.62)
    p.drawPath(path)
    p.drawEllipse(QPointF(0.32, 0.74), 0.11, 0.09)
    p.drawEllipse(QPointF(0.72, 0.62), 0.11, 0.09)


def _g_movie(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.12, 0.22, 0.76, 0.56), 0.10, 0.10)
    p.drawPath(path)
    triangle = QPainterPath()
    triangle.moveTo(0.42, 0.36)
    triangle.lineTo(0.42, 0.64)
    triangle.lineTo(0.66, 0.50)
    triangle.closeSubpath()
    p.fillPath(triangle, p.pen().color())


def _g_film(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.12, 0.20, 0.76, 0.60), 0.08, 0.08)
    p.drawPath(path)
    p.setBrush(p.pen().color())
    for y in (0.26, 0.40, 0.54, 0.68):
        p.drawRect(QRectF(0.16, y, 0.08, 0.08))
        p.drawRect(QRectF(0.76, y, 0.08, 0.08))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _g_archive(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.10, 0.32)
    path.lineTo(0.90, 0.32)
    path.moveTo(0.16, 0.32)
    path.lineTo(0.16, 0.84)
    path.lineTo(0.84, 0.84)
    path.lineTo(0.84, 0.32)
    path.moveTo(0.38, 0.52)
    path.lineTo(0.62, 0.52)
    p.drawPath(path)


def _g_table(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.12, 0.20, 0.76, 0.60), 0.08, 0.08)
    path.moveTo(0.12, 0.42)
    path.lineTo(0.88, 0.42)
    path.moveTo(0.38, 0.20)
    path.lineTo(0.38, 0.80)
    path.moveTo(0.62, 0.20)
    path.lineTo(0.62, 0.80)
    p.drawPath(path)


def _g_slides(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.12, 0.18, 0.76, 0.50), 0.08, 0.08)
    path.moveTo(0.50, 0.68)
    path.lineTo(0.50, 0.82)
    path.moveTo(0.32, 0.82)
    path.lineTo(0.68, 0.82)
    p.drawPath(path)


def _g_book(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.50, 0.28)
    path.cubicTo(0.38, 0.18, 0.24, 0.16, 0.10, 0.18)
    path.lineTo(0.10, 0.78)
    path.cubicTo(0.24, 0.76, 0.38, 0.78, 0.50, 0.88)
    path.cubicTo(0.62, 0.78, 0.76, 0.76, 0.90, 0.78)
    path.lineTo(0.90, 0.18)
    path.cubicTo(0.76, 0.16, 0.62, 0.18, 0.50, 0.28)
    path.closeSubpath()
    path.moveTo(0.50, 0.28)
    path.lineTo(0.50, 0.88)
    p.drawPath(path)


def _g_globe(p: QPainter) -> None:
    p.drawEllipse(QPointF(0.50, 0.50), 0.38, 0.38)
    path = QPainterPath()
    path.moveTo(0.12, 0.50)
    path.lineTo(0.88, 0.50)
    p.drawPath(path)
    p.drawEllipse(QRectF(0.34, 0.12, 0.32, 0.76))



def _g_share(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.30, 0.50)
    path.lineTo(0.70, 0.28)
    path.moveTo(0.30, 0.50)
    path.lineTo(0.70, 0.72)
    p.drawPath(path)
    r = 0.08
    for x, y in ((0.30, 0.50), (0.70, 0.28), (0.70, 0.72)):
        node = QPainterPath()
        node.addEllipse(QPointF(x, y), r, r)
        p.drawPath(node)


def _g_shelf(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.18, 0.78)
    path.lineTo(0.82, 0.78)
    path.moveTo(0.24, 0.78)
    path.lineTo(0.24, 0.86)
    path.moveTo(0.76, 0.78)
    path.lineTo(0.76, 0.86)
    path.addRoundedRect(QRectF(0.28, 0.18, 0.44, 0.50), 0.06, 0.06)
    p.drawPath(path)


def _g_copy_ref(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.30, 0.30, 0.48, 0.54), 0.06, 0.06)
    path.moveTo(0.22, 0.68)
    path.lineTo(0.22, 0.22)
    path.lineTo(0.68, 0.22)
    p.drawPath(path)


def _g_move(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(0.16, 0.32)
    path.lineTo(0.38, 0.32)
    path.lineTo(0.48, 0.44)
    path.lineTo(0.84, 0.44)
    path.lineTo(0.84, 0.82)
    path.lineTo(0.16, 0.82)
    path.closeSubpath()
    path.moveTo(0.36, 0.64)
    path.lineTo(0.64, 0.64)
    path.lineTo(0.54, 0.54)
    path.moveTo(0.64, 0.64)
    path.lineTo(0.54, 0.74)
    p.drawPath(path)


def _g_copy_path(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.20, 0.40, 0.36, 0.20), 0.10, 0.10)
    path.addRoundedRect(QRectF(0.44, 0.40, 0.36, 0.20), 0.10, 0.10)
    p.drawPath(path)


def _g_terminal(p: QPainter) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.14, 0.20, 0.72, 0.60), 0.08, 0.08)
    path.moveTo(0.28, 0.40)
    path.lineTo(0.42, 0.50)
    path.lineTo(0.28, 0.60)
    path.moveTo(0.48, 0.60)
    path.lineTo(0.66, 0.60)
    p.drawPath(path)


_GLYPHS = {
    "compress": _g_compress,
    "crop": _g_crop,
    "edit": _g_edit,
    "annotate": _g_annotate,
    "background": _g_background,
    "redact": _g_redact,
    "metadata": _g_metadata,
    "document": _g_document,
    "doc_compress": _g_doc_compress,
    "pdf_create": _g_pdf_create,
    "collage": _g_collage,
    "qr": _g_qr,
    "qr_scan": _g_qr_scan,
    "normalize": _g_normalize,
    "visualizer": _g_visualizer,
    "channels": _g_channels,
    "mute": _g_mute,
    "bleep": _g_bleep,
    "trim": _g_trim,
    "speed": _g_speed,
    "camera": _g_camera,
    "split": _g_split,
    "join": _g_join,
    "merge": _g_merge,
    "text": _g_text,
    "extract": _g_extract,
    "image": _g_image,
    "music": _g_music,
    "movie": _g_movie,
    "film": _g_film,
    "archive": _g_archive,
    "table": _g_table,
    "slides": _g_slides,
    "book": _g_book,
    "globe": _g_globe,
    "share": _g_share,
    "shelf": _g_shelf,
    "copy_ref": _g_copy_ref,
    "move": _g_move,
    "copy_path": _g_copy_path,
    "terminal": _g_terminal,

}

GLYPH_KEYS = tuple(sorted(_GLYPHS))

#: Tool id -> glyph name (mirrors ``catalog``'s tool ids).
_TOOL_GLYPHS = {
    "img.compress": "compress",
    "aud.compress": "compress",
    "vid.compress": "compress",
    "doc.compress": "doc_compress",
    "pdf.compress": "doc_compress",
    "txt.compress": "doc_compress",
    "img.crop": "crop",
    "vid.crop": "crop",
    "img.edit": "edit",
    "img.annotate": "annotate",
    "img.background": "background",
    "img.redact": "redact",
    "vid.redact": "redact",
    "img.metadata": "metadata",
    "aud.metadata": "metadata",
    "vid.metadata": "metadata",
    "gif.metadata": "metadata",
    "pdf.metadata": "metadata",
    "img.pdf": "pdf_create",
    "img.collage": "collage",
    "aud.normalize": "normalize",
    "aud.visualizer": "visualizer",
    "aud.trim": "trim",
    "vid.trim": "trim",
    "aud.channels": "channels",
    "aud.bleep": "bleep",
    "vid.removeaudio": "mute",
    "vid.speed": "speed",
    "vid.snapshots": "camera",
    "vid.split": "split",
    "pdf.split": "split",
    "vid.join": "join",
    "pdf.merge": "merge",
    "pdf.qr": "qr_scan",
    "qr.read": "qr_scan",
    "arc.extract": "extract",
    "doc.ocr": "text",
    "img.ocr": "text",
    "txt.ocr": "text",
    "act.share": "share",
    "act.shelf": "shelf",
    "act.copy_ref": "copy_ref",
    "act.move": "move",
    "act.copy_path": "copy_path",
    "act.terminal": "terminal",

}

#: File extension -> glyph name (image families share one glyph).
_EXT_GLYPHS = {
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "webp": "image",
    "heic": "image",
    "heif": "image",
    "tiff": "image",
    "tif": "image",
    "bmp": "image",
    "svg": "image",
    "avif": "image",
    "gif": "film",
    "mp3": "music",
    "m4a": "music",
    "wav": "music",
    "flac": "music",
    "ogg": "music",
    "opus": "music",
    "aiff": "music",
    "aif": "music",
    "wma": "music",
    "mp4": "movie",
    "mov": "movie",
    "mkv": "movie",
    "avi": "movie",
    "webm": "movie",
    "wmv": "movie",
    "m4v": "movie",
    "pdf": "document",
    "docx": "document",
    "rtf": "document",
    "odt": "document",
    "txt": "text",
    "md": "text",
    "srt": "text",
    "vtt": "text",
    "xlsx": "table",
    "csv": "table",
    "pptx": "slides",
    "epub": "book",
    "html": "globe",
    "zip": "archive",
    "tar": "archive",
    "gz": "archive",
    "rar": "archive",
}

_ALIASES = {
    "tag": "metadata",
    "link": "join",
    "links": "join",
    "pdf": "document",
    "photo": "image",
    "wave": "visualizer",
    "faders": "channels",
    "notes": "music",
}


def _resolve(key: str) -> str | None:
    """The glyph name for *key* (tool id, extension, glyph name or alias)."""
    name = str(key or "").strip().lower()
    if not name:
        return None
    name = name.lstrip(".")
    if name in _TOOL_GLYPHS:
        return _TOOL_GLYPHS[name]
    if name in _EXT_GLYPHS:
        return _EXT_GLYPHS[name]
    name = _ALIASES.get(name, name)
    return name if name in _GLYPHS else None


def paint_icon(
    painter: QPainter,
    key: str,
    rect: QRectF,
    color: QColor,
    stroke: float = 2.0,
) -> bool:
    """Stroke the line icon for *key* inside *rect*.

    Returns ``True`` when an icon was painted, ``False`` for unknown keys (the
    caller can then fall back to text only).  *stroke* is the pen width in
    device-independent pixels; *rect* is squared up around its centre.
    """
    glyph = _GLYPHS.get(_resolve(key) or "")
    if glyph is None:
        return False
    box = float(min(rect.width(), rect.height()))
    if box <= 1.0:
        return False
    width = max(0.4, float(stroke)) / box
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(rect.center())
        painter.scale(box, box)
        painter.translate(-0.5, -0.5)
        glyph(painter)
    finally:
        painter.restore()
    return True


def has_icon(key: str) -> bool:
    """Whether :func:`paint_icon` can draw *key*."""
    return _resolve(key) is not None


def icon_for(key: str) -> str:
    """Logical glyph name for *key* (compatibility shim; never an emoji).

    ``icon_for("jpg") == "image"``; unknown keys return ``""`` so callers can
    skip the icon instead of painting a placeholder glyph.
    """
    return _resolve(key) or ""
