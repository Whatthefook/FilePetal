"""Conversion engines: images, audio, video, PDF/TXT/DOCX, documents, archives."""

from __future__ import annotations

import gzip
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from . import i18n, naming, render
from .image_pdf import PdfOptions, create_image_pdf
from .catalog import (
    AUDIO_EXTS, FAMILY_ARCHIVE, FAMILY_AUDIO, FAMILY_DOC, FAMILY_GIF,
    FAMILY_IMAGE, FAMILY_PDF, FAMILY_SUB, FAMILY_TXT, FAMILY_VIDEO, GIF_EXTS,
    PDF_EXTS, RASTER_EXTS, SVG_EXTS, TXT_EXTS, ARCHIVE_EXTS, family_of,
)
from .media import (
    CREATE_NO_WINDOW, MediaInfo, ffmpeg_path, probe, run_ffmpeg, run_process,
    unrar_path, rar_path,
)

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None


class EngineError(Exception):
    pass


_MAX_EXTRACT_BYTES = 16 * 1024 ** 3
_GZ_SNIFF_BYTES = 64 * 1024


@dataclass
class Ctx:
    """Progress/cancel/status plumbing shared by every conversion."""

    progress: Callable[[float], None] = lambda f: None
    status: Callable[[str], None] = lambda s: None
    cancel: threading.Event | None = None

    def cancelled(self) -> bool:
        return self.cancel is not None and self.cancel.is_set()


def _no_window_kw() -> dict:
    return {"creationflags": CREATE_NO_WINDOW} if os.name == "nt" else {}


def verify_writable(path: Path) -> None:
    """Reject locked files early (macOS parity: locked-file rejection)."""
    if not path.exists():
        raise EngineError(i18n.tr("err.file_missing", name=path.name))
    try:
        with open(path, "rb+"):
            pass
    except PermissionError as exc:
        raise EngineError(i18n.tr("err.file_locked", name=path.name)) from exc
    except OSError:
        return


def _unique(folder: Path, stem: str, suffix: str, reserved: set[Path]) -> Path:
    return naming.unique_path(folder, stem, suffix, reserved)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def load_image(path: Path) -> Image.Image:
    if path.suffix.lower() in SVG_EXTS:
        return render_svg(path)
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception as exc:
        raise EngineError(
            i18n.tr("err.read_image", name=path.name, detail=exc)) from exc


def render_svg(path: Path, target_width: int | None = None) -> Image.Image:
    """Rasterize SVG at its declared pixel size via QtSvg."""
    from PySide6.QtCore import QByteArray, QSize
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    data = path.read_bytes()
    if path.suffix.lower() == ".svgz":
        data = gzip.decompress(data)
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise EngineError(i18n.tr("err.rasterize_svg", name=path.name))
    size = renderer.defaultSize()
    width = target_width or (size.width() if size.width() > 0 else 1024)
    height = int(round(width * size.height() / size.width())) if size.width() else width
    if height <= 0:
        height = 1024
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = image.constBits().tobytes()
    return Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", image.bytesPerLine(), 1)


def _flatten(img: Image.Image, background: str = "white") -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        canvas = Image.new("RGB", img.size, background)
        canvas.paste(img, mask=img.getchannel("A"))
        return canvas
    return img.convert("RGB")


def _image_save_args(target: str, img: Image.Image, source: Path) -> tuple[dict, str]:
    kwargs: dict = {}
    fmt = target.upper()
    if target == "jpg":
        fmt = "JPEG"
        kwargs["quality"] = 92
        kwargs["optimize"] = True
        kwargs["progressive"] = True
    elif target == "png":
        kwargs["optimize"] = True
    elif target == "webp":
        fmt = "WEBP"
        kwargs["quality"] = 92
        kwargs["method"] = 6
    elif target == "heic":
        fmt = "HEIF"
        kwargs["quality"] = 90
    elif target == "avif":
        fmt = "AVIF"
        kwargs["quality"] = 80
    elif target == "tiff":
        fmt = "TIFF"
        kwargs["compression"] = "tiff_lzw"
    return kwargs, fmt


def convert_image(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    verify_writable(path)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    img = load_image(path)
    folder = path.parent
    out_path = _unique(folder, path.stem, f".{target}", reserved)

    img = ImageOps.exif_transpose(img)
    exif = None
    if target.lower() not in ("png", "heic", "heif"):
        exif = img.info.get("exif")

    if target == "pdf":
        if img.mode in ("RGBA", "LA", "P"):
            img = _flatten(img)
        elif img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_path, "PDF", resolution=150.0)
        ctx.progress(1.0)
        return out_path

    if target in ("jpg",):
        img = _flatten(img)
    elif target == "avif" and img.mode not in ("RGB", "RGBA"):
        # pillow-heif writes RGB/RGBA AVIF; flatten palettes and odd modes.
        img = _flatten(img)
    kwargs, fmt = _image_save_args(target, img, path)
    if exif and fmt in ("JPEG", "TIFF", "WEBP", "AVIF"):
        kwargs["exif"] = exif
    try:
        if fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(out_path, fmt, **kwargs)
    except Exception as exc:
        raise EngineError(
            i18n.tr("err.save_image", name=out_path.name, detail=exc)) from exc
    ctx.progress(1.0)
    return out_path


def images_to_pdf(
    paths: list[Path],
    ctx: Ctx,
    reserved: set[Path],
    options: PdfOptions | None = None,
) -> Path:
    """Compatibility wrapper for the configurable image-to-PDF engine."""
    return create_image_pdf(paths, ctx, reserved, options)


def image_to_docx(path: Path, ctx: Ctx, reserved: set[Path]) -> Path:
    import docx
    from docx.shared import Inches

    verify_writable(path)
    out_path = _unique(path.parent, path.stem, ".docx", reserved)
    document = docx.Document()
    img = ImageOps.exif_transpose(load_image(path))
    tmp = io.BytesIO()
    (img.convert("RGB") if img.mode != "RGB" else img).save(tmp, "PNG")
    tmp.seek(0)
    width_inches = min(6.5, img.width / 150.0)
    document.add_picture(tmp, width=Inches(width_inches))
    document.save(str(out_path))
    ctx.progress(1.0)
    return out_path


# ---------------------------------------------------------------------------
# Audio / video via FFmpeg
# ---------------------------------------------------------------------------

CODEC_ARGS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac", "-compression_level", "6"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "aiff": ["-c:a", "pcm_s16be"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
}

#: Video-stream encoders for the containers that are not H.264 + AAC (WebM,
#: AVI, WMV); ``convert_video`` and ``convert_gif`` share them.
_VIDEO_STREAM_ARGS = {
    # VP9 is the slowest encoder of the set: -cpu-used 4 keeps WebM usable.
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
             "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p"],
    "avi": ["-c:v", "mpeg4", "-q:v", "4"],
    "wmv": ["-c:v", "wmv2", "-q:v", "4"],
}

#: Audio-stream encoders pairing with :data:`_VIDEO_STREAM_ARGS`.
_VIDEO_TARGET_AUDIO_ARGS = {
    "webm": ["-c:a", "libopus", "-b:a", "128k"],
    "avi": ["-c:a", "libmp3lame", "-q:a", "4"],
    "wmv": ["-c:a", "wmav2", "-b:a", "192k"],
}


def convert_audio(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    verify_writable(path)
    info = probe(path)
    out_path = _unique(path.parent, path.stem, f".{target}", reserved)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    args = ["-i", str(path), "-vn", *CODEC_ARGS[target], "-map_metadata", "0", str(out_path)]
    tail: list[str] = []
    code = run_ffmpeg(args, info.duration, ctx.progress, ctx.cancel, tail=tail)
    _finish_ffmpeg(code, out_path, tail)
    return out_path


_EVEN_SCALE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def convert_video(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    """Transcode *path* into the video/audio container *target*.

    Video streams are always rescaled to even dimensions.  Besides the H.264
    targets, WebM re-encodes with VP9 + Opus (VP9 is the slowest encoder here,
    so ``-deadline good -cpu-used 4`` trades quality for usability), AVI uses
    MPEG-4 part 2 + MP3 and WMV uses WMV2 + WMAv2.
    """
    verify_writable(path)
    info = probe(path)
    out_path = _unique(path.parent, path.stem, f".{target}", reserved)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    args = ["-i", str(path)]
    if target == "mp4":
        args += [
            "-vf", _EVEN_SCALE,
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k",
        ]
    elif target == "mov":
        args += [
            "-vf", _EVEN_SCALE,
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        ]
    elif target == "mkv":
        codecs_copy = info.video() and info.video().codec in ("h264", "hevc", "vp9", "av1")
        if codecs_copy:
            args += ["-c:v", "copy"]
        else:
            args += ["-vf", _EVEN_SCALE, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        audio = info.audio()
        if audio and audio.codec in ("aac", "mp3", "flac", "opus", "vorbis"):
            args += ["-c:a", "copy"]
        else:
            args += ["-c:a", "aac", "-b:a", "192k"]
    elif target in _VIDEO_STREAM_ARGS:
        args += [
            "-vf", _EVEN_SCALE,
            *_VIDEO_STREAM_ARGS[target],
            *_VIDEO_TARGET_AUDIO_ARGS[target],
        ]
    elif target == "gif":
        args += ["-vf", _gif_filter(), "-loop", "0"]
    elif target in ("mp3", "m4a"):
        args += ["-vn", *CODEC_ARGS[target]]
    args += [str(out_path)]
    tail: list[str] = []
    code = run_ffmpeg(args, info.duration, ctx.progress, ctx.cancel, tail=tail)
    _finish_ffmpeg(code, out_path, tail)
    return out_path


def _gif_filter() -> str:
    return (
        "fps=15,scale='min(960,iw)':-2:flags=lanczos,"
        "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
    )


def convert_gif(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    verify_writable(path)
    info = probe(path)
    out_path = _unique(path.parent, path.stem, f".{target}", reserved)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    args = ["-i", str(path)]
    if target == "mp4":
        args += ["-vf", _EVEN_SCALE, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
    elif target == "mov":
        args += ["-vf", _EVEN_SCALE, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", "-an"]
    elif target in _VIDEO_STREAM_ARGS:
        args += ["-vf", _EVEN_SCALE, *_VIDEO_STREAM_ARGS[target], "-an"]
    else:
        args += ["-vf", _EVEN_SCALE, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p"]
    args += [str(out_path)]
    tail: list[str] = []
    code = run_ffmpeg(args, info.duration, ctx.progress, ctx.cancel, tail=tail)
    _finish_ffmpeg(code, out_path, tail)
    return out_path


def _finish_ffmpeg(code: int, out_path: Path, tail: list[str] | None = None) -> None:
    if code == -9:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        raise EngineError(i18n.tr("err.cancelled"))
    if code != 0 or not out_path.exists():
        out_path.unlink(missing_ok=True)
        detail = ""
        if tail:
            lines = [line for line in tail if line][-3:]
            if lines:
                detail = ": " + " | ".join(lines)
        raise EngineError(
            i18n.tr("err.ffmpeg_process", name=out_path.name) + detail)
    if out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise EngineError(i18n.tr("err.ffmpeg_empty"))


# ---------------------------------------------------------------------------
# PDF / TXT / DOCX
# ---------------------------------------------------------------------------

_PDF_DPI = 300.0


def _open_pdf_reader(path: Path):
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise EngineError(i18n.tr("err.pdf_open")) from exc
    if reader.is_encrypted:
        raise EngineError(i18n.tr("err.pdf_password"))
    return reader


def _open_pdf_document(path: Path):
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(str(path))
    except Exception as exc:
        if "password" in str(exc).lower():
            raise EngineError(i18n.tr("err.pdf_password")) from exc
        raise EngineError(i18n.tr("err.pdf_open")) from exc


_OCR_DPI = 250.0

_ocr_available_cache: bool | None = None
_ocr_engine_cache = None


def _ocr_available() -> bool:
    """Whether the optional open-source OCR engine can be imported."""
    global _ocr_available_cache
    if _ocr_available_cache is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401

            _ocr_available_cache = True
        except Exception:
            _ocr_available_cache = False
    return _ocr_available_cache


def _ocr_engine():
    global _ocr_engine_cache
    if _ocr_engine_cache is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine_cache = RapidOCR()
    return _ocr_engine_cache


def _ocr_pdf_text(path: Path, ctx: Ctx | None = None) -> str:
    """OCR every page of *path* (250 dpi renders) and join with page markers."""
    import numpy as np

    pdf = _open_pdf_document(path)
    engine = _ocr_engine()
    page_count = len(pdf)
    scale = _OCR_DPI / 72.0
    chunks: list[str] = []
    for number in range(page_count):
        if ctx is not None and ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        if ctx is not None:
            ctx.status(i18n.tr(
                "action.reading_page_ocr",
                number=number + 1, total=page_count,
            ))
        image = pdf[number].render(scale=scale).to_pil()
        try:
            result, _ = engine(np.asarray(image))
        finally:
            image.close()
        text = "\n".join(line[1] for line in result) if result else ""
        if page_count > 1:
            chunks.append(f"----- Page {number + 1} -----\n{text}")
        else:
            chunks.append(text)
        if ctx is not None:
            ctx.progress((number + 1) / page_count)
    return "\n\n".join(chunks).strip()


def _is_page_separator(line: str) -> bool:
    return line.startswith("----- Page ") and line.endswith(" -----")


def pdf_to_images(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> list[Path]:
    verify_writable(path)
    pdf = _open_pdf_document(path)
    return _render_pdf_pages(pdf, path.parent, path, target, ctx, reserved)


def _render_pdf_pages(
    pdf, folder: Path, naming_source: Path, target: str, ctx: Ctx, reserved: set[Path],
) -> list[Path]:
    """Rasterize an open pdfium document, named after *naming_source*.

    Single page: ``<stem>.<ext>`` inside *folder*. Multiple pages: a staged
    ``<stem> JPG/PNG Pages`` folder published atomically into *folder*.
    """
    page_count = len(pdf)
    scale = _PDF_DPI / 72.0
    ext = ".jpg" if target == "jpg" else ".png"
    outputs: list[Path] = []
    if page_count <= 1:
        page = pdf[0]
        image = page.render(scale=scale).to_pil()
        out_path = _unique(folder, naming_source.stem, ext, reserved)
        _save_rendered(image, out_path, target)
        outputs.append(out_path)
        ctx.progress(1.0)
        return outputs
    dir_name = naming.folder_name(naming_source, "JPG Pages" if target == "jpg" else "PNG Pages")
    out_dir = folder / dir_name
    index = 2
    while out_dir.exists():
        out_dir = folder / f"{dir_name} {index}"
        index += 1
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tangerine_pages_", dir=str(folder)))
    try:
        for number in range(page_count):
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            page = pdf[number]
            image = page.render(scale=scale).to_pil()
            page_name = f"Page {number + 1:03d}{ext}"
            _save_rendered(image, tmp_dir / page_name, target)
            ctx.progress((number + 1) / page_count)
            ctx.status(i18n.tr(
                "action.rendering_page", number=number + 1, total=page_count))
        os.replace(tmp_dir, out_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    outputs.extend(sorted(out_dir.iterdir()))
    return outputs


def _save_rendered(image, out_path: Path, target: str) -> None:
    if target == "jpg":
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(out_path, "JPEG", quality=92, dpi=(_PDF_DPI, _PDF_DPI), optimize=True)
    else:
        image.save(out_path, "PNG", dpi=(_PDF_DPI, _PDF_DPI), optimize=True)


def pdf_text(path: Path, ctx: Ctx | None = None) -> str:
    reader = _open_pdf_reader(path)
    chunks = []
    for number, page in enumerate(reader.pages, start=1):
        if ctx is not None and ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if len(reader.pages) > 1:
            chunks.append(f"----- Page {number} -----\n{text}")
        else:
            chunks.append(text)
    result = "\n\n".join(chunks).strip()
    if result:
        return result
    try:
        pdf = _open_pdf_document(path)
        pages = []
        for number in range(len(pdf)):
            if ctx is not None and ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            page = pdf[number]
            text = page.get_textpage().get_text_range() or ""
            if len(pdf) > 1:
                pages.append(f"----- Page {number + 1} -----\n{text}")
            else:
                pages.append(text)
        result = "\n\n".join(pages).strip()
    except EngineError:
        raise
    except Exception:
        result = ""
    if result:
        return result
    if _ocr_available():
        return _ocr_pdf_text(path, ctx)
    raise EngineError(i18n.tr("err.ocr_install"))


def convert_pdf(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> list[Path]:
    verify_writable(path)
    if target in ("jpg", "png"):
        return pdf_to_images(path, target, ctx, reserved)
    if target == "txt":
        ctx.status(i18n.tr("action.extracting_text", name=path.name))
        text = pdf_text(path, ctx)
        if not text:
            raise EngineError(i18n.tr("err.pdf_no_text"))
        out_path = _unique(path.parent, path.stem, ".txt", reserved)
        out_path.write_text(text + "\n", "utf-8")
        ctx.progress(1.0)
        return [out_path]
    if target == "docx":
        return [pdf_to_docx(path, ctx, reserved)]
    raise EngineError(i18n.tr("err.pdf_unsupported", target=target))


def pdf_to_docx(path: Path, ctx: Ctx, reserved: set[Path]) -> Path:
    import docx
    from docx.shared import Inches

    reader = _open_pdf_reader(path)
    document = docx.Document()
    page_texts: list[str] = []
    for page in reader.pages:
        if ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        try:
            page_texts.append(page.extract_text() or "")
        except Exception:
            page_texts.append("")
    if _ocr_available() and not any(text.strip() for text in page_texts):
        for line in _ocr_pdf_text(path, ctx).splitlines():
            if not _is_page_separator(line):
                document.add_paragraph(line)
    else:
        pdf = _open_pdf_document(path)
        scale = 150.0 / 72.0
        for number, text in enumerate(page_texts):
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            if text.strip():
                for paragraph in text.splitlines():
                    document.add_paragraph(paragraph)
            else:
                rendered = pdf[number].render(scale=scale).to_pil()
                if rendered.mode != "RGB":
                    rendered = rendered.convert("RGB")
                tmp = io.BytesIO()
                rendered.save(tmp, "PNG")
                tmp.seek(0)
                document.add_picture(tmp, width=Inches(6.5))
            ctx.progress((number + 1) / max(len(page_texts), 1))
    out_path = _unique(path.parent, path.stem, ".docx", reserved)
    document.save(str(out_path))
    return out_path


FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
    Path("C:/Windows/Fonts/lucon.ttf"),
]

PDF_MONO_CANDIDATES = [
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/DejaVuSansMono.ttf"),
]

PDF_UNICODE_FALLBACKS = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]


def _mono_font(size: int):
    from PIL import ImageFont

    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _pdf_mono_font(text: str) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    required = {char for char in text if ord(char) > 0xFF}
    chosen = None
    for index, candidate in enumerate(PDF_MONO_CANDIDATES + PDF_UNICODE_FALLBACKS):
        if not candidate.exists():
            continue
        name = "TangerineMono" if index == 0 else f"TangerineMono{index + 1}"
        try:
            font = TTFont(name, str(candidate), subfontIndex=0)
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(font)
        except Exception:
            continue
        if chosen is None:
            chosen = name
        if all(ord(char) in font.face.charToGlyph for char in required):
            return name
    return chosen or "Courier"


def text_to_pdf(
    text: str, out_path: Path, ctx: Ctx, *, page_numbers: bool | None = None,
) -> Path:
    """Write plain text to *out_path* through the shared document pipeline.

    The text keeps its monospace columns (``pre.plain``, wrapped to the page
    width). If QtWebEngine is not ready yet it still produces a paginated
    reportlab PDF with the same paper size and margins.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas as pdf_canvas

    ctx.status(i18n.tr("action.writing", name=out_path.name))
    options = render.print_options()
    html = render.plain_text_to_html(text, out_path.stem, options)
    if render.html_to_pdf(
        html, out_path, title=out_path.stem, options=options,
        page_numbers=page_numbers,
    ):
        ctx.progress(1.0)
        return out_path

    page_width, page_height = render.page_size_points(options["page_size"])
    left, top, right, bottom = render.margins_to_points(options["margins_mm"])
    if page_numbers is None:
        page_numbers = bool(options.get("page_numbers", True))
    font_size = 10.0
    leading = 13.5
    font_name = "Courier"
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        font_name = _pdf_mono_font(text)
    char_width = pdfmetrics.stringWidth("M", font_name, font_size)
    usable = page_width - left - right
    max_chars = max(20, int(usable / char_width)) if char_width else 84
    wrapped: list[str] = []
    for raw_line in text.replace("\t", "    ").splitlines():
        line = raw_line
        while len(line) > max_chars:
            wrapped.append(line[:max_chars])
            line = line[max_chars:]
        wrapped.append(line)
    pdf = pdf_canvas.Canvas(str(out_path), pagesize=(page_width, page_height))
    pdf.setFont(font_name, font_size)
    y = page_height - top
    for line in wrapped:
        if ctx.cancelled():
            pdf.save()
            out_path.unlink(missing_ok=True)
            raise EngineError(i18n.tr("err.cancelled"))
        if y < bottom:
            pdf.showPage()
            pdf.setFont(font_name, font_size)
            y = page_height - top
        pdf.drawString(left, y, line)
        y -= leading
    pdf.save()
    render.postprocess_pdf(
        out_path, title=out_path.stem, page_numbers=bool(page_numbers))
    ctx.progress(1.0)
    return out_path


def txt_to_pdf(path: Path, ctx: Ctx, reserved: set[Path]) -> Path:
    text = path.read_text("utf-8", errors="replace")
    out_path = _unique(path.parent, path.stem, ".pdf", reserved)
    return text_to_pdf(text, out_path, ctx)


def txt_to_image(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> list[Path]:
    from PIL import ImageDraw

    text = path.read_text("utf-8", errors="replace")
    font = _mono_font(15)
    line_height = 20
    max_chars = 100
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\t", "    ")
        while len(line) > max_chars:
            lines.append(line[:max_chars])
            line = line[max_chars:]
        lines.append(line)
    width = 1275
    ext = ".jpg" if target == "jpg" else ".png"
    if len(lines) * line_height > 16000:
        chunks = [lines[index:index + 800] for index in range(0, len(lines), 800)]
    else:
        chunks = [lines]
    outputs: list[Path] = []
    for chunk in chunks:
        height = max(len(chunk) * line_height + 40, 200)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        y = 20
        for line in chunk:
            draw.text((20, y), line, font=font, fill="black")
            y += line_height
        out_path = _unique(path.parent, path.stem, ext, reserved)
        if target == "jpg":
            image.save(out_path, "JPEG", quality=92, optimize=True)
        else:
            image.save(out_path, "PNG", optimize=True)
        outputs.append(out_path)
    ctx.progress(1.0)
    return outputs


def convert_txt(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> list[Path]:
    verify_writable(path)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    if target == "pdf":
        return [txt_to_pdf(path, ctx, reserved)]
    return txt_to_image(path, target, ctx, reserved)


# ---------------------------------------------------------------------------
# Subtitles (SRT / WebVTT / plain text)
# ---------------------------------------------------------------------------

#: Encodings tried in order when reading a subtitle file.
_SUBTITLE_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")
_SUBTITLE_TIME = r"(?:\d{1,2}:)?\d{1,2}:\d{1,2}[,.]\d{1,3}"
_SUBTITLE_CUE_RE = re.compile(
    rf"^({_SUBTITLE_TIME})\s*-->\s*({_SUBTITLE_TIME})\s*(.*)$"
)


def _read_subtitle_text(path: Path) -> str:
    """Decode subtitle bytes tolerantly (BOM, UTF-8, CP1252) and normalise CRLF."""
    data = path.read_bytes()
    for encoding in _SUBTITLE_ENCODINGS:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_subtitle_cues(text: str) -> list[tuple[str, str, str]]:
    """Split subtitle text into ``(timestamp, settings, body)`` cues.

    Index lines, VTT cue identifiers and the ``WEBVTT`` header are skipped, so
    the same parser reads both SRT and WebVTT.
    """
    cues: list[tuple[str, str, str]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        match = _SUBTITLE_CUE_RE.match(lines[index].strip())
        if match is None:
            index += 1
            continue
        start, end, settings = match.groups()
        body: list[str] = []
        index += 1
        while index < len(lines) and lines[index].strip():
            body.append(lines[index].strip().lstrip("\ufeff"))
            index += 1
        cues.append(
            (f"{start} --> {end}", settings.strip(), "\n".join(body)))
    return cues


def _subtitle_timestamp(timestamp: str, separator: str) -> str:
    """Rewrite a cue timestamp with *separator* (``,`` SRT, ``.`` WebVTT)."""
    return timestamp.replace(",", separator).replace(".", separator)


def _subtitle_to_vtt(text: str) -> str:
    blocks = ["WEBVTT", ""]
    for timestamp, settings, body in _parse_subtitle_cues(text):
        line = _subtitle_timestamp(timestamp, ".")
        blocks.append(f"{line} {settings}" if settings else line)
        blocks.append(body)
        blocks.append("")
    return "\n".join(blocks).rstrip("\n") + "\n"


def _subtitle_to_srt(text: str) -> str:
    blocks: list[str] = []
    for number, (timestamp, _settings, body) in enumerate(
            _parse_subtitle_cues(text), start=1):
        blocks += [str(number), _subtitle_timestamp(timestamp, ","), body, ""]
    if not blocks:
        return ""
    return "\n".join(blocks).rstrip("\n") + "\n"


def _subtitle_to_txt(text: str) -> str:
    """Plain transcript: cue bodies only, blank runs collapsed to one line."""
    lines: list[str] = []
    for _timestamp, _settings, body in _parse_subtitle_cues(text):
        for line in body.split("\n"):
            line = line.strip()
            if line or (lines and lines[-1]):
                lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def convert_subtitle(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    """Convert an SRT/WebVTT subtitle to VTT, SRT or plain text.

    No external engine is involved; the encoding is detected tolerantly and the
    output is always UTF-8.
    """
    verify_writable(path)
    ctx.status(i18n.tr(
        "action.converting_file_to", name=path.name, target=target.upper()))
    writers = {
        "vtt": _subtitle_to_vtt,
        "srt": _subtitle_to_srt,
        "txt": _subtitle_to_txt,
    }
    writer = writers.get(target)
    if writer is None:
        raise EngineError(i18n.tr("err.no_engine", name=path.name))
    out_path = _unique(path.parent, path.stem, f".{target}", reserved)
    out_path.write_text(writer(_read_subtitle_text(path)), "utf-8")
    ctx.progress(1.0)
    return out_path


# ---------------------------------------------------------------------------
# Archives
# ---------------------------------------------------------------------------

def _check_extract_size(total: int) -> None:
    if total > _MAX_EXTRACT_BYTES:
        raise EngineError(i18n.tr("err.archive_too_large"))


def _validate_path_safety(dest: Path, relative_name: str) -> None:
    dest_resolved = dest.resolve()
    target = (dest / relative_name).resolve()
    if not (target == dest_resolved or target.is_relative_to(dest_resolved)):
        raise EngineError(i18n.tr("err.archive_traversal", name=relative_name))


def _extract_tar(archive: tarfile.TarFile, dest: Path) -> None:
    for member in archive.getmembers():
        _validate_path_safety(dest, member.name)
    try:
        archive.extractall(dest, filter="data")
    except TypeError:
        archive.extractall(dest)


def _looks_like_tar(data: bytes) -> bool:
    return len(data) >= 262 and data[257:262] == b"ustar"


def _extract_archive(path: Path, dest: Path, ctx: Ctx) -> None:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            _check_extract_size(sum(info.file_size for info in archive.infolist()))
            for info in archive.infolist():
                _validate_path_safety(dest, info.filename)
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            archive.extractall(dest)
        return
    if suffix == ".rar":
        unrar = unrar_path()
        if not unrar:
            raise EngineError(i18n.tr("err.rar_missing_reader"))
        if ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        code = run_process([unrar, "x", "-y", str(path), str(dest) + os.sep], cancel=ctx.cancel)
        if code == -9:
            raise EngineError(i18n.tr("err.cancelled"))
        if code != 0:
            raise EngineError(i18n.tr("err.rar_extract"))
        return
    if suffix == ".tar":
        with tarfile.open(path, "r:") as archive:
            _check_extract_size(sum(member.size for member in archive.getmembers()))
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            _extract_tar(archive, dest)
        return
    if suffix == ".gz":
        _extract_gzip(path, dest, ctx)
        return
    raise EngineError(i18n.tr("err.archive_unsupported", name=path.name))


def _extract_gzip(path: Path, dest: Path, ctx: Ctx) -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            _check_extract_size(sum(member.size for member in archive.getmembers()))
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            _extract_tar(archive, dest)
        return
    except tarfile.TarError:
        pass
    inner_name = path.stem if path.stem else "payload"
    payload_path = dest / inner_name
    total = 0
    with gzip.open(path, "rb") as src, open(payload_path, "wb") as dst:
        head = src.read(_GZ_SNIFF_BYTES)
        dst.write(head)
        total = len(head)
        if total > _MAX_EXTRACT_BYTES:
            raise EngineError(i18n.tr("err.archive_too_large"))
        while True:
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_EXTRACT_BYTES:
                raise EngineError(i18n.tr("err.archive_too_large"))
            dst.write(chunk)
    if _looks_like_tar(head) or (total <= _GZ_SNIFF_BYTES and tarfile.is_tarfile(payload_path)):
        with tarfile.open(payload_path, "r:") as archive:
            if ctx.cancelled():
                raise EngineError(i18n.tr("err.cancelled"))
            _extract_tar(archive, dest)
        payload_path.unlink(missing_ok=True)


def _create_archive(dest_archive: Path, source_dir: Path, ctx: Ctx) -> None:
    suffix = dest_archive.suffix.lower()
    entries = sorted(source_dir.iterdir())
    if suffix == ".zip":
        with zipfile.ZipFile(dest_archive, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in entries:
                for file in [entry] if entry.is_file() else entry.rglob("*"):
                    if file.is_file():
                        archive.write(file, file.relative_to(source_dir))
        return
    if suffix == ".tar":
        with tarfile.open(dest_archive, "w:") as archive:
            for entry in entries:
                archive.add(entry, arcname=entry.name)
        return
    if suffix == ".gz":
        with tarfile.open(dest_archive, "w:gz") as archive:
            for entry in entries:
                archive.add(entry, arcname=entry.name)
        return
    if suffix == ".rar":
        rar = rar_path()
        if not rar:
            raise EngineError(i18n.tr("err.rar_missing_writer"))
        names = [
            f".\\{entry.name}" if entry.name.startswith(("-", "@")) else entry.name
            for entry in entries
        ]
        if not names:
            raise EngineError(i18n.tr("err.archive_repack"))
        if ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        code = run_process([rar, "a", "-m0", "-ep1", "-y", str(dest_archive), *names], cwd=str(source_dir), cancel=ctx.cancel)
        if code == -9:
            raise EngineError(i18n.tr("err.cancelled"))
        if code not in (0, 1):
            raise EngineError(i18n.tr("err.rar_create"))
        return
    raise EngineError(i18n.tr("err.archive_target", name=dest_archive.name))


def convert_archive(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> Path:
    verify_writable(path)
    ctx.status(i18n.tr(
        "action.repackaging", name=path.name, target=target.upper()))
    tmp_dir = Path(tempfile.mkdtemp(prefix="tangerine_arc_"))
    extract_dir = tmp_dir / "content"
    extract_dir.mkdir()
    suffix = ".tar.gz" if target == "gz" else f".{target}"
    out_path = _unique(path.parent, path.stem, suffix, reserved)
    try:
        _extract_archive(path, extract_dir, ctx)
        if ctx.cancelled():
            raise EngineError(i18n.tr("err.cancelled"))
        _create_archive(out_path, extract_dir, ctx)
    except Exception:
        out_path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if not out_path.exists() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise EngineError(i18n.tr("err.archive_repack"))
    ctx.progress(1.0)
    return out_path


def extract_archive(path: Path, ctx: Ctx, reserved: set[Path]) -> Path:
    verify_writable(path)
    name = path.name
    if name.lower().endswith(".tar.gz"):
        stem = name[: -len(".tar.gz")]
    else:
        stem = path.stem
    directory = path.parent / stem
    index = 2
    while directory.exists():
        directory = path.parent / f"{stem} {index}"
        index += 1
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tangerine_extract_", dir=str(path.parent)))
    ctx.status(i18n.tr("action.extracting", name=path.name))
    try:
        _extract_archive(path, tmp_dir, ctx)
        os.replace(tmp_dir, directory)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    ctx.progress(1.0)
    return directory


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def convert_single(path: Path, target: str, ctx: Ctx, reserved: set[Path]) -> list[Path]:
    if not path.exists():
        raise EngineError(i18n.tr("err.source_missing", name=path.name))
    family = family_of(path)
    if family == FAMILY_IMAGE:
        if target == "docx":
            return [image_to_docx(path, ctx, reserved)]
        return [convert_image(path, target, ctx, reserved)]
    if family == FAMILY_AUDIO:
        return [convert_audio(path, target, ctx, reserved)]
    if family == FAMILY_VIDEO:
        return [convert_video(path, target, ctx, reserved)]
    if family == FAMILY_GIF:
        return [convert_gif(path, target, ctx, reserved)]
    if family == FAMILY_PDF:
        return convert_pdf(path, target, ctx, reserved)
    if family == FAMILY_TXT:
        return convert_txt(path, target, ctx, reserved)
    if family == FAMILY_SUB:
        return [convert_subtitle(path, target, ctx, reserved)]
    if family == FAMILY_DOC:
        from . import documents

        return documents.convert_document(path, target, ctx, reserved)
    if family == FAMILY_ARCHIVE:
        return [convert_archive(path, target, ctx, reserved)]
    raise EngineError(i18n.tr("err.no_engine", name=path.name))
