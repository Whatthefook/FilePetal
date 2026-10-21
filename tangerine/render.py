"""Faithful HTML rendering through QtWebEngine (v1.8+, print polish in v1.9).

Conversions run on worker threads (``jobs.Job``), but Chromium only renders
on the GUI thread: :func:`html_to_pdf` hands the markup to a renderer object
that lives there, waits for ``pdfPrintingFinished`` and reports back, so the
old reportlab text dumps stay only as a fallback.

v1.9 adds the print quality pass shared by every document conversion: an
explicit :class:`QPageLayout` (Qt ignores the CSS ``@page`` margins as soon as
the print layout carries its own), a print stylesheet with widow/orphan and
page-break control, and a best-effort post-process that stamps PDF metadata
and page numbers.

The builders (markdown, docx, xlsx, csv, txt, paragraphs, slides) are pure
Python and can be tested without WebEngine; ``ensure_ready`` must run once
from the GUI thread.
"""

from __future__ import annotations

import csv as _csv
import html as _html
import importlib.util
import io
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QThread, Qt, QTimer, QUrl, Signal

from . import paths

RENDER_TIMEOUT_S = 60.0

#: Paper sizes in millimetres (width, height), portrait.
PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
}
DEFAULT_PAGE_SIZE = "a4"

#: Margin presets in millimetres as (left, top, right, bottom).
MARGIN_PRESETS_MM: dict[str, tuple[float, float, float, float]] = {
    "normal": (16.0, 18.0, 16.0, 18.0),
    "compact": (10.0, 12.0, 10.0, 12.0),
    "wide": (25.0, 20.0, 25.0, 20.0),
}
DEFAULT_MARGIN_PRESET = "normal"

_MM_TO_PT = 72.0 / 25.4

#: x-position of the page-number text, in points from the bottom edge.
_PAGE_NUMBER_Y = 17.0

_PAGE_CSS = """
@page { size: __PAGE_SIZE__; margin: __PAGE_MARGIN__; }
html, body { margin: 0; padding: 0; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt;
       line-height: 1.55; color: #1f2328;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1, h2, h3, h4 { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.25;
                 margin: 1.2em 0 0.5em;
                 page-break-after: avoid; break-after: avoid; }
h1 { font-size: 20pt; border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em; }
h2 { font-size: 15pt; }
h3 { font-size: 13pt; }
h4 { font-size: 11pt; }
p { margin: 0.5em 0; orphans: 2; widows: 2; }
a { color: #0969da; text-decoration: none; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 9.5pt;
       background: #f6f8fa; padding: 0 0.2em; border-radius: 3px; }
pre { font-family: Consolas, 'Courier New', monospace; font-size: 9.5pt;
      background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px;
      padding: 0.7em; white-space: pre-wrap; overflow-wrap: break-word;
      tab-size: 4; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
pre.plain { background: none; border: none; border-radius: 0; padding: 0;
            font-size: 10pt; line-height: 1.45; }
blockquote { margin: 0.6em 0; padding: 0 0.9em; border-left: 3px solid #d0d7de;
             color: #57606a; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 0.7em 0; font-size: 10pt; }
thead { display: table-header-group; }
th, td { border: 1px solid #d0d7de; padding: 0.35em 0.55em; text-align: left;
         vertical-align: top; overflow-wrap: break-word; }
th { background: #f6f8fa; }
tr { page-break-inside: avoid; }
img { max-width: 100%; height: auto; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 1.2em 0; }
ul, ol { padding-left: 1.6em; }
li { margin: 0.15em 0; }
.slide { page-break-before: always; break-before: page; }
.slide:first-of-type { page-break-before: avoid; break-before: auto; }
.slide-number { font-family: 'Segoe UI', Arial, sans-serif; font-size: 8.5pt;
                color: #8b949e; margin: 0 0 0.3em; text-transform: uppercase;
                letter-spacing: 0.08em; }
.slide h1 { font-size: 17pt; border-bottom: none; padding-bottom: 0; }
@media screen {
  body { max-width: 46rem; margin: 2.5rem auto 3rem; padding: 0 1.25rem; }
  pre { overflow-x: auto; }
  table { font-size: 10.5pt; }
  .slide { break-before: auto; page-break-before: auto;
           border-top: 1px solid #d0d7de; margin-top: 2rem; padding-top: 1.2rem; }
  .slide:first-of-type { border-top: none; margin-top: 0; padding-top: 0; }
}
"""


def print_options() -> dict[str, Any]:
    """Print settings (paper, margins, numbering) resolved for this machine."""
    from . import settings

    size = str(settings.get("pdfPageSize", DEFAULT_PAGE_SIZE) or "").lower()
    if size not in PAGE_SIZES_MM:
        size = DEFAULT_PAGE_SIZE
    preset = str(settings.get("pdfMarginPreset", DEFAULT_MARGIN_PRESET) or "").lower()
    if preset not in MARGIN_PRESETS_MM:
        preset = DEFAULT_MARGIN_PRESET
    return {
        "page_size": size,
        "margins_mm": MARGIN_PRESETS_MM[preset],
        "page_numbers": bool(settings.get("pdfPageNumbers", True)),
    }


def _resolve(options: dict[str, Any] | None) -> tuple[str, tuple[float, float, float, float]]:
    if not options:
        return DEFAULT_PAGE_SIZE, MARGIN_PRESETS_MM[DEFAULT_MARGIN_PRESET]
    size = str(options.get("page_size") or DEFAULT_PAGE_SIZE).lower()
    if size not in PAGE_SIZES_MM:
        size = DEFAULT_PAGE_SIZE
    margins = options.get("margins_mm") or MARGIN_PRESETS_MM[DEFAULT_MARGIN_PRESET]
    try:
        left, top, right, bottom = (float(value) for value in margins)
    except (TypeError, ValueError):
        left, top, right, bottom = MARGIN_PRESETS_MM[DEFAULT_MARGIN_PRESET]
    return size, (left, top, right, bottom)


def page_size_points(page_size: str) -> tuple[float, float]:
    """Paper size in PostScript points (width, height)."""
    width, height = PAGE_SIZES_MM.get(page_size, PAGE_SIZES_MM[DEFAULT_PAGE_SIZE])
    return width * _MM_TO_PT, height * _MM_TO_PT


def margins_to_points(
    margins_mm: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) millimetres to points, for reportlab."""
    left, top, right, bottom = margins_mm
    return left * _MM_TO_PT, top * _MM_TO_PT, right * _MM_TO_PT, bottom * _MM_TO_PT


@lru_cache(maxsize=1)
def _pygments_css() -> str:
    try:
        from pygments.formatters import HtmlFormatter
    except Exception:
        return ""
    return HtmlFormatter().get_style_defs(".codehilite")


def print_css(options: dict[str, Any] | None = None) -> str:
    """The print stylesheet with the chosen paper size and margins baked in."""
    page_size, margins_mm = _resolve(options)
    width, height = PAGE_SIZES_MM[page_size]
    left, top, right, bottom = margins_mm
    return _PAGE_CSS.replace(
        "__PAGE_SIZE__", f"{width:g}mm {height:g}mm",
    ).replace(
        "__PAGE_MARGIN__", f"{top:g}mm {right:g}mm {bottom:g}mm {left:g}mm",
    )


def _document(title: str, body: str, options: dict[str, Any] | None = None) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_html.escape(title)}</title>"
        f"<style>{print_css(options)}{_pygments_css()}</style></head>"
        f"<body>{body}</body></html>"
    )


def _title_from_markdown(source: str, fallback: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def markdown_to_html(
    source: str, title: str = "", options: dict[str, Any] | None = None,
) -> str:
    """Render CommonMark/GFM (tables, footnotes, codehilite) to full HTML."""
    import markdown

    body = markdown.markdown(
        source,
        extensions=["extra", "sane_lists", "codehilite"],
        extension_configs={"codehilite": {"guess_lang": False}},
    )
    return _document(title or _title_from_markdown(source, "Document"), body, options)


def docx_to_html(path: Path, title: str = "", options: dict[str, Any] | None = None) -> str:
    """Semantic DOCX rendering through mammoth (images embed as data URIs)."""
    import mammoth

    with open(path, "rb") as handle:
        body = mammoth.convert_to_html(handle).value
    return _document(title or Path(path).stem, body, options)


def xlsx_to_html(path: Path, title: str = "", options: dict[str, Any] | None = None) -> str:
    """Spreadsheet rendering through xlsx2html (styles, merged cells)."""
    from xlsx2html import xlsx2html

    stream = xlsx2html(str(path))
    body = stream.getvalue() if hasattr(stream, "getvalue") else str(stream)
    return _document(title or Path(path).stem, body, options)


def table_to_html(rows: list[list[str]]) -> str:
    if not rows:
        return "<p></p>"
    head, *rest = rows
    head_cells = "".join(f"<th>{_html.escape(cell)}</th>" for cell in head)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{_html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rest
    )
    return f"<table><thead><tr>{head_cells}</tr></thead><tbody>{body_rows}</tbody></table>"


def csv_to_html(path: Path, title: str = "", options: dict[str, Any] | None = None) -> str:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        rows = [row for row in _csv.reader(handle)]
    return _document(title or Path(path).stem, table_to_html(rows), options)


def plain_text_to_html(
    text: str, title: str = "", options: dict[str, Any] | None = None,
) -> str:
    """Plain text keeps its columns: a wrapped monospace block, no reflow."""
    body = f"<pre class='plain'>{_html.escape(text.rstrip())}</pre>"
    return _document(title or "Text", body, options)


def paragraphs_to_html(
    text: str, title: str = "", options: dict[str, Any] | None = None,
) -> str:
    """Flowing prose from extracted text (RTF/ODT): blank lines break pages of prose."""
    blocks = [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    parts: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        parts.append("<p>" + "<br>".join(_html.escape(line) for line in lines) + "</p>")
    return _document(title or "Document", "".join(parts) or "<p></p>", options)


def slides_to_html(
    slides: list[tuple[str, list[str]]],
    title: str = "",
    options: dict[str, Any] | None = None,
) -> str:
    """Approximate PowerPoint rendering: one section per slide, title + bullets."""
    parts: list[str] = []
    for number, (slide_title, bullets) in enumerate(slides, start=1):
        chunk = [f"<section class='slide'><p class='slide-number'>Slide {number}</p>"]
        if slide_title:
            chunk.append(f"<h1>{_html.escape(slide_title)}</h1>")
        if bullets:
            items = "".join(f"<li>{_html.escape(bullet)}</li>" for bullet in bullets)
            chunk.append(f"<ul>{items}</ul>")
        chunk.append("</section>")
        parts.append("".join(chunk))
    return _document(title or "Presentation", "".join(parts) or "<p></p>", options)


# ---------------------------------------------------------------------------
# PDF post-process: metadata + page numbers (best effort, never fatal)
# ---------------------------------------------------------------------------

def _page_number_overlay(page, index: int, total: int):
    try:
        from pypdf import PdfReader
        from reportlab.pdfgen import canvas as pdf_canvas
    except Exception:
        return None
    try:
        if int(page.get("/Rotate", 0) or 0) % 360:
            return None
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        buffer = io.BytesIO()
        canvas = pdf_canvas.Canvas(buffer, pagesize=(width, height))
        canvas.setFont("Helvetica", 9)
        canvas.setFillGray(0.35)
        canvas.drawCentredString(width / 2.0, _PAGE_NUMBER_Y, f"{index} / {total}")
        canvas.save()
        buffer.seek(0)
        return PdfReader(buffer).pages[0]
    except Exception:
        return None


def postprocess_pdf(path: Path, *, title: str = "", page_numbers: bool = True) -> bool:
    """Stamp metadata (title/author) and ``n / total`` numbers on every page.

    Failures are silent by design: the rendered PDF is already a valid result.
    """
    path = Path(path)
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return False
    tmp = path.with_name(path.name + ".tmp")
    try:
        reader = PdfReader(str(path))
        total = len(reader.pages)
        if not total:
            return False
        writer = PdfWriter()
        numbered = bool(page_numbers) and total > 1
        for index, page in enumerate(reader.pages, start=1):
            added = writer.add_page(page)
            if numbered:
                overlay = _page_number_overlay(page, index, total)
                if overlay is not None:
                    added.merge_page(overlay)
        writer.add_metadata({
            "/Title": title or path.stem,
            "/Author": "FilePetal",
            "/Creator": "FilePetal",
            "/Producer": f"FilePetal {paths.APP_VERSION}",
        })
        with open(tmp, "wb") as handle:
            writer.write(handle)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------------------
# QtWebEngine renderer
# ---------------------------------------------------------------------------

def _make_layout(page_size: str, margins_mm: tuple[float, float, float, float]):
    """Explicit page layout; Qt ignores the CSS ``@page`` margin without it."""
    try:
        from PySide6.QtCore import QMarginsF
        from PySide6.QtGui import QPageLayout, QPageSize
    except Exception:
        return None
    size_id = (
        QPageSize.PageSizeId.A4 if page_size == "a4" else QPageSize.PageSizeId.Letter
    )
    left, top, right, bottom = margins_mm
    try:
        return QPageLayout(
            QPageSize(size_id),
            QPageLayout.Orientation.Portrait,
            QMarginsF(left, top, right, bottom),
            QPageLayout.Unit.Millimeter,
        )
    except Exception:
        return None


class _RenderJob:
    __slots__ = (
        "html", "out", "title", "page_size", "margins_mm", "page_numbers",
        "done", "success",
    )

    def __init__(
        self,
        html: str,
        out: Path,
        *,
        title: str = "",
        page_size: str = DEFAULT_PAGE_SIZE,
        margins_mm: tuple[float, float, float, float] | None = None,
        page_numbers: bool = True,
    ) -> None:
        self.html = html
        self.out = out
        self.title = title
        self.page_size = page_size
        self.margins_mm = margins_mm or MARGIN_PRESETS_MM[DEFAULT_MARGIN_PRESET]
        self.page_numbers = page_numbers
        self.done = threading.Event()
        self.success = False


class _WebEngineRenderer(QObject):
    """Lives on the GUI thread; workers submit jobs through the signal."""

    _request = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._page = None
        self._request.connect(self._render, Qt.ConnectionType.QueuedConnection)

    def render(self, job: _RenderJob) -> bool:
        with self._lock:
            # Already on the renderer thread (GUI): run directly, waiting for a
            # queued call would block the event loop the render needs.
            if QThread.currentThread() is self.thread():
                self._render(job)
            else:
                self._request.emit(job)
                if not job.done.wait(RENDER_TIMEOUT_S):
                    return False
            if not job.success:
                return False
            postprocess_pdf(
                job.out, title=job.title, page_numbers=job.page_numbers)
            return True

    def _render(self, job: _RenderJob) -> None:
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage
        except Exception:
            job.done.set()
            return
        page = QWebEnginePage()
        self._page = page
        layout = _make_layout(job.page_size, job.margins_mm)
        loop = QEventLoop()
        state = {"done": False, "success": False}

        def finish() -> None:
            if not state["done"]:
                state["done"] = True
                loop.quit()

        def on_pdf(path: str, success: bool) -> None:
            state["success"] = bool(success) and Path(path) == Path(job.out)
            finish()

        def on_load(ok: bool) -> None:
            if not ok:
                finish()
                return
            page.pdfPrintingFinished.connect(on_pdf)
            if layout is not None:
                page.printToPdf(str(job.out), layout)
            else:
                page.printToPdf(str(job.out))
            QTimer.singleShot(45000, finish)

        page.loadFinished.connect(on_load)
        page.setHtml(job.html, QUrl("about:blank"))
        QTimer.singleShot(30000, finish)
        loop.exec()
        self._page = None
        job.success = state["success"]
        job.done.set()


_renderer: _WebEngineRenderer | None = None
_ready_lock = threading.Lock()


def ensure_ready() -> bool:
    """Create the renderer; must be called once from the GUI thread."""
    global _renderer
    with _ready_lock:
        if _renderer is not None:
            return True
        if importlib.util.find_spec("PySide6.QtWebEngineCore") is None:
            return False
        try:
            _renderer = _WebEngineRenderer()
        except Exception:
            _renderer = None
            return False
        return True


def available() -> bool:
    if _renderer is not None:
        return True
    return importlib.util.find_spec("PySide6.QtWebEngineCore") is not None


def html_to_pdf(
    html: str,
    out: Path,
    *,
    title: str = "",
    options: dict[str, Any] | None = None,
    page_numbers: bool | None = None,
) -> bool:
    """Render markup to PDF on the GUI thread; False means "use fallback"."""
    renderer = _renderer
    if renderer is None:
        return False
    page_size, margins_mm = _resolve(options)
    if page_numbers is None:
        page_numbers = bool((options or {}).get("page_numbers", True))
    job = _RenderJob(
        html,
        Path(out),
        title=title,
        page_size=page_size,
        margins_mm=margins_mm,
        page_numbers=page_numbers,
    )
    return renderer.render(job)
