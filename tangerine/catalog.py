"""Format families, conversion targets and file tools - mirrors the macOS spec."""

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from . import media

RASTER_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".avif", ".heic", ".heif", ".tiff", ".tif", ".bmp", ".dib", ".ico"}
SVG_EXTS = {".svg"}
IMAGE_EXTS = RASTER_EXTS | SVG_EXTS
GIF_EXTS = {".gif"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".aif", ".wma"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".m4v"}
PDF_EXTS = {".pdf"}
TXT_EXTS = {".txt"}
SUB_EXTS = {".srt", ".vtt"}
DOC_EXTS = {".docx", ".xlsx", ".pptx", ".csv", ".rtf", ".md", ".odt", ".epub"}
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".rar"}

DOC_OFFICE_EXTS = {".docx", ".xlsx", ".pptx"}

DOCX_OUT_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
DOCX_OUT_PDF_EXTS = {".pdf"}
TXT_OUT_PDF_EXTS = {".pdf"}

IMAGE_TARGETS = ["jpg", "png", "webp", "avif", "heic", "tiff", "pdf"]
AUDIO_TARGETS = ["mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma"]
VIDEO_TARGETS = ["mp4", "mov", "mkv", "webm", "avi", "wmv", "gif", "mp3", "m4a"]
GIF_TARGETS = ["mp4", "mov", "mkv", "webm", "avi", "wmv"]
ARCHIVE_TARGETS = ["zip", "tar", "gz", "rar"]
PDF_TARGETS = ["docx", "jpg", "png", "txt"]
TXT_TARGETS = ["pdf", "jpg", "png"]
IMAGE_DOC_TARGETS = ["pdf", "docx"]

#: Subtitle targets per source extension; subtitles need no external engine.
SUB_TARGETS = {
    ".srt": ("vtt", "txt"),
    ".vtt": ("srt", "txt"),
}

#: Targets that only FFmpeg can produce.
FFMPEG_TARGETS = {
    "mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma",
    "mp4", "mov", "mkv", "gif", "webm", "avi", "wmv",
}

DOC_CONVERSIONS = {
    ".docx": ("txt", "pdf", "jpg", "png"),
    ".xlsx": ("csv", "pdf", "jpg", "png"),
    ".pptx": ("txt", "pdf", "jpg", "png"),
    ".csv": ("xlsx", "pdf", "jpg", "png", "txt"),
    ".rtf": ("txt", "pdf", "jpg", "png"),
    ".md": ("txt", "html", "pdf", "jpg", "png"),
    ".odt": ("txt", "pdf", "jpg", "png"),
    ".epub": ("txt",),
}

DOC_READER_ENGINES = {
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".rtf": "rtf",
    ".md": "markdown",
    ".odt": "odt",
}

DOC_TARGET_ENGINES = {
    "xlsx": ("xlsx",),
    "html": ("markdown",),
    "pdf": ("reportlab",),
    "jpg": ("reportlab", "pdfium"),
    "png": ("reportlab", "pdfium"),
}

DOC_TARGET_LABELS = {
    "txt": "Text File",
    "pdf": "PDF",
    "jpg": "JPG",
    "png": "PNG",
    "csv": "CSV",
    "xlsx": "Excel",
    "html": "HTML",
}

FAMILY_IMAGE = "image"
FAMILY_GIF = "gif"
FAMILY_AUDIO = "audio"
FAMILY_VIDEO = "video"
FAMILY_PDF = "pdf"
FAMILY_TXT = "txt"
FAMILY_SUB = "sub"
FAMILY_DOC = "doc"
FAMILY_ARCHIVE = "archive"


@dataclass(frozen=True)
class Conversion:
    id: str
    label: str
    target_ext: str
    engine: str
    family: str


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    family: str
    batch: bool = False
    engines: tuple[str, ...] = ()


def family_of(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in RASTER_EXTS or ext in SVG_EXTS:
        return FAMILY_IMAGE
    if ext in GIF_EXTS:
        return FAMILY_GIF
    if ext in AUDIO_EXTS:
        return FAMILY_AUDIO
    if ext in VIDEO_EXTS:
        return FAMILY_VIDEO
    if ext in PDF_EXTS:
        return FAMILY_PDF
    if ext in SUB_EXTS:
        return FAMILY_SUB
    if ext in TXT_EXTS:
        return FAMILY_TXT
    if ext in DOC_EXTS:
        return FAMILY_DOC
    if ext in ARCHIVE_EXTS:
        return FAMILY_ARCHIVE
    return None


def is_archive(name: str) -> bool:
    return Path(name).suffix.lower() in ARCHIVE_EXTS


_ENGINES: set[str] | None = None


#: Capability name -> import name. The modules themselves are imported lazily
#: where they are used (engines.py, documents.py, render.py, tools.py); this
#: registry exists so availability can be reported without paying that cost.
_ENGINE_MODULES = (
    ("pillow", "PIL"),
    ("heic", "pillow_heif"),
    ("pdfium", "pypdfium2"),
    ("pypdf", "pypdf"),
    ("docx", "docx"),
    ("xlsx", "openpyxl"),
    ("pptx", "pptx"),
    ("rtf", "striprtf"),
    ("odt", "odf"),
    ("markdown", "markdown"),
    ("reportlab", "reportlab"),
    ("qr", "cv2"),
    ("ocr", "rapidocr_onnxruntime"),
)


def _installed(module: str) -> bool:
    """True when *module* is importable, without importing it.

    The catalog is warmed on the GUI thread right after startup. Importing
    the document/OCR/vision stack just to probe it cost ~2.4 s and ~90 MB
    of idle memory; ``find_spec`` answers the same question in microseconds.
    """
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def available_engines() -> set[str]:
    global _ENGINES
    if _ENGINES is not None:
        return _ENGINES
    engines = {name for name, module in _ENGINE_MODULES if _installed(module)}
    if media.ffmpeg_path():
        engines.add("ffmpeg")
    if media.unrar_path():
        engines.add("unrar")
    if media.rar_path():
        engines.add("rar")
    _ENGINES = engines
    return engines


def _conversion(ext: str, target: str, family: str) -> Conversion | None:
    engines = available_engines()
    if target in ("jpg", "png", "tiff", "webp"):
        if "pillow" not in engines:
            return None
    if target in ("heic", "avif") and "heic" not in engines:
        # The pillow-heif plugin registers both the HEIF and AVIF codecs.
        return None
    if target == "pdf":
        if family in (FAMILY_IMAGE, FAMILY_TXT) and "pdfium" not in engines and "pillow" not in engines:
            return None
    if target == "docx" and "docx" not in engines:
        return None
    if target == "txt" and family == FAMILY_PDF and "pypdf" not in engines:
        return None
    if target in FFMPEG_TARGETS and "ffmpeg" not in engines:
        return None
    if target == "rar" and "rar" not in engines:
        return None
    return Conversion(
        id=f"conv:{ext}:{target}",
        label=target.upper(),
        target_ext=target,
        engine="engine",
        family=family,
    )


def _doc_conversion(source_ext: str, target: str, family: str) -> Conversion | None:
    """A document conversion, offered only when reader and writer can run."""
    engines = available_engines()
    reader = DOC_READER_ENGINES.get(source_ext)
    if reader and reader not in engines:
        return None
    if not set(DOC_TARGET_ENGINES.get(target, ())) <= engines:
        return None
    return Conversion(
        id=f"conv:{source_ext.lstrip('.')}:{target}",
        label=DOC_TARGET_LABELS.get(target, target.upper()),
        target_ext=target,
        engine="engine",
        family=family,
    )


def _subtitle_targets(exts: set[str]) -> list[str]:
    """Subtitle targets offered for a selection, skipping formats already present."""
    targets: list[str] = []
    for source in SUB_TARGETS:
        for target in SUB_TARGETS[source]:
            if target not in targets and target not in exts:
                targets.append(target)
    return targets


def _mixed_conversions(paths_: list[Path], families: set) -> list[Conversion]:
    """Targets available for a mixed selection (union, first family first)."""
    if None in families:
        return []
    first = family_of(paths_[0])
    ordered = [first] + [f for f in sorted(families) if f != first]
    merged: dict[str, Conversion] = {}
    for family in ordered:
        subset = [p for p in paths_ if family_of(p) == family]
        for conv in conversions_for(subset):
            merged.setdefault(conv.target_ext, conv)
    return list(merged.values())


def conversions_for(paths_: list[Path]) -> list[Conversion]:
    """Output-format targets offered for the given source selection."""
    if not paths_:
        return []
    families = {family_of(p) for p in paths_}
    if len(families) != 1:
        return _mixed_conversions(paths_, families)
    family = families.pop()
    if family is None:
        return []
    exts = {p.suffix.lower().lstrip(".") for p in paths_}
    results: list[Conversion] = []
    if family == FAMILY_IMAGE:
        has_svg = bool(exts & {e.lstrip(".") for e in SVG_EXTS})
        targets = list(IMAGE_TARGETS)
        if not has_svg:
            targets.append("docx")
        for target in targets:
            if target.lstrip(".") in exts and not has_svg:
                continue
            if target == "heic" and exts == {"heic"}:
                continue
            conv = _conversion("image", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_AUDIO:
        for target in AUDIO_TARGETS:
            if target in exts:
                continue
            conv = _conversion("audio", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_VIDEO:
        for target in VIDEO_TARGETS:
            if target in exts:
                continue
            conv = _conversion("video", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_GIF:
        for target in GIF_TARGETS:
            conv = _conversion("gif", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_PDF:
        for target in PDF_TARGETS:
            conv = _conversion("pdf", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_TXT:
        for target in TXT_TARGETS:
            conv = _conversion("txt", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_SUB:
        for target in _subtitle_targets(exts):
            conv = _conversion("sub", target, family)
            if conv:
                results.append(conv)
    elif family == FAMILY_DOC:
        source_exts = [p.suffix.lower() for p in paths_]
        for target in DOC_CONVERSIONS.get(source_exts[0], ()):
            if any(target not in DOC_CONVERSIONS.get(ext, ()) for ext in source_exts):
                continue
            conv = None
            for ext in source_exts:
                conv = _doc_conversion(ext, target, family)
                if conv is None:
                    break
            if conv:
                results.append(conv)
    elif family == FAMILY_ARCHIVE:
        for target in ARCHIVE_TARGETS:
            if exts == {target}:
                continue
            conv = _conversion("archive", target, family)
            if conv:
                results.append(conv)
    return results


IMAGE_TOOLS = [
    Tool("img.compress", "Compress", FAMILY_IMAGE, batch=True),
    Tool("img.metadata", "Metadata", FAMILY_IMAGE),
    Tool("img.edit", "Edit Photo", FAMILY_IMAGE),
    Tool("img.annotate", "Annotate Photo", FAMILY_IMAGE),
    Tool("img.background", "Add Background", FAMILY_IMAGE),
    Tool("img.crop", "Crop", FAMILY_IMAGE),
    Tool("img.redact", "Redact Photo", FAMILY_IMAGE),
    Tool("img.pdf", "Create PDF", FAMILY_IMAGE, batch=True),
    Tool("img.collage", "Create Collage", FAMILY_IMAGE, batch=True),
]
AUDIO_TOOLS = [
    Tool("aud.compress", "Compress", FAMILY_AUDIO, batch=True),
    Tool("aud.metadata", "Metadata", FAMILY_AUDIO),
    Tool("aud.normalize", "Normalize Volume", FAMILY_AUDIO),
    Tool("aud.visualizer", "Audio Visualizer", FAMILY_AUDIO),
    Tool("aud.trim", "Trim Audio", FAMILY_AUDIO),
    Tool("aud.channels", "Convert Audio Channels", FAMILY_AUDIO),
    Tool("aud.bleep", "Bleep Audio", FAMILY_AUDIO),
]
VIDEO_TOOLS = [
    Tool("vid.compress", "Compress", FAMILY_VIDEO, batch=True),
    Tool("vid.metadata", "Metadata", FAMILY_VIDEO),
    Tool("vid.removeaudio", "Remove Audio", FAMILY_VIDEO),
    Tool("vid.trim", "Trim", FAMILY_VIDEO),
    Tool("vid.crop", "Crop", FAMILY_VIDEO),
    Tool("vid.speed", "Change Speed", FAMILY_VIDEO),
    Tool("vid.snapshots", "Snapshots", FAMILY_VIDEO),
    Tool("vid.split", "Split Video", FAMILY_VIDEO),
    Tool("vid.redact", "Redact Video", FAMILY_VIDEO),
    Tool("vid.join", "Join Videos", FAMILY_VIDEO, batch=True),
]
GIF_TOOLS = [
    Tool("gif.metadata", "Metadata", FAMILY_GIF),
]
PDF_TOOLS = [
    Tool("pdf.compress", "Compress", FAMILY_PDF),
    Tool("pdf.metadata", "Metadata", FAMILY_PDF),
    Tool("pdf.split", "Split PDF", FAMILY_PDF),
    Tool("pdf.qr", "Read QR Codes", FAMILY_PDF),
    Tool("pdf.merge", "Merge into one PDF", FAMILY_PDF, batch=True),
]
ARCHIVE_TOOLS = [Tool("arc.extract", "Extract", FAMILY_ARCHIVE)]
DOC_TOOLS = [Tool("doc.compress", "Compress", FAMILY_DOC)]
NO_OP = [Tool("qr.read", "Read QR Codes", FAMILY_IMAGE, batch=True)]


def tools_for(paths_: list[Path]) -> list[Tool]:
    """File tools offered for the given source selection (including batches)."""
    if not paths_:
        return []
    families = [family_of(p) for p in paths_]
    if any(f is None for f in families):
        return []
    unique = set(families)
    engines = available_engines()

    def filt(tools: list[Tool]) -> list[Tool]:
        out = []
        for tool in tools:
            if tool.engines and not set(tool.engines) <= engines:
                continue
            out.append(tool)
        return out

    if len(paths_) > 1:
        counts = {f: families.count(f) for f in unique}
        tools: list[Tool] = []
        if counts.get(FAMILY_IMAGE):
            tools.append(Tool("img.compress", "Compress", FAMILY_IMAGE, batch=True))
            image_paths = [p for p in paths_ if family_of(p) == FAMILY_IMAGE]
            # SVG sources support crop/background, but the annotate/redact
            # editors operate on raster canvases.
            raster_images = [p for p in image_paths if p.suffix.lower() not in SVG_EXTS]
            # Geometry is per-image: the user must draw a crop/annotation/
            # redaction on each source independently. The dispatcher opens
            # one editor at a time, while tool_paths keeps mixed selections
            # scoped to their images.
            tools.extend(
                Tool(tool.id, tool.label, FAMILY_IMAGE, batch=True)
                for tool in IMAGE_TOOLS
                if tool.id in {"img.crop", "img.background"}
                or (raster_images and tool.id in {"img.annotate", "img.redact"})
            )
            tools.append(Tool("img.pdf", "Create PDF", FAMILY_IMAGE, batch=True))
            if counts[FAMILY_IMAGE] > 1:
                tools.append(Tool("img.collage", "Create Collage", FAMILY_IMAGE, batch=True))
        elif counts.get(FAMILY_GIF):
            tools.append(Tool("img.pdf", "Create PDF", FAMILY_IMAGE, batch=True))
        if counts.get(FAMILY_VIDEO):
            tools.append(Tool("vid.compress", "Compress", FAMILY_VIDEO, batch=True))
            if counts[FAMILY_VIDEO] > 1:
                tools.append(Tool("vid.join", "Join Videos", FAMILY_VIDEO, batch=True))
        if counts.get(FAMILY_AUDIO):
            tools.append(Tool("aud.compress", "Compress", FAMILY_AUDIO, batch=True))
        if counts.get(FAMILY_PDF, 0) > 1:
            tools.append(Tool("pdf.merge", "Merge into one PDF", FAMILY_PDF, batch=True))
        if unique & {FAMILY_IMAGE, FAMILY_GIF, FAMILY_PDF}:
            qr_family = FAMILY_PDF if FAMILY_PDF in unique else FAMILY_IMAGE
            tools.append(Tool("qr.read", "Read QR Codes", qr_family, batch=True))
        return filt(tools)
    family = families[0]
    if family == FAMILY_IMAGE:
        path = paths_[0]
        tools = list(IMAGE_TOOLS)
        if path.suffix.lower() in SVG_EXTS:
            tools = [t for t in tools if t.id in ("img.pdf", "img.crop", "img.background")]
        if path.suffix.lower() in (".bmp",):
            tools = [t for t in tools if t.id not in ("img.metadata",)]
        tools.append(Tool("qr.read", "Read QR Codes", FAMILY_IMAGE))
        return filt(tools)
    if family == FAMILY_GIF:
        return filt(GIF_TOOLS + [Tool("img.pdf", "Create PDF", FAMILY_GIF, batch=True),
                                Tool("qr.read", "Read QR Codes", FAMILY_GIF)])
    if family == FAMILY_AUDIO:
        return filt(AUDIO_TOOLS)
    if family == FAMILY_VIDEO:
        return filt(VIDEO_TOOLS)
    if family == FAMILY_PDF:
        return filt(PDF_TOOLS)
    if family == FAMILY_TXT:
        return filt([Tool("txt.compress", "Compress", FAMILY_TXT)])
    if family == FAMILY_DOC:
        if paths_[0].suffix.lower() in DOC_OFFICE_EXTS:
            return filt(DOC_TOOLS)
        return []
    if family == FAMILY_ARCHIVE:
        return filt(ARCHIVE_TOOLS)
    # Subtitles (FAMILY_SUB) are converted straight to SRT/VTT/TXT: no tools.
    return []


BATCH_TOOL_IDS = {
    "img.compress", "img.crop", "img.annotate", "img.redact", "img.background",
    "img.pdf", "img.collage", "aud.compress", "vid.compress", "vid.join",
    "pdf.merge",
}

#: Families a batch tool applies to; used to filter mixed selections.
_TOOL_FAMILIES = {
    "img.compress": {FAMILY_IMAGE},
    "img.crop": {FAMILY_IMAGE},
    "img.annotate": {FAMILY_IMAGE},
    "img.redact": {FAMILY_IMAGE},
    "img.background": {FAMILY_IMAGE},
    "img.pdf": {FAMILY_IMAGE, FAMILY_GIF},
    "img.collage": {FAMILY_IMAGE},
    "vid.compress": {FAMILY_VIDEO},
    "vid.join": {FAMILY_VIDEO},
    "aud.compress": {FAMILY_AUDIO},
    "pdf.merge": {FAMILY_PDF},
    "qr.read": {FAMILY_IMAGE, FAMILY_GIF, FAMILY_PDF},
}


def tool_paths(key: str, paths_: list[Path]) -> list[Path]:
    """Files of a mixed selection a batch tool actually applies to."""
    families = _TOOL_FAMILIES.get(key)
    if families is None:
        return list(paths_)
    selected = [p for p in paths_ if family_of(p) in families]
    if key in {"img.annotate", "img.redact"}:
        selected = [p for p in selected if p.suffix.lower() not in SVG_EXTS]
    return selected


def conversion_paths(target_ext: str, paths_: list[Path]) -> list[Path]:
    """Files of a mixed selection that can convert to ``target_ext``."""
    return [
        p
        for p in paths_
        if any(c.target_ext == target_ext for c in conversions_for([p]))
    ]


@dataclass(frozen=True)
class ActionItem:
    id: str
    label: str


ACTIONS = [
    ActionItem("act.share", "Share"),
    ActionItem("act.shelf", "Float"),
    ActionItem("act.copy_ref", "Copy Files"),
    ActionItem("act.move", "Move to Folder"),
    ActionItem("act.copy_path", "Copy Path"),
    ActionItem("act.terminal", "Open in Terminal"),
]


def actions_for(paths_: list[Path]) -> list[ActionItem]:
    """Actions offered for the given selection."""
    if not paths_:
        return []
    return list(ACTIONS)
