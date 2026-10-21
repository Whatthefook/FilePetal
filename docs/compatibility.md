# FilePetal Compatibility Matrix & Engine Specifications

FilePetal is an offline-first Windows 11 file conversion and productivity utility. All processing is executed **entirely on your local machine** using real, embedded open-source engines. No cloud services, external servers, telemetry, or network connections are ever utilized.

---

## 1. Source-to-Output Conversion Matrix

| Source Family | Input Formats | Available Outputs | Local Engine & Method |
| :--- | :--- | :--- | :--- |
| **Raster Images** | `jpg`, `jpeg`, `png`, `webp`, `avif`, `heic`, `heif`, `tiff`, `tif`, `bmp` | `jpg`, `png`, `webp`, `avif`, `heic`, `tiff`, `pdf`, `docx`* | **Pillow / pillow-heif / reportlab**<br>Lossless or high-quality transcoding; EXIF rotation preservation; `docx` export available from JPG/PNG. |
| **Vector Images** | `svg` | `jpg`, `png`, `webp`, `avif`, `heic`, `tiff`, `pdf` | **PySide6.QtSvg + Pillow**<br>High-resolution rasterization and vector PDF generation. |
| **Audio** | `mp3`, `m4a`, `wav`, `flac`, `ogg`, `opus`, `aiff`, `wma` | `mp3`, `m4a`, `wav`, `flac`, `ogg`, `opus`, `aiff`, `wma` | **FFmpeg (bundled / local)**<br>Lossless audio decoding and targeted codec re-encoding. |
| **Video** | `mp4`, `mov`, `mkv`, `avi`, `webm`, `wmv`, `m4v` | `mp4`, `mov`, `mkv`, `webm`, `avi`, `wmv`, `gif`, `mp3`, `m4a` | **FFmpeg (bundled / local)**<br>Hardware-accelerated or CPU encoding; audio stream extraction to MP3/M4A. |
| **Animated GIF** | `gif` | `mp4`, `mov`, `mkv`, `webm`, `avi`, `wmv` | **FFmpeg**<br>Transcodes frame sequences to modern container codecs. |
| **Subtitles** | `srt`, `vtt` | `srt` ↔ `vtt`, `txt` | **FilePetal Subtitle Parser (Pure Python)**<br>Strict timestamp translation, BOM/UTF-8/CP1252 auto-detection, plain transcript export. |
| **PDF** | `pdf` | `docx`, `jpg`, `png`, `txt` | **pypdf + pypdfium2 (+ RapidOCR if installed)**<br>Direct selectable text extraction; 300 DPI page rasterization; optional local ONNX OCR. |
| **Plain Text** | `txt` | `pdf`, `jpg`, `png` | **ReportLab + pypdfium2**<br>Clean layout with selectable text and page numbers. |
| **Word (.docx)** | `docx` | `txt`, `pdf`, `jpg`, `png` | **python-docx + Mammoth / QtWebEngine + pypdfium2**<br>Preserves headings, paragraphs, tables, images, and formatting. |
| **Excel (.xlsx)** | `xlsx` | `csv`, `pdf`, `jpg`, `png` | **openpyxl + xlsx2html / QtWebEngine**<br>Renders active sheet with cached values and borders. |
| **PowerPoint (.pptx)**| `pptx` | `txt`, `pdf`, `jpg`, `png` | **python-pptx + QtWebEngine**<br>Slide-by-slide export with layout approximations. |
| **CSV** | `csv` | `xlsx`, `pdf`, `jpg`, `png`, `txt` | **openpyxl + ReportLab / QtWebEngine**<br>Clean table layout and spreadsheet conversion. |
| **Rich Text (.rtf)** | `rtf` | `txt`, `pdf`, `jpg`, `png` | **striprtf + ReportLab**<br>Strips RTF control words and formats readable paragraphs. |
| **Markdown (.md)** | `md` | `txt`, `html`, `pdf`, `jpg`, `png` | **Markdown + QtWebEngine / ReportLab**<br>Full GitHub Flavored Markdown support with typography. |
| **OpenDocument (.odt)**| `odt` | `txt`, `pdf`, `jpg`, `png` | **odfpy + ReportLab**<br>Extracts structured paragraphs and tables into formatted pages. |
| **ePub (.epub)** | `epub` | `txt` | **zipfile + xml parser**<br>Extracts chapter text into clean plain text transcript. |
| **Archives** | `zip`, `tar`, `tar.gz`, `rar` | `zip`, `tar`, `gz`, `rar` | **zipfile / tarfile / local unrar / rar**<br>Path-traversal safe extraction and multi-container repacking. |

\* `docx` target is supported from `jpg` and `png` sources.

---

## 2. Tools Compatibility Matrix

FilePetal tools run real editors and non-destructive processing pipelines on your files:

| Tool Identifier | Label | Target Family | Function & Engine |
| :--- | :--- | :--- | :--- |
| `img.compress` | Compress Image | Images | Re-encodes with perceptual quality floor (JPEG/PNG/WebP), optional dimension caps or target file size. |
| `img.metadata` | Metadata Viewer/Editor | Images | Reads EXIF/IPTC/XMP; allows viewing, editing, or scrubbing GPS coordinates. |
| `img.edit` | Photo Editor | Images | Interactive canvas adjustments: exposure, contrast, saturation, temperature, vibrance, sharpness, vignette, grain, and color presets. |
| `img.annotate` | Annotate Photo | Images | High-resolution freehand drawing, arrows, shapes, callouts, and text annotations. |
| `img.background`| Add Background | Images | Adds custom canvas, padding, corner radii, drop shadow, solid colors, multi-stop gradients, or image backdrops. |
| `img.crop` | Crop | Images | Aspect ratio presets (1:1, 16:9, 4:3, custom), freehand bounding boxes, rotation. |
| `img.redact` | Redact Photo | Images | Censors regions with solid color, blur, or 12px mosaic pixelation; automatic face detection via OpenCV Haar cascade. |
| `img.pdf` | Create PDF | Images | Interactive multi-image organizer, natural filename sorting, layout grids, headers, margins, and page sizes. |
| `img.collage` | Create Collage | Images | Generates contact sheets, photo grids, custom spacing, cell shapes, and canvas sizes. |
| `qr.read` | Read QR Codes | Images, PDF, GIF | Detects and decodes multiple QR codes per image or PDF page with result inspector and clipboard copying. |
| `vid.compress` | Compress Video | Video | Rate-distortion optimization via FFmpeg (H.264/H.265/VP9), resolution scaling, bitrate controls. |
| `vid.metadata` | Video Metadata | Video | Inspects streams, codecs, bitrates, audio tracks, and container tags via `ffprobe`. |
| `vid.removeaudio`| Remove Audio | Video | Losslessly strips all audio streams with `-c:v copy -an`. |
| `vid.trim` | Trim Video | Video | Interactive timeline scrubber for keyframe-accurate start and end points. |
| `vid.crop` | Crop Video | Video | Visual bounding box crop with FFmpeg `crop=w:h:x:y` filter. |
| `vid.speed` | Video Speed | Video | Speed adjustments (0.25x to 4.0x) with pitch-corrected audio (`atempo`). |
| `vid.snapshots` | Video Snapshots | Video | Extracts video frames as full-resolution PNG/JPG images at defined intervals. |
| `vid.split` | Split Video | Video | Splits video into equal duration chunks or parts. |
| `vid.redact` | Redact Video | Video | Applies blurred, solid, or pixelated bounding boxes across video timelines. |
| `vid.join` | Join Videos | Video | Concatenates multiple video files of similar format. |
| `aud.compress` | Compress Audio | Audio | Bitrate reduction using Opus, AAC, or MP3 encoders via FFmpeg. |
| `aud.metadata` | Audio Metadata | Audio | Inspects ID3/Vorbis/FLAC metadata tags. |
| `aud.normalize` | Normalize Audio | Audio | EBU R128 two-pass loudness normalization (`loudnorm`). |
| `aud.visualizer`| Audio Visualizer | Audio | Renders waveform visualization video clip from audio track. |
| `aud.trim` | Trim Audio | Audio | Timeline scrubber for trimming start and end positions. |
| `aud.channels` | Audio Channels | Audio | Converts between Mono and Stereo channels. |
| `aud.bleep` | Bleep Audio | Audio | Inserts 1 kHz sine-wave censor tones over selected intervals. |
| `pdf.compress` | Compress PDF | PDF | Recompresses stream objects and removes duplicate data using pypdf. |
| `pdf.split` | Split PDF | PDF | Explodes PDF into individual page files. |
| `pdf.merge` | Merge PDFs | PDF | Non-destructive combination of multiple PDF documents into one. |
| `doc.compress` | Compress Document | DOCX, XLSX, PPTX| Re-compresses inner ZIP archives with maximum DEFLATE compression. |
| `arc.extract` | Extract Archive | ZIP, TAR, GZ, RAR| Extracts archive contents into a new directory with Zip Slip / Tar Slip path traversal protection. |

---

## 3. Quick Actions Matrix

| Action | ID | Behavior |
| :--- | :--- | :--- |
| **Share** | `act.share` | Invokes Windows 11 system Share UI via the native shell verb. If the system share contract is unavailable for the selected file type, falls back to copying file references with a helpful notice. |
| **Float (Shelf)** | `act.shelf` | Staging area window that floats on top. Allows dragging files in or out, copying references, inspecting sizes, or clearing. |
| **Copy Files** | `act.copy_ref` | Copies true `CF_HDROP` file references to the Windows clipboard for direct pasting into File Explorer, emails, or chat applications. |
| **Move to Folder** | `act.move` | Prompts for a destination folder and moves files safely. Name collisions are automatically resolved with sibling numbering (`filename 2.ext`) to prevent data loss. |
| **Copy Path** | `act.copy_path` | Copies full, clean Windows paths to the clipboard (newline-delimited for multi-file selections). |
| **Terminal** | `act.terminal` | Opens the containing directory in Windows Terminal (`wt.exe`), with seamless fallback to PowerShell. |

---

## 4. Honest Limitations & Unsupported Directions

FilePetal strictly adheres to honesty in conversion capabilities and does **not fake** conversion results:

1. **Apple iWork Formats (.pages, .numbers, .key)**:
   - **Status**: **Unsupported**.
   - **Rationale**: Apple Pages, Numbers, and Keynote files are zipped proprietary binary protocol buffers (IWA format). There is no offline, open-source converter that can faithfully render Pages documents on Windows without Apple's proprietary engine or sending user files to iCloud. FilePetal refuses to fake conversion or produce mangled output.
2. **PDF to Microsoft Office (Word/Excel/PowerPoint)**:
   - **Fidelity Consideration**: PDF to DOCX extracts selectable text paragraphs, preserved document tables, and renders embedded graphics. Scanned documents use local OCR if the optional OCR stack is installed.
   - **Limitation**: PDF is a print description language, not an editable flow document. Complex magazine or vector DTP desktop publishing layouts may not match Adobe Acrobat Pro's proprietary vector reconstruction.
3. **Legacy Binary Office (.doc, .xls, .ppt)**:
   - **Status**: **Unsupported**.
   - **Rationale**: FilePetal supports modern OOXML (`.docx`, `.xlsx`, `.pptx`) and OpenDocument (`.odt`) standards. Obsolete 1997-2003 binary formats are not supported locally without legacy COM Office automation.
4. **Original File Protection**:
   - **Guarantee**: Source files are **NEVER modified or overwritten**. All output files are generated as sibling files (`name 2.ext`) or placed into dedicated subfolders with safe collision resolution.
   - **Atomic Cleanup**: Incomplete jobs due to user cancellation or errors delete their temporary `.part` files automatically.
