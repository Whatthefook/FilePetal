"""Create one PDF from one or more selected image files."""

from __future__ import annotations

import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import i18n
from .catalog import GIF_EXTS, RASTER_EXTS, SVG_EXTS

if TYPE_CHECKING:
    from .engines import Ctx


_PDF_IMAGE_EXTS = set(RASTER_EXTS) | set(SVG_EXTS) | set(GIF_EXTS) | {
    ".jpe", ".jfif", ".dib", ".ico",
}
_NATURAL_PARTS = re.compile(r"(\d+)")
_RESERVED_LOCK = threading.Lock()
# Five retries with 1.0 second total backoff. WinError 5 can be transient on
# Windows when another process briefly denies replacement; persistent access
# errors still surface after the bounded retry window.
_PUBLISH_RETRY_DELAYS = (0.05, 0.10, 0.20, 0.25, 0.40)
_PUBLISH_RETRYABLE_WINERRORS = frozenset({5, 32})


@dataclass(frozen=True)
class PdfOptions:
    order: str = "received"
    rows: int = 1
    columns: int = 1
    with_filenames: bool = False
    font_scale: float = 1.0
    output: Path | None = None


def is_pdf_image(path: str | Path) -> bool:
    """Return whether the filename extension is supported by the PDF action."""
    return Path(path).suffix.casefold() in _PDF_IMAGE_EXTS


def _natural_key(path: Path) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in _NATURAL_PARTS.split(path.name)
    )


def ordered_paths(paths: list[Path], order: str) -> list[Path]:
    """Apply the selected page order; manual means the caller's supplied order."""
    if order not in {"received", "name", "manual"}:
        raise ValueError(f"Unsupported image PDF order: {order}")
    if order == "name":
        return sorted(paths, key=lambda path: (_natural_key(path), path.name.casefold()))
    return list(paths)


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _deduplicate(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw)
        canonical = _canonical(path)
        key = os.path.normcase(str(canonical))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _check_cancel(ctx: Ctx) -> None:
    from .engines import EngineError

    if ctx.cancelled():
        raise EngineError(i18n.tr("err.cancelled"))


def _prepare_image(path: Path, with_filename: bool, font_scale: float) -> Image.Image:
    """Load through the shared engine so HEIF and SVG use app codecs."""
    from . import engines

    source = engines.load_image(path)
    image = source
    try:
        oriented = ImageOps.exif_transpose(image)
        if oriented is not image:
            image.close()
            image = oriented

        has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
        if has_alpha:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            try:
                flattened = Image.alpha_composite(background, rgba).convert("RGB")
            finally:
                background.close()
                rgba.close()
            image.close()
            image = flattened
        elif image.mode != "RGB":
            converted = image.convert("RGB")
            image.close()
            image = converted

        if not with_filename:
            result = image
            image = None
            return result

        size = max(8, min(72, round(14 * font_scale)))
        font = ImageFont.load_default(size=size)
        margin = max(6, round(size * 0.65))
        while size > 8:
            bbox = font.getbbox(path.name)
            if bbox[2] - bbox[0] <= image.width - margin * 2:
                break
            size -= 1
            font = ImageFont.load_default(size=size)
        bbox = font.getbbox(path.name)
        band_height = max(size + margin * 2, bbox[3] - bbox[1] + margin * 2)
        labeled = Image.new("RGB", (image.width, image.height + band_height), "white")
        labeled.paste(image, (0, 0))
        draw = ImageDraw.Draw(labeled)
        draw.text((margin, image.height + margin - bbox[1]), path.name, fill="black", font=font)
        result = labeled
        image.close()
        image = None
        return result
    finally:
        if image is not None:
            image.close()


def _compose_grid(images: list[Image.Image], rows: int, columns: int) -> Image.Image:
    cell_width = max(image.width for image in images)
    cell_height = max(image.height for image in images)
    sheet = Image.new("RGB", (cell_width * columns, cell_height * rows), "white")
    try:
        for index, image in enumerate(images):
            thumbnail = ImageOps.contain(
                image, (cell_width, cell_height), method=Image.Resampling.LANCZOS,
            )
            try:
                x = (index % columns) * cell_width + (cell_width - thumbnail.width) // 2
                y = (index // columns) * cell_height + (cell_height - thumbnail.height) // 2
                sheet.paste(thumbnail, (x, y))
            finally:
                if thumbnail is not image:
                    thumbnail.close()
        return sheet
    except Exception:
        sheet.close()
        raise


def _output_candidate(paths: list[Path], options: PdfOptions) -> tuple[Path, bool]:
    if options.output is not None:
        return _canonical(Path(options.output)), True
    first = paths[0]
    stem = first.stem if len(paths) == 1 else f"{first.stem} PDF"
    return first.parent / f"{stem}.pdf", False


def _reserved_keys(reserved: set[Path]) -> set[str]:
    return {os.path.normcase(str(_canonical(path))) for path in reserved}


def _reserve_output(
    candidate: Path,
    explicit: bool,
    reserved: set[Path],
) -> tuple[Path, tuple[int, int, bytes]]:
    """Claim a sibling name and return its path plus the placeholder file identity."""
    from .engines import EngineError

    candidate.parent.mkdir(parents=True, exist_ok=True)
    stem, suffix = candidate.stem, candidate.suffix or ".pdf"
    number = 1
    while True:
        path = candidate if number == 1 else candidate.with_name(f"{stem} {number}{suffix}")
        path = _canonical(path)
        key = os.path.normcase(str(path))
        with _RESERVED_LOCK:
            reserved_keys = _reserved_keys(reserved)
            if key in reserved_keys:
                if explicit:
                    raise EngineError(i18n.tr("err.output_exists", name=path.name))
                number += 1
                continue
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            except FileExistsError as exc:
                if explicit:
                    raise EngineError(i18n.tr("err.output_exists", name=path.name)) from exc
                number += 1
                continue
            else:
                try:
                    marker = os.urandom(32)
                    if os.write(descriptor, marker) != len(marker):
                        raise OSError("Could not write the PDF output reservation marker")
                    identity = os.fstat(descriptor)
                finally:
                    os.close(descriptor)
                reserved.add(path)
                return path, (identity.st_dev, identity.st_ino, marker)


def _owns_output_reservation(path: Path, identity: tuple[int, int, bytes]) -> bool:
    """Check the reserved directory entry still refers to our placeholder."""
    descriptor = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        current = os.fstat(descriptor)
        marker = os.read(descriptor, len(identity[2]))
    except OSError:
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return (current.st_dev, current.st_ino, marker) == identity


def _replace_with_retry(
    source: Path,
    destination: Path,
    reservation: tuple[int, int, bytes],
    ctx: Ctx,
) -> None:
    """Atomically publish a PDF, retrying only transient Windows sharing errors."""
    for attempt in range(len(_PUBLISH_RETRY_DELAYS) + 1):
        _check_cancel(ctx)
        if not _owns_output_reservation(destination, reservation):
            raise OSError(f"Reserved PDF output changed before publication: {destination.name}")
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            # ERROR_LOCK_VIOLATION (33) describes a byte-range lock, not the
            # sharing denial (32) that can temporarily block a rename. Do not
            # retry 33 or generic errno values such as POSIX EIO (5).
            _check_cancel(ctx)
            if (getattr(exc, "winerror", None) not in _PUBLISH_RETRYABLE_WINERRORS
                    or attempt == len(_PUBLISH_RETRY_DELAYS)):
                raise
            delay = _PUBLISH_RETRY_DELAYS[attempt]
            if ctx.cancel is None:
                time.sleep(delay)
            elif ctx.cancel.wait(delay):
                _check_cancel(ctx)


def create_image_pdf(
    paths: list[Path],
    ctx: Ctx,
    reserved: set[Path] | None = None,
    options: PdfOptions | None = None,
) -> Path:
    """Create a PDF atomically; one source per page unless grid layout is set."""
    from .engines import EngineError

    options = options or PdfOptions()
    if options.order not in {"received", "name", "manual"}:
        raise ValueError(f"Unsupported image PDF order: {options.order}")
    if (isinstance(options.rows, bool) or not isinstance(options.rows, int)
            or isinstance(options.columns, bool) or not isinstance(options.columns, int)
            or options.rows < 1 or options.columns < 1):
        raise ValueError("PDF rows and columns must be positive integers.")
    if not math.isfinite(options.font_scale) or options.font_scale <= 0:
        raise ValueError("PDF filename font scale must be a positive finite number.")

    sources = _deduplicate([Path(path) for path in paths])
    if not sources:
        raise EngineError(i18n.tr("err.no_images"))
    for path in sources:
        if not is_pdf_image(path):
            raise EngineError(i18n.tr(
                "err.read_image", name=path.name,
                detail=i18n.tr("err.pdf_image_unsupported"),
            ))

    ordered = ordered_paths(sources, options.order)
    outputs = reserved if reserved is not None else set()
    pages: list[Image.Image] = []
    pdf_pages: list[Image.Image] = []
    output: Path | None = None
    reservation: tuple[int, int, bytes] | None = None
    temp_path: Path | None = None
    published = False
    try:
        ctx.status(i18n.tr("action.creating_pdf"))
        total = len(ordered)
        for index, path in enumerate(ordered, start=1):
            _check_cancel(ctx)
            ctx.status(i18n.tr(
                "action.converting_progress", name=path.name, index=index, total=total,
            ))
            pages.append(_prepare_image(path, options.with_filenames, options.font_scale))
            ctx.progress(0.80 * index / total)
        _check_cancel(ctx)

        capacity = options.rows * options.columns
        if capacity == 1:
            pdf_pages = list(pages)
        else:
            for start in range(0, total, capacity):
                _check_cancel(ctx)
                pdf_pages.append(_compose_grid(
                    pages[start:start + capacity], options.rows, options.columns,
                ))
        _check_cancel(ctx)

        candidate, explicit = _output_candidate(ordered, options)
        output, reservation = _reserve_output(candidate, explicit, outputs)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{output.stem}.", suffix=".tmp", dir=output.parent,
        )
        os.close(descriptor)
        temp_path = Path(temp_name)
        ctx.status(i18n.tr("action.creating_pdf"))
        ctx.progress(0.9)
        _check_cancel(ctx)
        pdf_pages[0].save(
            temp_path, "PDF", resolution=150.0,
            save_all=True, append_images=pdf_pages[1:],
        )
        _check_cancel(ctx)
        _replace_with_retry(temp_path, output, reservation, ctx)
        temp_path = None
        published = True
        ctx.progress(1.0)
        return output
    except EngineError:
        raise
    except Exception as exc:
        name = output.name if output is not None else "PDF"
        raise EngineError(i18n.tr("err.save_image", name=name, detail=exc)) from exc
    finally:
        for image in {id(image): image for image in [*pdf_pages, *pages]}.values():
            try:
                image.close()
            except Exception:
                pass
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                # Preserve the conversion/publication error if Windows still
                # has the temporary file open; cleanup is best effort here.
                pass
        if output is not None and not published:
            with _RESERVED_LOCK:
                if reservation is not None and _owns_output_reservation(output, reservation):
                    try:
                        output.unlink(missing_ok=True)
                    except OSError:
                        pass
                outputs.discard(output)
