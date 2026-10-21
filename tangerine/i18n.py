"""Internationalization for Tangerine (English + Spanish).

The active language is stored in the persistent settings under the
``language`` key.  Besides explicit codes from :data:`LANGUAGES` the special
value ``"system"`` resolves through :class:`QLocale` (e.g. ``es_MX`` -> ``es``)
and falls back to English when the locale is not supported.

Lookups use semantic ids such as ``"wheel.convert"`` or ``"tool.img.compress"``
and follow the chain *current language -> English -> the key itself*.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QLocale

log = logging.getLogger("tangerine")

LANGUAGES = [("en", "English"), ("es", "Español")]
DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # -- app / wheel / tray -------------------------------------------
        "app.name": "FilePetal",
        "wheel.convert": "Convert",
        "wheel.actions": "Actions",
        "wheel.tools": "Tools",
        "wheel.drop_file": "Drop a file here",
        "wheel.files_count": "{n} files",
        "tray.active": "Active",
        "tray.nothing_active": "Nothing active",
        "tray.settings": "Settings...",
        "tray.check_updates": "Check for Updates...",
        "tray.quit": "Quit FilePetal",
        "tray.working": "Working",
        "tray.tooltip": "FilePetal",
        "tray.welcome": (
            "Drag files from an Explorer window while holding Shift to convert them.\n"
            "Hold Alt+Shift instead for file tools like Compress, Crop, or Trim."
        ),
        "tray.already_running": "FilePetal is already running.",
        "tray.settings_unavailable": (
            "The settings window is not available in this build."
        ),
        "tray.update_message": (
            "FilePetal {version} for Windows\n\n"
            "This is a local build, so update checks are handled manually."
        ),
        "tray.quit_running": "Conversions are still running. Quit anyway?",
        # -- actions ------------------------------------------------------
        "action.file_to": "{name} → {target}",
        "action.converting_to": "Converting to {target}",
        "action.converting_many": "Converting {n} files to {target}",
        "action.converting_file": "Converting {name}",
        "action.converting_file_to": "Converting {name} to {target}",
        "action.converting_progress": "Converting {name} ({index} of {total})",
        "action.extracting_archive": "Extracting archive",
        "action.extracting": "Extracting {name}",
        "action.merging_pdfs": "Merging PDFs",
        "action.splitting_pdf": "Splitting PDF",
        "action.creating_pdf": "Creating PDF",
        "action.removing_audio": "Removing audio",
        "action.removing_audio_from": "Removing audio from {name}",
        "action.normalizing_volume": "Normalizing volume",
        "action.normalizing": "Normalizing {name}",
        "action.tidying_text": "Tidying text",
        "action.cleaning": "Cleaning {name}",
        "action.compressing_pdf": "Compressing PDF",
        "action.compressing_document": "Compressing document",
        "action.compressing": "Compressing {name}",
        "action.compressing_generic": "Compressing",
        "action.working_on": "Working on {name}",
        "action.working_on_many": "Working on {n} files",
        "action.repackaging": "Repackaging {name} as {target}",
        "action.converting_channels_of": "Converting channels of {name}",
        "action.trimming": "Trimming {name}",
        "action.redacting": "Redacting {name}",
        "action.cropping": "Cropping {name}",
        "action.adding_background_to": "Adding background to {name}",
        "action.editing": "Editing {name}",
        "action.annotating": "Annotating {name}",
        "action.rendering_annotations": "Rendering annotations for {name}",
        "action.building_collage": "Building collage",
        "action.building_visualizer": "Building visualizer for {name}",
        "action.bleeping": "Bleeping {name}",
        "action.changing_speed": "Changing speed of {name}",
        "action.exporting_snapshots": "Exporting snapshots for {name}",
        "action.splitting": "Splitting {name}",
        "action.splitting_into": "Splitting {name} into {parts} sections",
        "action.splitting_into_pages": "Splitting {name} into {total} pages",
        "action.joining": "Joining videos",
        "action.writing_metadata": "Writing metadata for {name}",
        "action.removing_metadata": "Removing metadata from {name}",
        "action.removing_location": "Removing location from {name}",
        "action.writing": "Writing {name}",
        "action.rendering_page": "Rendering page {number} of {total}",
        "action.reading_page_ocr": "Reading page {number} of {total} with OCR",
        "action.extracting_text": "Extracting text from {name}",
        "action.capturing_frame": "Capturing frame at {time:.2f}s",
        "action.scanning": "Scanning {name}",
        "action.scanning_qr": "Scanning for QR codes...",
        "action.read_qr": "Read QR Codes",
        "action.qr_title": "QR Codes",
        "action.qr_results": "Decoded results",
        "action.qr_empty": "No QR codes were found.",
        "action.copy": "Copy",
        "action.copy_all": "Copy All",
        "action.done": "Done",
        "action.optional_editor_missing": (
            "This tool needs the optional editor module, which is not available "
            "in this build."
        ),
        # -- progress -----------------------------------------------------
        "progress.starting": "Starting…",
        "progress.cancel": "Cancel",
        "progress.dismiss": "Dismiss",
        "progress.cancelling": "Cancelling…",
        "progress.cancelled": "Cancelled.",
        "progress.operation_failed": "The operation failed.",
        "progress.output_unconfirmed": "Finished (output not confirmed)",
        # -- settings window ----------------------------------------------
        "settings.title": "FilePetal Settings",
        "settings.tab.general": "General",
        "settings.tab.wheels": "Wheels",
        "settings.tab.formats": "Formats",
        "settings.tab.about": "About",
        "settings.language.label": "Language",
        "settings.language.system": "System",
        "settings.language.hint": (
            "The change applies immediately to the tray icon and the wheel; "
            "windows that are already open apply it when reopened."
        ),
        "settings.appearance.label": "Appearance",
        "settings.appearance.system": "System",
        "settings.appearance.light": "Light",
        "settings.appearance.dark": "Dark",
        "settings.appearance.hint": (
            "Appearance switches the material of the wheel, the progress card "
            "and the editors between the light and dark palettes. System "
            "follows the Windows theme."
        ),
        "settings.general.fullscreen": "Hide the wheel in games and full-screen apps",
        "settings.general.fullscreen_hint": (
            "The wheel never opens over full-screen games or apps; File "
            "Explorer, the desktop and windowed apps keep working as usual. "
            "Turn this off if an app you use never shows the wheel."
        ),
        "settings.wheels.intro": (
            "Hold one of these combinations while dragging files in File Explorer "
            "to open a wheel at the pointer."
        ),
        "settings.wheels.conversions": "Conversions wheel",
        "settings.wheels.tools": "Tools wheel",
        "settings.wheels.sound": "Sound and haptic feedback",
        "settings.wheels.fan_theme": "Fan theme",
        "settings.wheels.theme.glass": "Glass",
        "settings.wheels.theme.solid": "Solid",
        "settings.wheels.hint": (
            "The defaults are Shift for conversions and Alt+Shift for tools."
        ),
        "settings.wheels.sticky": "Sticky wheel (toggle)",
        "settings.wheels.sticky_hint": (
            "Press this combination with files selected in the Explorer to keep "
            "the wheel open after releasing the keys: click a petal to apply or "
            "click outside to close. Delete the combination to disable it."
        ),
        "settings.formats.search": "Search conversion defaults…",
        "settings.formats.images": "Images",
        "settings.formats.videos": "Videos",
        "settings.formats.audio": "Audio",
        "settings.formats.preset": "Compression preset",
        "settings.formats.size": "Compression size",
        "settings.formats.documents": "Documents and PDF",
        "settings.formats.page_size": "Paper size",
        "settings.formats.page_size.a4": "A4 (210 × 297 mm)",
        "settings.formats.page_size.letter": "Letter (216 × 279 mm)",
        "settings.formats.margins": "Margins",
        "settings.formats.margins.normal": "Normal (16 / 18 mm)",
        "settings.formats.margins.compact": "Compact (10 / 12 mm)",
        "settings.formats.margins.wide": "Wide (25 / 20 mm)",
        "settings.formats.page_numbers": "Add page numbers to PDF files",
        "settings.formats.documents_hint": (
            "Applies to every document conversion to PDF, JPG or PNG: Markdown, "
            "DOCX, XLSX, CSV, RTF, ODT, PPTX and TXT."
        ),
        "settings.strength.balanced": "Balanced",
        "settings.strength.strong": "Strong",
        "settings.size.original": "Original dimensions",
        "settings.size.2560": "Longest edge 2560 px",
        "settings.size.1920": "Longest edge 1920 px",
        "settings.size.1280": "Longest edge 1280 px",
        "settings.about.title": (
            "FilePetal {version} for Windows (build {build})"
        ),
        "settings.about.blurb": (
            "An offline-first drag-to-convert companion for File Explorer: hold "
            "a modifier while dragging, drop on a petal."
        ),
        "settings.about.not_found": "not found",
        "settings.about.ffmpeg": "FFmpeg",
        "settings.about.ffprobe": "FFprobe",
        "settings.about.rar_writer": "RAR writer",
        "settings.about.rar_reader": "RAR reader",
        "settings.about.settings_file": "Settings",
        "settings.about.log": "Log",
        "settings.about.open_folder": "Open Settings Folder",
        "settings.about.restore": "Restore Defaults",
        "settings.restore.title": "Restore Defaults",
        "settings.restore.confirm": (
            "Restore every FilePetal setting to its default value?"
        ),
        "settings.restore.done": "Settings restored to defaults.",
        "settings.mask.none": "None",
        # -- tool petal labels --------------------------------------------
        "tool.img.compress": "Compress",
        "tool.img.metadata": "Metadata",
        "tool.img.edit": "Edit Photo",
        "tool.img.annotate": "Annotate Photo",
        "tool.img.background": "Add Background",
        "tool.img.crop": "Crop",
        "tool.img.redact": "Redact Photo",
        "tool.img.pdf": "Create PDF",
        "tool.img.collage": "Create Collage",
        "tool.aud.compress": "Compress",
        "tool.aud.metadata": "Metadata",
        "tool.aud.normalize": "Normalize Volume",
        "tool.aud.visualizer": "Audio Visualizer",
        "tool.aud.trim": "Trim Audio",
        "tool.aud.channels": "Convert Audio Channels",
        "tool.aud.bleep": "Bleep Audio",
        "tool.vid.compress": "Compress",
        "tool.vid.metadata": "Metadata",
        "tool.vid.removeaudio": "Remove Audio",
        "tool.vid.trim": "Trim",
        "tool.vid.crop": "Crop",
        "tool.vid.speed": "Change Speed",
        "tool.vid.snapshots": "Snapshots",
        "tool.vid.split": "Split Video",
        "tool.vid.redact": "Redact Video",
        "tool.vid.join": "Join Videos",
        "tool.gif.metadata": "Metadata",
        "tool.pdf.compress": "Compress",
        "tool.pdf.metadata": "Metadata",
        "tool.pdf.split": "Split PDF",
        "tool.pdf.qr": "Read QR Codes",
        "tool.pdf.merge": "Merge into one PDF",
        "tool.arc.extract": "Extract",
        "tool.doc.compress": "Compress",
        "tool.qr.read": "Read QR Codes",
        # -- conversion petal labels ---------------------------------------
        "conv.jpg": "JPG",
        "conv.png": "PNG",
        "conv.webp": "WEBP",
        "conv.heic": "HEIC",
        "conv.tiff": "TIFF",
        "conv.pdf": "PDF",
        "conv.docx": "DOCX",
        "conv.mp3": "MP3",
        "conv.m4a": "M4A",
        "conv.wav": "WAV",
        "conv.flac": "FLAC",
        "conv.mp4": "MP4",
        "conv.mov": "MOV",
        "conv.mkv": "MKV",
        "conv.gif": "GIF",
        "conv.zip": "ZIP",
        "conv.tar": "TAR",
        "conv.gz": "GZ",
        "conv.rar": "RAR",
        "conv.txt": "Text File",
        "conv.csv": "CSV",
        "conv.xlsx": "Excel",
        "conv.html": "HTML",
        "conv.avif": "AVIF",
        "conv.ogg": "OGG",
        "conv.opus": "Opus",
        "conv.aiff": "AIFF",
        "conv.wma": "WMA",
        "conv.webm": "WebM",
        "conv.avi": "AVI",
        "conv.wmv": "WMV",
        "conv.srt": "SRT",
        "conv.vtt": "VTT",
        # -- shared buttons / labels ----------------------------------------
        "btn.cancel": "Cancel",
        "btn.close": "Close",
        "btn.copy": "Copy",
        "btn.save_copy": "Save Copy",
        "btn.undo": "Undo",
        "btn.reset": "Reset",
        "btn.move_up": "Move up",
        "btn.move_down": "Move down",
        "btn.select_all": "Select All",
        "btn.color": "Color",
        "btn.choose_image": "Choose Image...",
        "btn.clear": "Clear",
        "btn.stop": "Stop",
        "btn.play": "Play",
        "btn.play_selection": "Play Selection",
        "btn.play_original": "Play Original",
        "btn.remove_selected": "Remove Selected",
        "btn.delete_selected": "Delete Selected",
        "btn.remove_all": "Remove All",
        "btn.detect_faces": "Detect Faces",
        "btn.save_trimmed": "Save Trimmed Copy",
        "btn.save_redacted": "Save Redacted Copy",
        "btn.save_bleeped": "Save Bleeped Copy",
        "btn.save_converted": "Save Converted Copy",
        "btn.save_background": "Save with Background",
        "btn.remove_location": "Remove Location",
        "btn.save_annotated": "Save Annotated Copy",
        "btn.save_speed": "Save Speed Change",
        "btn.create_visualizer": "Create Visualizer",
        "btn.export_snapshots": "Export Snapshots",
        "btn.add_range": "Add / Update Range",
        "btn.delete_range": "Delete Range",
        "btn.bleep_entire": "Bleep Entire Audio",
        "btn.auto_trim": "Auto-trim Silence",
        "btn.refresh_frame": "Refresh Frame",
        "btn.set_in": "Set In from Playhead",
        "btn.set_out": "Set Out from Playhead",
        "btn.draw_box": "Draw Box from Frame...",
        "btn.extend_end": "Extend to End",
        "btn.add_frame": "Add Current Frame",
        "btn.frame_back": "◀ Frame",
        "btn.frame_forward": "Frame ▶",
        "btn.crop_video": "Crop Video",
        "btn.split_video": "Split Video",
        "btn.join_videos": "Join Videos",
        "btn.use_box": "Use Box",
        # -- dialog titles --------------------------------------------------
        "dlg.compress.title": "Compress",
        "dlg.collage.title": "Create Collage",
        "dlg.crop.title": "Crop",
        "dlg.redact.title": "Redact Photo",
        "dlg.background.title": "Add Background",
        "dlg.edit.title": "Edit Photo",
        "dlg.annotate.title": "Annotate Photo",
        "dlg.metadata.title": "Metadata",
        "dlg.channels.title": "Convert Audio Channels",
        "dlg.visualizer.title": "Audio Visualizer",
        "dlg.trim_audio.title": "Trim Audio",
        "dlg.bleep.title": "Bleep Audio",
        "dlg.trim_video.title": "Trim Video",
        "dlg.crop_video.title": "Crop Video",
        "dlg.speed.title": "Change Speed",
        "dlg.snapshots.title": "Snapshots",
        "dlg.split_video.title": "Split Video",
        "dlg.redact_video.title": "Redact Video",
        "dlg.join.title": "Join Videos",
        "dlg.boxdraw.title": "Draw Redaction Box",
        "dlg.not_available": "The {label} editor is not available yet.",
        # -- labels ---------------------------------------------------------
        "lbl.field": "Field",
        "lbl.value": "Value",
        "lbl.loading": "Loading…",
        "lbl.loading_waveform": "Loading waveform…",
        "lbl.loading_preview": "Loading preview…",
        "lbl.start": "Start",
        "lbl.end": "End",
        "lbl.range_start": "Range start",
        "lbl.range_end": "Range end",
        "lbl.shape": "Shape",
        "lbl.frame_at": "Frame at",
        "lbl.effect": "Effect",
        "lbl.size": "Size",
        "lbl.layout": "Layout",
        "lbl.image_area": "Image area",
        "lbl.image_fit": "Image fit",
        "lbl.spacing": "Spacing",
        "lbl.padding": "Padding",
        "lbl.rounded_corners": "Rounded corners",
        "lbl.background": "Background",
        "lbl.margin": "Margin",
        "lbl.order": "Order",
        "lbl.aspect": "Aspect",
        "lbl.w": "W",
        "lbl.h": "H",
        "lbl.compression_preset": "Compression preset",
        "lbl.dimensions": "Dimensions",
        "lbl.brightness": "Brightness",
        "lbl.contrast": "Contrast",
        "lbl.saturation": "Saturation",
        "lbl.sharpness": "Sharpness",
        "lbl.exposure": "Exposure",
        "lbl.temperature": "Temperature",
        "lbl.vibrance": "Vibrance",
        "lbl.vignette": "Vignette",
        "lbl.grain": "Grain",
        "lbl.preset": "Preset",
        "lbl.gradient_from": "Gradient from",
        "lbl.gradient_to": "Gradient to",
        "lbl.angle": "Angle",
        "lbl.sections": "Number of sections",
        # -- combo options ---------------------------------------------------
        "opt.balanced": "Balanced",
        "opt.strong": "Strong",
        "opt.original": "Original dimensions",
        "opt.limit_2560": "Limit to 2560 px",
        "opt.limit_1920": "Limit to 1920 px",
        "opt.limit_1280": "Limit to 1280 px",
        "opt.grid": "Grid",
        "opt.horizontal": "Horizontal",
        "opt.vertical": "Vertical",
        "opt.featured": "Featured",
        "opt.source_size": "Source size",
        "opt.px2000": "2000 px",
        "opt.px1500": "1500 px",
        "opt.px1080": "1080 px",
        "opt.fill": "Fill cell",
        "opt.contain": "Contain",
        "opt.white": "White",
        "opt.black": "Black",
        "opt.transparent": "Transparent",
        "opt.free": "Free",
        "opt.solid": "Solid",
        "opt.blur": "Blur",
        "opt.pixelate": "Pixelated",
        "opt.bg_color": "Color",
        "opt.bg_gradient": "Gradient",
        "opt.bg_image": "Image",
        "opt.aspect_original": "Original",
        "opt.preset_none": "None",
        "opt.preset_mono": "Mono",
        "opt.preset_sepia": "Sepia",
        "opt.preset_noir": "Noir",
        "opt.preset_vivid": "Vivid",
        "opt.preset_cool": "Cool",
        "opt.preset_warm": "Warm",
        "opt.mono": "Mono mixdown",
        "opt.stereo": "Two-channel stereo",
        "opt.landscape": "Landscape 1280 x 720",
        "opt.portrait": "Portrait 720 x 1280",
        "opt.square": "Square 1080 x 1080",
        "opt.arrow": "Arrow",
        "opt.pen": "Draw",
        "opt.rect": "Rect",
        "opt.ellipse": "Ellipse",
        "opt.text": "Text",
        "opt.highlight": "Highlight",
        "opt.callout": "Number",
        # -- notes and messages ---------------------------------------------
        "msg.preview_unavailable": "Preview unavailable",
        "msg.crop.need_area": "Select a crop area first.",
        "msg.range_too_short": "The selected range is too short.",
        "dlg.compress.target": "Compress to target file size",
        "dlg.compress.note": (
            "Balanced targets about 20% savings with less quality loss. "
            "Strong targets about 50%. The original bytes are kept whenever "
            "re-encoding would make the file larger."
        ),
        "dlg.count_files": "{count} files",
        "dlg.redact.color_title": "Redaction Color",
        "dlg.redact.hint": (
            "Drag on the photo to draw a redaction box. Select a box and press "
            "Delete to remove it."
        ),
        "dlg.redact.no_faces": "No faces were detected.",
        "dlg.redact.need_box": "Draw at least one redaction box.",
        "dlg.background.color_title": "Background Color",
        "dlg.background.image_title": "Background Image",
        "dlg.background.note": (
            "The image is centered on a canvas built from the chosen fill. "
            "The margin and aspect expand the canvas and the photo is never "
            "enlarged; corners follow the radius."
        ),
        "msg.background.no_image": "Choose a background image first.",
        "dlg.annotate.color_title": "Annotation Color",
        "dlg.annotate.need_op": "Add at least one annotation.",
        "dlg.annotate.text_title": "Text",
        "dlg.annotate.text_prompt": "Enter text:",
        "dlg.metadata.status_image": (
            "Editing metadata writes a separate copy: {name} Metadata{ext}. "
            "Fields not listed here are preserved."
        ),
        "dlg.metadata.status_ro": (
            "This format keeps a read-only metadata view here."
        ),
        "dlg.metadata.status_ro_strip": (
            "This format keeps a read-only metadata view here. Remove All "
            "strips metadata into a separate copy."
        ),
        "dlg.metadata.save_image_only": (
            "Saving edited metadata is available for images."
        ),
        "dlg.metadata.save_image_only_strip": (
            " Use Remove All to strip metadata from this file."
        ),
        "dlg.metadata.location_invalid": (
            "Latitude and longitude must be decimal numbers."
        ),
        "dlg.channels.heading": "{name} currently has {count} channel(s).",
        "dlg.channels.hint": (
            "Mono to stereo duplicates the signal. "
            "Mono mixdown combines both channels."
        ),
        "dlg.visualizer.bg_title": "Background Image",
        "dlg.visualizer.bg_none": "Background image: none",
        "dlg.visualizer.bg_named": "Background image: {name}",
        "dlg.visualizer.hint": (
            "The full recording is rendered as a warm orange waveform "
            "on black or your chosen image."
        ),
        "fmt.images_filter": "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        "dlg.trim.auto_title": "Auto-trim",
        "dlg.trim.no_waveform": "The waveform is not available yet.",
        "dlg.trim.silent_range": (
            "The selected range is silent at this threshold. Lower the threshold "
            "or turn off automatic trimming."
        ),
        "dlg.bleep.hint": (
            "Drag across the waveform to add a range, then drag a range or "
            "either edge to adjust it. A 1 kHz tone replaces the samples "
            "inside every range on all channels."
        ),
        "dlg.bleep.range_short": "The range is too short.",
        "dlg.bleep.need_range": "Add at least one bleep range first.",
        "dlg.crop_video.no_frame": "Could not read a frame from this video.",
        "msg.crop_video.not_ready": "The preview frame is not ready yet.",
        "msg.crop_video.larger": "Select a larger crop area.",
        "msg.crop_video.full_frame": (
            "The whole frame is selected, so a byte-identical copy will be saved."
        ),
        "dlg.speed.hint": (
            "Preview playback uses the selected speed. Audio pitch is "
            "preserved by the encoder."
        ),
        "dlg.speed.same": "Choose a speed other than 1.00x.",
        "dlg.snapshots.no_frame": "Could not read this frame.",
        "dlg.snapshots.need_frame": "Add at least one frame.",
        "dlg.split_video.about": (
            "About {per} s per section ({total} s total)."
        ),
        "dlg.split_video.hint": (
            "Every section is written as a separate file inside a new folder "
            "beside the source."
        ),
        "dlg.redact_video.hint": (
            "Boxes stay fixed in the frame. The saved video burns the effect "
            "into pixels and keeps the chosen soundtrack."
        ),
        "dlg.redact_video.rows_ignored": (
            "Rows {rows} were ignored: invalid times or size."
        ),
        "dlg.redact_video.need_box": "Add at least one valid redaction box.",
        "dlg.boxdraw.hint": (
            "Drag to draw the box that should be hidden in this video."
        ),
        "dlg.boxdraw.need_box": "Draw a box first.",
        "dlg.join.hint": (
            "Clips are fitted to the first video's shape (up to 1920 px on the "
            "longest edge) and joined at 30 fps with normalized audio."
        ),
        # -- metadata rows ----------------------------------------------------
        "meta.duration": "Duration",
        "meta.overall_bitrate": "Overall bitrate",
        "meta.video_codec": "Video codec",
        "meta.dimensions": "Dimensions",
        "meta.frame_rate": "Frame rate",
        "meta.audio_codec": "Audio codec",
        "meta.channels": "Channels",
        "meta.sample_rate": "Sample rate",
        "meta.latitude": "Latitude",
        "meta.longitude": "Longitude",
        "meta.altitude": "Altitude",
        # -- engine / tool errors ---------------------------------------------
        "err.cancelled": "Cancelled.",
        "err.source_missing": "The source file could not be found: {name}",
        "err.gps_image_only": "Location can only be removed from images.",
        "err.background_image": "Background image not found: {name}",
        "err.file_missing": "The file no longer exists: {name}",
        "err.file_locked": "The file is locked or read-only: {name}",
        "err.read_image": "Could not read image: {name}\n{detail}",
        "err.rasterize_svg": "Could not rasterize SVG: {name}",
        "err.save_image": "Could not save {name}\n{detail}",
        "err.no_images": "No images selected.",
        "err.ffmpeg_process": "FFmpeg could not process {name}",
        "err.ffmpeg_empty": "FFmpeg produced an empty file.",
        "err.pdf_open": "This PDF could not be opened.",
        "err.pdf_password": "Password-protected PDFs are not supported.",
        "err.ocr_install": (
            "This PDF has no selectable text. Install OCR support with: "
            "pip install rapidocr-onnxruntime"
        ),
        "err.pdf_no_text": "No text could be read from this PDF, even with OCR.",
        "err.pdf_unsupported": "Unsupported PDF conversion: {target}",
        "err.archive_too_large": "This archive is too large to extract safely.",
        "err.rar_missing_reader": "WinRAR is required to read RAR archives.",
        "err.rar_extract": (
            "Could not extract this RAR archive (password-protected or "
            "multivolume RAR is not supported)."
        ),
        "err.rar_missing_writer": "WinRAR is required to create RAR archives.",
        "err.archive_repack": "The archive could not be repackaged.",
        "err.rar_create": "Could not create the RAR archive.",
        "err.archive_unsupported": "Unsupported archive: {name}",
        "err.archive_target": "Unsupported archive target: {name}",
        "err.no_engine": "No conversion engine for {name}",
        "err.video_compress": "FFmpeg could not compress this video.",
        "err.doc_compress_type": (
            "Only Word, Excel, and PowerPoint files can be compressed."
        ),
        "err.audio_compress": "FFmpeg could not compress this audio file.",
        "err.audio_container": "Unsupported audio container: {ext}",
        "err.speed_positive": "Speed must be greater than zero.",
        "err.bleep_range": "Add at least one bleep range first.",
        "err.no_audio_track": "This video has no audio track to visualize.",
        "err.no_video_stream": "No video stream found.",
        "err.frame_capture": "Could not capture a frame at {time:.2f}s.",
        "err.split_sections": "Choose at least two sections.",
        "err.split_failed": "Could not split this video.",
        "err.join_two": "Select at least two videos to join.",
        "err.first_no_video": "The first video has no video stream.",
        "err.redact_box": "Add at least one redaction box first.",
        "err.redact_invalid": "No valid redaction boxes.",
        "err.pdf_select": "Select at least one PDF.",
        "err.doc_package_docx": (
            "Opening Word files requires the 'python-docx' package."
        ),
        "err.doc_open": "This document could not be opened.",
        "err.doc_package_xlsx": (
            "Opening Excel files requires the 'openpyxl' package."
        ),
        "err.doc_spreadsheet": "This spreadsheet could not be opened.",
        "err.doc_file": "This file could not be opened.",
        "err.doc_package_pptx": (
            "Opening PowerPoint files requires the 'python-pptx' package."
        ),
        "err.doc_presentation": "This presentation could not be opened.",
        "err.doc_package_rtf": (
            "Opening RTF files requires the 'striprtf' package."
        ),
        "err.doc_package_md": (
            "Opening Markdown files requires the 'markdown' package."
        ),
        "err.doc_markdown": "This Markdown file could not be opened.",
        "err.doc_package_odt": "Opening ODT files requires the 'odfpy' package.",
        "err.doc_epub": "This e-book could not be opened.",
        "err.doc_unsupported": "Unsupported document format.",
        "err.doc_no_text": "This document contains no readable text.",
        "err.doc_package_xlsx_write": (
            "Creating Excel files requires the 'openpyxl' package."
        ),
        "err.doc_no_rows": "This file contains no readable rows.",
        "err.doc_pdf_failed": "This file could not be converted to PDF.",
        "err.doc_no_slides": "This presentation contains no slides.",
        "err.doc_image_failed": (
            "This document could not be rendered as an image: {name}"
        ),
        "err.doc_html_only_md": "Only Markdown files can be converted to HTML.",
        "err.doc_unsupported_conversion": (
            "Unsupported document conversion: {target}"
        ),
        "settings.wheels.actions": "Actions wheel modifier",
        "settings.about.offline_ready": "Offline-ready (Local processing only)",
        "settings.about.bundled_tools": "Bundled local tools",
        "act.share": "Share",
        "act.shelf": "Float",
        "act.copy_ref": "Copy Files",
        "act.move": "Move",
        "act.copy_path": "Copy Path",
        "act.terminal": "Terminal",
        "action.share_fallback_copied": "System Share not available for this file type. File reference copied to clipboard.",
        "action.move_select_folder": "Select Destination Folder",
        "action.move_error": "Could not move files:\n{error}",
        "action.paths_copied": "Path(s) copied to clipboard",
        "action.refs_copied": "File reference(s) copied to clipboard",
        "shelf.title": "FilePetal Shelf",
        "shelf.hint": "Staged files stay here. Drag them out to any app or folder.",
        "shelf.empty_hint": "No files on the shelf. Drop files here or use the Float action.",
        "shelf.count_hint": "{count} file(s) staged on shelf.",
        "shelf.pin_tooltip": "Toggle pin / stay on top",
        "shelf.copy_files": "Copy Files",
        "shelf.clear": "Clear",
        "err.archive_traversal": "Malicious archive entry rejected (path traversal): {name}",
        "wheel.no_conversion": "No offline conversion available for this format",
        "wheel.no_tools": "No tools available for this format",
        "wheel.actions_hint": "Press Ctrl+Shift for Actions",
        "action.terminal_opened": "Terminal opened in {folder}",
        "action.move_success": "Moved {n} file(s)",
    },
    "es": {
        # -- app / wheel / tray -------------------------------------------
        "app.name": "FilePetal",
        "wheel.convert": "Convertir",
        "wheel.actions": "Acciones",
        "wheel.tools": "Herramientas",
        "wheel.drop_file": "Suelta un archivo aquí",
        "wheel.files_count": "{n} archivos",
        "tray.active": "Activo",
        "tray.nothing_active": "Nada activo",
        "tray.settings": "Ajustes...",
        "tray.check_updates": "Buscar actualizaciones...",
        "tray.quit": "Salir de FilePetal",
        "tray.working": "Trabajando",
        "tray.tooltip": "FilePetal",
        "tray.welcome": (
            "Arrastra archivos desde el Explorador manteniendo Shift para convertirlos.\n"
            "Mantén Alt+Shift para herramientas como Comprimir, Recortar o Censurar."
        ),
        "tray.already_running": "FilePetal ya se está ejecutando.",
        "tray.settings_unavailable": (
            "La ventana de ajustes no está disponible en esta compilación."
        ),
        "tray.update_message": (
            "FilePetal {version} para Windows\n\n"
            "Esta es una compilación local, así que las actualizaciones se "
            "gestionan manualmente."
        ),
        "tray.quit_running": "Hay conversiones en curso. ¿Salir de todos modos?",
        # -- actions ------------------------------------------------------
        "action.file_to": "{name} → {target}",
        "action.converting_to": "Convirtiendo a {target}",
        "action.converting_many": "Convirtiendo {n} archivos a {target}",
        "action.converting_file": "Convirtiendo {name}",
        "action.converting_file_to": "Convirtiendo {name} a {target}",
        "action.converting_progress": "Convirtiendo {name} ({index} de {total})",
        "action.extracting_archive": "Extrayendo archivo",
        "action.extracting": "Extrayendo {name}",
        "action.merging_pdfs": "Uniendo PDFs",
        "action.splitting_pdf": "Dividiendo PDF",
        "action.creating_pdf": "Creando PDF",
        "action.removing_audio": "Quitando audio",
        "action.removing_audio_from": "Quitando el audio de {name}",
        "action.normalizing_volume": "Normalizando volumen",
        "action.normalizing": "Normalizando {name}",
        "action.tidying_text": "Limpiando texto",
        "action.cleaning": "Limpiando {name}",
        "action.compressing_pdf": "Comprimiendo PDF",
        "action.compressing_document": "Comprimiendo documento",
        "action.compressing": "Comprimiendo {name}",
        "action.compressing_generic": "Comprimiendo",
        "action.working_on": "Trabajando en {name}",
        "action.working_on_many": "Trabajando en {n} archivos",
        "action.repackaging": "Recomprimiendo {name} como {target}",
        "action.converting_channels_of": "Convirtiendo los canales de {name}",
        "action.trimming": "Recortando {name}",
        "action.redacting": "Censurando {name}",
        "action.cropping": "Recortando {name}",
        "action.adding_background_to": "Añadiendo fondo a {name}",
        "action.editing": "Editando {name}",
        "action.annotating": "Anotando {name}",
        "action.rendering_annotations": "Dibujando las anotaciones de {name}",
        "action.building_collage": "Creando collage",
        "action.building_visualizer": "Creando visualizador para {name}",
        "action.bleeping": "Silenciando {name}",
        "action.changing_speed": "Cambiando la velocidad de {name}",
        "action.exporting_snapshots": "Exportando capturas de {name}",
        "action.splitting": "Dividiendo {name}",
        "action.splitting_into": "Dividiendo {name} en {parts} secciones",
        "action.splitting_into_pages": "Dividiendo {name} en {total} páginas",
        "action.joining": "Uniendo vídeos",
        "action.writing_metadata": "Escribiendo metadatos de {name}",
        "action.removing_metadata": "Quitando metadatos de {name}",
        "action.removing_location": "Quitando ubicación de {name}",
        "action.writing": "Escribiendo {name}",
        "action.rendering_page": "Dibujando la página {number} de {total}",
        "action.reading_page_ocr": "Leyendo la página {number} de {total} con OCR",
        "action.extracting_text": "Extrayendo texto de {name}",
        "action.capturing_frame": "Capturando el fotograma en {time:.2f}s",
        "action.scanning": "Analizando {name}",
        "action.scanning_qr": "Buscando códigos QR...",
        "action.read_qr": "Leer códigos QR",
        "action.qr_title": "Códigos QR",
        "action.qr_results": "Resultados decodificados",
        "action.qr_empty": "No se encontraron códigos QR.",
        "action.copy": "Copiar",
        "action.copy_all": "Copiar todo",
        "action.done": "Listo",
        "action.optional_editor_missing": (
            "Esta herramienta necesita el módulo opcional de editores, que no "
            "está disponible en esta compilación."
        ),
        # -- progress -----------------------------------------------------
        "progress.starting": "Iniciando…",
        "progress.cancel": "Cancelar",
        "progress.dismiss": "Cerrar",
        "progress.cancelling": "Cancelando…",
        "progress.cancelled": "Cancelado.",
        "progress.operation_failed": "La operación falló.",
        "progress.output_unconfirmed": "Terminado (salida no confirmada)",
        # -- settings window ----------------------------------------------
        "settings.title": "Ajustes de FilePetal",
        "settings.tab.general": "General",
        "settings.tab.wheels": "Ruedas",
        "settings.tab.formats": "Formatos",
        "settings.tab.about": "Acerca de",
        "settings.language.label": "Idioma",
        "settings.language.system": "Sistema",
        "settings.language.hint": (
            "El cambio se aplica al instante en la bandeja y en la rueda; las "
            "ventanas ya abiertas lo aplican al volver a abrirse."
        ),
        "settings.appearance.label": "Apariencia",
        "settings.appearance.system": "Sistema",
        "settings.appearance.light": "Claro",
        "settings.appearance.dark": "Oscuro",
        "settings.appearance.hint": (
            "La apariencia cambia el material de la rueda, la tarjeta de "
            "progreso y los editores entre las paletas clara y oscura. "
            "Sistema sigue el tema de Windows."
        ),
        "settings.general.fullscreen": (
            "Ocultar la rueda en juegos y aplicaciones a pantalla completa"
        ),
        "settings.general.fullscreen_hint": (
            "La rueda no se abre sobre juegos ni aplicaciones a pantalla "
            "completa; el Explorador, el escritorio y las ventanas normales "
            "siguen funcionando igual. Desactívalo si alguna aplicación no "
            "muestra la rueda cuando la necesitas."
        ),
        "settings.wheels.intro": (
            "Mantén una de estas combinaciones al arrastrar archivos en el "
            "Explorador para abrir una rueda en el puntero."
        ),
        "settings.wheels.conversions": "Rueda de conversiones",
        "settings.wheels.tools": "Rueda de herramientas",
        "settings.wheels.sound": "Sonido y respuesta háptica",
        "settings.wheels.fan_theme": "Tema del abanico",
        "settings.wheels.theme.glass": "Cristal",
        "settings.wheels.theme.solid": "Sólido",
        "settings.wheels.hint": (
            "Los valores predeterminados son Shift para conversiones y "
            "Alt+Shift para herramientas."
        ),
        "settings.wheels.sticky": "Rueda fija (toggle)",
        "settings.wheels.sticky_hint": (
            "Pulsa esta combinación con archivos seleccionados en el Explorador "
            "para que la rueda quede abierta al soltar las teclas: haz clic en un "
            "pétalo para aplicarla o fuera para cerrarla. Borra la combinación "
            "para desactivarla."
        ),
        "settings.formats.search": "Buscar valores de conversión…",
        "settings.formats.images": "Imágenes",
        "settings.formats.videos": "Vídeos",
        "settings.formats.audio": "Audio",
        "settings.formats.preset": "Ajuste de compresión",
        "settings.formats.size": "Tamaño de compresión",
        "settings.formats.documents": "Documentos y PDF",
        "settings.formats.page_size": "Tamaño de papel",
        "settings.formats.page_size.a4": "A4 (210 × 297 mm)",
        "settings.formats.page_size.letter": "Carta (216 × 279 mm)",
        "settings.formats.margins": "Márgenes",
        "settings.formats.margins.normal": "Normales (16 / 18 mm)",
        "settings.formats.margins.compact": "Compactos (10 / 12 mm)",
        "settings.formats.margins.wide": "Amplios (25 / 20 mm)",
        "settings.formats.page_numbers": "Añadir números de página a los PDF",
        "settings.formats.documents_hint": (
            "Se aplica a todas las conversiones de documentos a PDF, JPG o PNG: "
            "Markdown, DOCX, XLSX, CSV, RTF, ODT, PPTX y TXT."
        ),
        "settings.strength.balanced": "Equilibrado",
        "settings.strength.strong": "Fuerte",
        "settings.size.original": "Dimensiones originales",
        "settings.size.2560": "Lado mayor 2560 px",
        "settings.size.1920": "Lado mayor 1920 px",
        "settings.size.1280": "Lado mayor 1280 px",
        "settings.about.title": (
            "FilePetal {version} para Windows (compilación {build})"
        ),
        "settings.about.blurb": (
            "Un complemento de conversión por arrastre para el Explorador: "
            "mantén un modificador al arrastrar y suelta sobre un pétalo."
        ),
        "settings.about.not_found": "no encontrado",
        "settings.about.ffmpeg": "FFmpeg",
        "settings.about.ffprobe": "FFprobe",
        "settings.about.rar_writer": "Escritor RAR",
        "settings.about.rar_reader": "Lector RAR",
        "settings.about.settings_file": "Ajustes",
        "settings.about.log": "Registro",
        "settings.about.open_folder": "Abrir carpeta de ajustes",
        "settings.about.restore": "Restaurar valores",
        "settings.restore.title": "Restaurar valores",
        "settings.restore.confirm": (
            "¿Restaurar todos los ajustes de FilePetal a sus valores "
            "predeterminados?"
        ),
        "settings.restore.done": (
            "Ajustes restaurados a sus valores predeterminados."
        ),
        "settings.mask.none": "Ninguno",
        # -- tool petal labels --------------------------------------------
        "tool.img.compress": "Comprimir",
        "tool.img.metadata": "Metadatos",
        "tool.img.edit": "Editar foto",
        "tool.img.annotate": "Anotar",
        "tool.img.background": "Añadir fondo",
        "tool.img.crop": "Recortar",
        "tool.img.redact": "Censurar",
        "tool.img.pdf": "Crear PDF",
        "tool.img.collage": "Collage",
        "tool.aud.compress": "Comprimir",
        "tool.aud.metadata": "Metadatos",
        "tool.aud.normalize": "Normalizar",
        "tool.aud.visualizer": "Visualizador",
        "tool.aud.trim": "Recortar",
        "tool.aud.channels": "Canales",
        "tool.aud.bleep": "Silenciar",
        "tool.vid.compress": "Comprimir",
        "tool.vid.metadata": "Metadatos",
        "tool.vid.removeaudio": "Quitar audio",
        "tool.vid.trim": "Recortar",
        "tool.vid.crop": "Recortar área",
        "tool.vid.speed": "Velocidad",
        "tool.vid.snapshots": "Capturas",
        "tool.vid.split": "Dividir",
        "tool.vid.redact": "Censurar",
        "tool.vid.join": "Unir vídeos",
        "tool.gif.metadata": "Metadatos",
        "tool.pdf.compress": "Comprimir",
        "tool.pdf.metadata": "Metadatos",
        "tool.pdf.split": "Dividir PDF",
        "tool.pdf.qr": "Leer QR",
        "tool.pdf.merge": "Unir PDFs",
        "tool.arc.extract": "Extraer",
        "tool.doc.compress": "Comprimir",
        "tool.qr.read": "Leer QR",
        # -- conversion petal labels ---------------------------------------
        "conv.jpg": "JPG",
        "conv.png": "PNG",
        "conv.webp": "WEBP",
        "conv.heic": "HEIC",
        "conv.tiff": "TIFF",
        "conv.pdf": "PDF",
        "conv.docx": "DOCX",
        "conv.mp3": "MP3",
        "conv.m4a": "M4A",
        "conv.wav": "WAV",
        "conv.flac": "FLAC",
        "conv.mp4": "MP4",
        "conv.mov": "MOV",
        "conv.mkv": "MKV",
        "conv.gif": "GIF",
        "conv.zip": "ZIP",
        "conv.tar": "TAR",
        "conv.gz": "GZ",
        "conv.rar": "RAR",
        "conv.txt": "Archivo de texto",
        "conv.csv": "CSV",
        "conv.xlsx": "Excel",
        "conv.html": "HTML",
        "conv.avif": "AVIF",
        "conv.ogg": "OGG",
        "conv.opus": "Opus",
        "conv.aiff": "AIFF",
        "conv.wma": "WMA",
        "conv.webm": "WebM",
        "conv.avi": "AVI",
        "conv.wmv": "WMV",
        "conv.srt": "SRT",
        "conv.vtt": "VTT",
        # -- shared buttons / labels ----------------------------------------
        "btn.cancel": "Cancelar",
        "btn.close": "Cerrar",
        "btn.copy": "Copiar",
        "btn.save_copy": "Guardar copia",
        "btn.undo": "Deshacer",
        "btn.reset": "Restablecer",
        "btn.move_up": "Subir",
        "btn.move_down": "Bajar",
        "btn.select_all": "Seleccionar todo",
        "btn.color": "Color",
        "btn.choose_image": "Elegir imagen...",
        "btn.clear": "Quitar",
        "btn.stop": "Detener",
        "btn.play": "Reproducir",
        "btn.play_selection": "Reproducir selección",
        "btn.play_original": "Reproducir original",
        "btn.remove_selected": "Quitar selección",
        "btn.delete_selected": "Eliminar selección",
        "btn.remove_all": "Quitar todo",
        "btn.detect_faces": "Detectar caras",
        "btn.save_trimmed": "Guardar copia recortada",
        "btn.save_redacted": "Guardar copia censurada",
        "btn.save_bleeped": "Guardar copia silenciada",
        "btn.save_converted": "Guardar copia convertida",
        "btn.save_background": "Guardar con fondo",
        "btn.remove_location": "Quitar ubicación",
        "btn.save_annotated": "Guardar copia anotada",
        "btn.save_speed": "Guardar cambio de velocidad",
        "btn.create_visualizer": "Crear visualizador",
        "btn.export_snapshots": "Exportar capturas",
        "btn.add_range": "Añadir / actualizar rango",
        "btn.delete_range": "Eliminar rango",
        "btn.bleep_entire": "Silenciar todo el audio",
        "btn.auto_trim": "Recorte automático",
        "btn.refresh_frame": "Actualizar fotograma",
        "btn.set_in": "Fijar inicio en el cursor",
        "btn.set_out": "Fijar fin en el cursor",
        "btn.draw_box": "Dibujar caja en el fotograma...",
        "btn.extend_end": "Extender hasta el final",
        "btn.add_frame": "Añadir fotograma actual",
        "btn.frame_back": "◀ Fotograma",
        "btn.frame_forward": "Fotograma ▶",
        "btn.crop_video": "Recortar vídeo",
        "btn.split_video": "Dividir vídeo",
        "btn.join_videos": "Unir vídeos",
        "btn.use_box": "Usar caja",
        # -- dialog titles --------------------------------------------------
        "dlg.compress.title": "Comprimir",
        "dlg.collage.title": "Crear collage",
        "dlg.crop.title": "Recortar",
        "dlg.redact.title": "Censurar foto",
        "dlg.background.title": "Añadir fondo",
        "dlg.edit.title": "Editar foto",
        "dlg.annotate.title": "Anotar foto",
        "dlg.metadata.title": "Metadatos",
        "dlg.channels.title": "Convertir canales de audio",
        "dlg.visualizer.title": "Visualizador de audio",
        "dlg.trim_audio.title": "Recortar audio",
        "dlg.bleep.title": "Silenciar audio",
        "dlg.trim_video.title": "Recortar vídeo",
        "dlg.crop_video.title": "Recortar área del vídeo",
        "dlg.speed.title": "Cambiar velocidad",
        "dlg.snapshots.title": "Capturas",
        "dlg.split_video.title": "Dividir vídeo",
        "dlg.redact_video.title": "Censurar vídeo",
        "dlg.join.title": "Unir vídeos",
        "dlg.boxdraw.title": "Dibujar caja de censura",
        "dlg.not_available": "El editor de {label} aún no está disponible.",
        # -- labels ---------------------------------------------------------
        "lbl.field": "Campo",
        "lbl.value": "Valor",
        "lbl.loading": "Cargando…",
        "lbl.loading_waveform": "Cargando onda…",
        "lbl.loading_preview": "Cargando vista previa…",
        "lbl.start": "Inicio",
        "lbl.end": "Fin",
        "lbl.range_start": "Inicio del rango",
        "lbl.range_end": "Fin del rango",
        "lbl.shape": "Forma",
        "lbl.frame_at": "Fotograma en",
        "lbl.effect": "Efecto",
        "lbl.size": "Grosor",
        "lbl.layout": "Diseño",
        "lbl.image_area": "Área de imagen",
        "lbl.image_fit": "Ajuste de imagen",
        "lbl.spacing": "Espaciado",
        "lbl.padding": "Margen",
        "lbl.rounded_corners": "Esquinas redondeadas",
        "lbl.background": "Fondo",
        "lbl.margin": "Margen",
        "lbl.order": "Orden",
        "lbl.aspect": "Proporción",
        "lbl.w": "An",
        "lbl.h": "Al",
        "lbl.compression_preset": "Ajuste de compresión",
        "lbl.dimensions": "Dimensiones",
        "lbl.brightness": "Brillo",
        "lbl.contrast": "Contraste",
        "lbl.saturation": "Saturación",
        "lbl.sharpness": "Nitidez",
        "lbl.exposure": "Exposición",
        "lbl.temperature": "Temperatura",
        "lbl.vibrance": "Vibranza",
        "lbl.vignette": "Viñeta",
        "lbl.grain": "Grano",
        "lbl.preset": "Preajuste",
        "lbl.gradient_from": "Degradado desde",
        "lbl.gradient_to": "Degradado hasta",
        "lbl.angle": "Ángulo",
        "lbl.sections": "Número de secciones",
        # -- combo options ---------------------------------------------------
        "opt.balanced": "Equilibrado",
        "opt.strong": "Fuerte",
        "opt.original": "Dimensiones originales",
        "opt.limit_2560": "Límite 2560 px",
        "opt.limit_1920": "Límite 1920 px",
        "opt.limit_1280": "Límite 1280 px",
        "opt.grid": "Cuadrícula",
        "opt.horizontal": "Horizontal",
        "opt.vertical": "Vertical",
        "opt.featured": "Destacado",
        "opt.source_size": "Tamaño original",
        "opt.px2000": "2000 px",
        "opt.px1500": "1500 px",
        "opt.px1080": "1080 px",
        "opt.fill": "Rellenar",
        "opt.contain": "Ajustar",
        "opt.white": "Blanco",
        "opt.black": "Negro",
        "opt.transparent": "Transparente",
        "opt.free": "Libre",
        "opt.solid": "Sólido",
        "opt.blur": "Desenfoque",
        "opt.pixelate": "Pixelado",
        "opt.bg_color": "Color",
        "opt.bg_gradient": "Degradado",
        "opt.bg_image": "Imagen",
        "opt.aspect_original": "Original",
        "opt.preset_none": "Ninguno",
        "opt.preset_mono": "Mono",
        "opt.preset_sepia": "Sepia",
        "opt.preset_noir": "Noir",
        "opt.preset_vivid": "Vívido",
        "opt.preset_cool": "Frío",
        "opt.preset_warm": "Cálido",
        "opt.mono": "Mezcla mono",
        "opt.stereo": "Estéreo de dos canales",
        "opt.landscape": "Horizontal 1280 x 720",
        "opt.portrait": "Vertical 720 x 1280",
        "opt.square": "Cuadrado 1080 x 1080",
        "opt.arrow": "Flecha",
        "opt.pen": "Trazo",
        "opt.rect": "Rectángulo",
        "opt.ellipse": "Elipse",
        "opt.text": "Texto",
        "opt.highlight": "Resaltar",
        "opt.callout": "Número",
        # -- notes and messages ---------------------------------------------
        "msg.preview_unavailable": "Vista previa no disponible",
        "msg.crop.need_area": "Selecciona primero un área de recorte.",
        "msg.range_too_short": "El rango seleccionado es demasiado corto.",
        "dlg.compress.target": "Comprimir a un tamaño objetivo",
        "dlg.compress.note": (
            "Equilibrado busca un 20 % de ahorro con menos pérdida de calidad. "
            "Fuerte busca un 50 %. Se conservan los bytes originales cuando "
            "recodificar agrandaría el archivo."
        ),
        "dlg.count_files": "{count} archivos",
        "dlg.redact.color_title": "Color de censura",
        "dlg.redact.hint": (
            "Arrastra sobre la foto para dibujar un recuadro de censura. "
            "Selecciona un recuadro y pulsa Supr para quitarlo."
        ),
        "dlg.redact.no_faces": "No se detectaron caras.",
        "dlg.redact.need_box": "Dibuja al menos un recuadro de censura.",
        "dlg.background.color_title": "Color de fondo",
        "dlg.background.image_title": "Imagen de fondo",
        "dlg.background.note": (
            "La imagen se centra en un lienzo creado con el relleno elegido. "
            "El margen y la proporción amplían el lienzo y la foto nunca se "
            "agranda; las esquinas siguen el radio."
        ),
        "msg.background.no_image": "Elige primero una imagen de fondo.",
        "dlg.annotate.color_title": "Color de anotación",
        "dlg.annotate.need_op": "Añade al menos una anotación.",
        "dlg.annotate.text_title": "Texto",
        "dlg.annotate.text_prompt": "Escribe el texto:",
        "dlg.metadata.status_image": (
            "Editar los metadatos escribe una copia aparte: {name} Metadata{ext}. "
            "Los campos no listados aquí se conservan."
        ),
        "dlg.metadata.status_ro": (
            "Este formato solo ofrece una vista de metadatos de solo lectura."
        ),
        "dlg.metadata.status_ro_strip": (
            "Este formato solo ofrece una vista de metadatos de solo lectura. "
            "Quitar todo elimina los metadatos en una copia aparte."
        ),
        "dlg.metadata.save_image_only": (
            "Guardar los metadatos editados solo está disponible para imágenes."
        ),
        "dlg.metadata.save_image_only_strip": (
            " Usa Quitar todo para eliminar los metadatos de este archivo."
        ),
        "dlg.metadata.location_invalid": (
            "La latitud y la longitud deben ser números decimales."
        ),
        "dlg.channels.heading": "{name} tiene actualmente {count} canal(es).",
        "dlg.channels.hint": (
            "De mono a estéreo se duplica la señal. "
            "La mezcla mono combina ambos canales."
        ),
        "dlg.visualizer.bg_title": "Imagen de fondo",
        "dlg.visualizer.bg_none": "Imagen de fondo: ninguna",
        "dlg.visualizer.bg_named": "Imagen de fondo: {name}",
        "dlg.visualizer.hint": (
            "Toda la grabación se dibuja como una onda naranja cálida "
            "sobre negro o sobre tu imagen."
        ),
        "fmt.images_filter": "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        "dlg.trim.auto_title": "Recorte automático",
        "dlg.trim.no_waveform": "La onda aún no está disponible.",
        "dlg.trim.silent_range": (
            "El rango seleccionado es silencioso con este umbral. Baja el umbral "
            "o desactiva el recorte automático."
        ),
        "dlg.bleep.hint": (
            "Arrastra sobre la onda para añadir un rango y luego arrastra el "
            "rango o sus bordes para ajustarlo. Un tono de 1 kHz sustituye las "
            "muestras de cada rango en todos los canales."
        ),
        "dlg.bleep.range_short": "El rango es demasiado corto.",
        "dlg.bleep.need_range": "Añade primero al menos un rango de silencio.",
        "dlg.crop_video.no_frame": "No se pudo leer un fotograma de este vídeo.",
        "msg.crop_video.not_ready": "El fotograma de vista previa aún no está listo.",
        "msg.crop_video.larger": "Selecciona un área de recorte más grande.",
        "msg.crop_video.full_frame": (
            "Se seleccionó el fotograma completo, así que se guardará una "
            "copia idéntica."
        ),
        "dlg.speed.hint": (
            "La vista previa usa la velocidad elegida. El codificador conserva "
            "el tono del audio."
        ),
        "dlg.speed.same": "Elige una velocidad distinta de 1.00x.",
        "dlg.snapshots.no_frame": "No se pudo leer este fotograma.",
        "dlg.snapshots.need_frame": "Añade al menos un fotograma.",
        "dlg.split_video.about": (
            "Unos {per} s por sección ({total} s en total)."
        ),
        "dlg.split_video.hint": (
            "Cada sección se guarda como un archivo aparte en una carpeta "
            "nueva junto al original."
        ),
        "dlg.redact_video.hint": (
            "Las cajas permanecen fijas en el fotograma. El vídeo guardado "
            "aplica el efecto a los píxeles y conserva la banda sonora elegida."
        ),
        "dlg.redact_video.rows_ignored": (
            "Se ignoraron las filas {rows}: tiempos o tamaño no válidos."
        ),
        "dlg.redact_video.need_box": (
            "Añade al menos una caja de censura válida."
        ),
        "dlg.boxdraw.hint": (
            "Arrastra para dibujar la caja que se ocultará en este vídeo."
        ),
        "dlg.boxdraw.need_box": "Dibuja primero una caja.",
        "dlg.join.hint": (
            "Los clips se ajustan a la forma del primer vídeo (hasta 1920 px "
            "en el lado mayor) y se unen a 30 fps con audio normalizado."
        ),
        # -- metadata rows ----------------------------------------------------
        "meta.duration": "Duración",
        "meta.overall_bitrate": "Bitrate total",
        "meta.video_codec": "Códec de vídeo",
        "meta.dimensions": "Dimensiones",
        "meta.frame_rate": "Fotogramas por segundo",
        "meta.audio_codec": "Códec de audio",
        "meta.channels": "Canales",
        "meta.sample_rate": "Frecuencia de muestreo",
        "meta.latitude": "Latitud",
        "meta.longitude": "Longitud",
        "meta.altitude": "Altitud",
        # -- engine / tool errors ---------------------------------------------
        "err.cancelled": "Cancelado.",
        "err.source_missing": "No se encontró el archivo de origen: {name}",
        "err.gps_image_only": "La ubicación solo se puede quitar de imágenes.",
        "err.background_image": "No se encontró la imagen de fondo: {name}",
        "err.file_missing": "El archivo ya no existe: {name}",
        "err.file_locked": "El archivo está bloqueado o es de solo lectura: {name}",
        "err.read_image": "No se pudo leer la imagen: {name}\n{detail}",
        "err.rasterize_svg": "No se pudo rasterizar el SVG: {name}",
        "err.save_image": "No se pudo guardar {name}\n{detail}",
        "err.no_images": "No hay imágenes seleccionadas.",
        "err.ffmpeg_process": "FFmpeg no pudo procesar {name}",
        "err.ffmpeg_empty": "FFmpeg generó un archivo vacío.",
        "err.pdf_open": "Este PDF no se pudo abrir.",
        "err.pdf_password": "Los PDF protegidos con contraseña no son compatibles.",
        "err.ocr_install": (
            "Este PDF no tiene texto seleccionable. Instala el soporte OCR con: "
            "pip install rapidocr-onnxruntime"
        ),
        "err.pdf_no_text": (
            "No se pudo leer texto de este PDF, ni siquiera con OCR."
        ),
        "err.pdf_unsupported": "Conversión de PDF no compatible: {target}",
        "err.archive_too_large": (
            "Este archivo comprimido es demasiado grande para extraerlo de forma "
            "segura."
        ),
        "err.rar_missing_reader": "Se requiere WinRAR para leer archivos RAR.",
        "err.rar_extract": (
            "No se pudo extraer este archivo RAR (no se admiten RAR protegidos "
            "con contraseña ni multivolumen)."
        ),
        "err.rar_missing_writer": "Se requiere WinRAR para crear archivos RAR.",
        "err.archive_repack": "El archivo comprimido no se pudo recomprimir.",
        "err.rar_create": "No se pudo crear el archivo RAR.",
        "err.archive_unsupported": "Archivo comprimido no compatible: {name}",
        "err.archive_target": "Destino de compresión no compatible: {name}",
        "err.no_engine": "No hay motor de conversión para {name}",
        "err.video_compress": "FFmpeg no pudo comprimir este vídeo.",
        "err.doc_compress_type": (
            "Solo se pueden comprimir archivos de Word, Excel y PowerPoint."
        ),
        "err.audio_compress": "FFmpeg no pudo comprimir este archivo de audio.",
        "err.audio_container": "Contenedor de audio no compatible: {ext}",
        "err.speed_positive": "La velocidad debe ser mayor que cero.",
        "err.bleep_range": "Añade primero al menos un rango de silencio.",
        "err.no_audio_track": (
            "Este vídeo no tiene pista de audio que visualizar."
        ),
        "err.no_video_stream": "No se encontró ninguna pista de vídeo.",
        "err.frame_capture": "No se pudo capturar un fotograma en {time:.2f}s.",
        "err.split_sections": "Elige al menos dos secciones.",
        "err.split_failed": "No se pudo dividir este vídeo.",
        "err.join_two": "Selecciona al menos dos vídeos para unir.",
        "err.first_no_video": "El primer vídeo no tiene pista de vídeo.",
        "err.redact_box": "Añade primero al menos una caja de censura.",
        "err.redact_invalid": "No hay cajas de censura válidas.",
        "err.pdf_select": "Selecciona al menos un PDF.",
        "err.doc_package_docx": (
            "Abrir archivos de Word requiere el paquete 'python-docx'."
        ),
        "err.doc_open": "Este documento no se pudo abrir.",
        "err.doc_package_xlsx": (
            "Abrir archivos de Excel requiere el paquete 'openpyxl'."
        ),
        "err.doc_spreadsheet": "Esta hoja de cálculo no se pudo abrir.",
        "err.doc_file": "Este archivo no se pudo abrir.",
        "err.doc_package_pptx": (
            "Abrir archivos de PowerPoint requiere el paquete 'python-pptx'."
        ),
        "err.doc_presentation": "Esta presentación no se pudo abrir.",
        "err.doc_package_rtf": (
            "Abrir archivos RTF requiere el paquete 'striprtf'."
        ),
        "err.doc_package_md": (
            "Abrir archivos Markdown requiere el paquete 'markdown'."
        ),
        "err.doc_markdown": "Este archivo Markdown no se pudo abrir.",
        "err.doc_package_odt": "Abrir archivos ODT requiere el paquete 'odfpy'.",
        "err.doc_epub": "Este libro electrónico no se pudo abrir.",
        "err.doc_unsupported": "Formato de documento no compatible.",
        "err.doc_no_text": "Este documento no contiene texto legible.",
        "err.doc_package_xlsx_write": (
            "Crear archivos de Excel requiere el paquete 'openpyxl'."
        ),
        "err.doc_no_rows": "Este archivo no contiene filas legibles.",
        "err.doc_pdf_failed": "Este archivo no se pudo convertir a PDF.",
        "err.doc_no_slides": "Esta presentación no contiene diapositivas.",
        "err.doc_image_failed": (
            "Este documento no se pudo representar como imagen: {name}"
        ),
        "err.doc_html_only_md": (
            "Solo los archivos Markdown se pueden convertir a HTML."
        ),
        "err.doc_unsupported_conversion": (
            "Conversión de documento no compatible: {target}"
        ),
        "wheel.no_conversion": "No hay conversión sin conexión para este formato",
        "wheel.no_tools": "No hay herramientas disponibles para este formato",
        "wheel.actions_hint": "Presiona Ctrl+Shift para Acciones",
        "action.terminal_opened": "Terminal abierto en {folder}",
        "action.move_success": "{n} archivo(s) movido(s)",
    },
}

_listeners: list = []


def _settings():
    """Return the settings module without creating an import cycle."""
    from . import settings

    return settings


def _system_locale_name() -> str:
    """The raw system locale name (``es_MX``); empty when unavailable."""
    try:
        return QLocale.system().name()
    except Exception:
        return ""


def _system_language() -> str:
    """Resolve the OS locale to a supported language code, else English."""
    code = str(_system_locale_name()).split("_")[0].lower()
    return code if code in TRANSLATIONS else DEFAULT_LANGUAGE


def resolve_language(code: str | None = None) -> str:
    """Resolve a language setting (``"system"`` included) to a code."""
    if code is None:
        code = _settings().get("language", DEFAULT_LANGUAGE)
    code = str(code or DEFAULT_LANGUAGE).lower()
    if code == "system":
        code = _system_language()
    return code if code in TRANSLATIONS else DEFAULT_LANGUAGE


TRANSLATIONS["en"].update({
    "err.output_exists": "The output file already exists: {name}",
    "err.pdf_image_unsupported": "This file type is not supported for image-to-PDF conversion.",
    "pdf.images.title": "Create PDF from images...",
    "pdf.images.intro": "{count} images · one PDF. Choose the page order and layout.",
    "pdf.images.invalid": "Select only existing image files to create a PDF.",
    "pdf.order.name": "Filename (natural A-Z)",
    "pdf.order.received": "Order received from Explorer",
    "pdf.order.manual": "Manual order",
    "pdf.order.hint": "Explorer does not guarantee Ctrl-click chronology. Use Manual for an exact sequence.",
    "pdf.move.up": "Move up", "pdf.move.down": "Move down",
    "pdf.layout": "Images per page", "pdf.rows": "Rows", "pdf.columns": "Columns",
    "pdf.filenames": "Add filenames", "pdf.font_scale": "Label size",
    "pdf.output": "Save PDF", "pdf.output.browse": "Browse...",
    "pdf.output.auto": "New file beside the images (automatic name)",
    "pdf.output.hint": "Existing files are preserved. Choose a new filename.",
    "pdf.output.exists": "This file already exists. Choose a new name; your existing file will be preserved.",
    "pdf.create": "Create PDF",
    "pdf.instance.old": "The running FilePetal version cannot receive this request. Quit it from the tray, then start the new version.",
    "shell.title": "File Explorer",
    "shell.hint": "Right-click images → Send to → FilePetal – Create PDF. The classic FilePetal PDF submenu is also registered.",
    "shell.repair": "Install / repair Explorer integration",
    "shell.source": "Explorer integration is available in the packaged Windows app.",
    "shell.ready": "Explorer shortcuts and the FilePetal PDF menu are registered.",
    "defaults.tab": "Tool options",
    "defaults.reuse": "Use these options next time without asking",
    "defaults.hint": "Optional. Change this in Settings → Tool options to show this dialog again.",
    "defaults.settings_hint": "Skip the options dialog only for tools you enable. Save options in a tool first. Turn it off here to change them next time. Crop, annotations and redaction are edited separately for each image.",
    "defaults.settings_tooltip": "Enable after saving this tool's options. Turn off to show its dialog again.",
    "defaults.show_all": "Show all tool dialogs again",
    "defaults.image_compress": "Image compression",
    "defaults.video_compress": "Video compression",
    "defaults.audio_compress": "Audio compression",
    "defaults.batch": "Apply these options to all {count} images. Preview: first image.",
    "pdf.add_images": "Add images…",
    "pdf.remove_images": "Remove selected",
    "err.annotate_save": "Could not save the annotated image. Check that the output folder is writable.",
})
TRANSLATIONS["es"].update({
    "settings.wheels.actions": "Modificador de la rueda de acciones",
    "settings.about.offline_ready": "Listo sin conexión (Solo procesamiento local)",
    "settings.about.bundled_tools": "Herramientas locales incluidas",
    "act.share": "Compartir",
    "act.shelf": "Flotar",
    "act.copy_ref": "Copiar archivos",
    "act.move": "Mover",
    "act.copy_path": "Copiar ruta",
    "act.terminal": "Terminal",
    "action.share_fallback_copied": "Compartir del sistema no disponible para este tipo de archivo. Referencia copiada al portapapeles.",
    "action.move_select_folder": "Seleccionar carpeta de destino",
    "action.move_error": "No se pudieron mover los archivos:\n{error}",
    "action.paths_copied": "Ruta(s) copiada(s) al portapapeles",
    "action.refs_copied": "Referencia(s) copiada(s) al portapapeles",
    "shelf.title": "Estante de FilePetal",
    "shelf.hint": "Los archivos preparados se quedan aquí. Arrástralos a cualquier app o carpeta.",
    "shelf.empty_hint": "No hay archivos en el estante. Suelta archivos aquí o usa la acción Flotar.",
    "shelf.count_hint": "{count} archivo(s) preparados en el estante.",
    "shelf.pin_tooltip": "Alternar fijar / mantener encima",
    "shelf.copy_files": "Copiar archivos",
    "shelf.clear": "Limpiar",
    "err.archive_traversal": "Entrada de archivo no segura rechazada (escape de ruta): {name}",
    "err.output_exists": "El archivo de salida ya existe: {name}",
    "err.pdf_image_unsupported": "Este tipo de archivo no se admite para convertir a PDF.",
    "pdf.images.title": "Crear PDF con imágenes...",
    "pdf.images.intro": "{count} imágenes · un PDF. Elige el orden y la distribución de las páginas.",
    "pdf.images.invalid": "Selecciona únicamente archivos de imagen existentes para crear un PDF.",
    "pdf.order.name": "Nombre de archivo (A-Z natural)",
    "pdf.order.received": "Orden recibido de Explorer",
    "pdf.order.manual": "Orden manual",
    "pdf.order.hint": "Explorer no garantiza la cronología de Ctrl+clic. Usa Manual para fijar una secuencia exacta.",
    "pdf.move.up": "Subir", "pdf.move.down": "Bajar",
    "pdf.layout": "Imágenes por página", "pdf.rows": "Filas", "pdf.columns": "Columnas",
    "pdf.filenames": "Añadir nombres de archivo", "pdf.font_scale": "Tamaño del texto",
    "pdf.output": "Guardar PDF", "pdf.output.browse": "Examinar...",
    "pdf.output.auto": "Archivo nuevo junto a las imágenes (nombre automático)",
    "pdf.output.hint": "Se conservan los archivos existentes. Elige un nombre nuevo.",
    "pdf.output.exists": "Este archivo ya existe. Elige otro nombre; se conservará el archivo existente.",
    "pdf.create": "Crear PDF",
    "pdf.instance.old": "La versión abierta de FilePetal no puede recibir esta solicitud. Ciérrala desde la bandeja y abre la versión nueva.",
    "shell.title": "Explorador de archivos",
    "shell.hint": "Clic derecho en imágenes → Enviar a → FilePetal – Crear PDF. También se registra el submenú clásico FilePetal PDF.",
    "shell.repair": "Instalar / reparar integración con Explorer",
    "shell.source": "La integración con Explorer está disponible en la aplicación empaquetada de Windows.",
    "shell.ready": "Se registraron los accesos de Explorer y el menú PDF de FilePetal.",
    "defaults.tab": "Opciones de herramientas",
    "defaults.reuse": "Usar estos ajustes la próxima vez sin preguntar",
    "defaults.hint": "Opcional. Desactívalo en Ajustes → Opciones de herramientas para volver a ver esta ventana.",
    "defaults.settings_hint": "Omite la ventana de opciones solo en las herramientas que actives. Primero guarda sus ajustes. Desactiva la casilla aquí para modificarlos la próxima vez. Recorte, anotación y censura se editan por separado en cada imagen.",
    "defaults.settings_tooltip": "Activa después de guardar los ajustes. Desactiva para volver a mostrar la ventana.",
    "defaults.show_all": "Volver a mostrar todas las ventanas de opciones",
    "defaults.image_compress": "Compresión de imágenes",
    "defaults.video_compress": "Compresión de vídeo",
    "defaults.audio_compress": "Compresión de audio",
    "defaults.batch": "Aplicar estos ajustes a las {count} imágenes. Vista previa: primera imagen.",
    "pdf.add_images": "Añadir imágenes…",
    "pdf.remove_images": "Quitar seleccionadas",
    "err.annotate_save": "No se pudo guardar la imagen anotada. Comprueba que la carpeta de salida permita escritura.",
})


def current_language() -> str:
    """The effective language code currently used for lookups."""
    return resolve_language()


def tr(key: str, **fmt) -> str:
    """Translate *key* for the current language with English fallback."""
    language = current_language()
    table = TRANSLATIONS.get(language, {})
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
    if text is None:
        text = key
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            log.warning("Could not format translation %r with %r", key, fmt)
    return text


def add_listener(callback) -> None:
    """Register *callback*, invoked with the language code after a change."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_listener(callback) -> None:
    """Unregister a callback added with :func:`add_listener`."""
    if callback in _listeners:
        _listeners.remove(callback)


def set_language(code: str) -> None:
    """Persist *code* and notify every registered listener."""
    code = str(code or DEFAULT_LANGUAGE)
    settings = _settings()
    settings.set("language", code)
    settings.save()
    for callback in list(_listeners):
        try:
            callback(code)
        except Exception:
            log.exception("i18n listener failed for language %r", code)
