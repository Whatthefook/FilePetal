# FilePetal

**A local-first file utility for Windows.** Drag files from File Explorer to a radial wheel to convert them, open a focused tool, or take a quick file action.

![FilePetal conversion wheel](docs/images/wheel-dark.png)

FilePetal runs on your PC. It converts, edits, and organizes files locally, with outputs written as new files so the originals remain intact.

> **Project history:** FilePetal is a renamed and extended continuation of [Tangerine for Windows](https://github.com/CristianO2601/tangerine-windows), and preserves its MIT license and contributor attribution. The radial drag-to-convert interaction was inspired by [Tangerine for Mac](https://tangerineformac.com/) by thmmhnsn. FilePetal is a community project with no official affiliation with the Mac app or its developer.

## Availability

- **Available now:** Windows 10 (version 1809 or later) and Windows 11, x64.
- **Planned:** macOS and Linux versions. Those builds are not available yet.
- **Website:** a lightweight project website and download tracking are planned for a later phase. The application itself does not include download analytics.

Windows installer and portable downloads will be listed in the repository's **Releases** section when a release is published.

## What FilePetal does

### Convert

Hold **Shift** while dragging files out of File Explorer. The radial conversion wheel appears by the pointer and shows compatible output formats for the selected files. Drop onto a format to start a local conversion. Multiple files can be processed in a batch.

Supported families include images, audio, video, GIF, PDF, text, Office and OpenDocument files, EPUB, subtitles, and archives. The exact input/output combinations and fidelity notes are in the [compatibility matrix](docs/compatibility.md).

### Tools

Hold **Alt+Shift** while dragging files to open the tools wheel. Available tools depend on the selected file type and include:

- **Images:** compress, view/edit/remove location metadata, adjust photos, annotate, add a background, crop, redact, make PDFs or collages, and read QR codes.
- **Video:** compress, inspect metadata, remove audio, trim, crop, change speed, extract frames, split, redact, and join.
- **Audio:** compress, inspect metadata, normalize volume, create a waveform video, trim, change channels, and bleep selected sections.
- **PDFs and documents:** compress, inspect metadata, split or merge PDFs, and compress supported Office files.
- **Archives:** extract ZIP, TAR, GZ, and supported RAR files with path-traversal protection.

Editors show a small progress window while background jobs run. Operations create output files without replacing the source. Read the [compatibility matrix](docs/compatibility.md) for engine requirements and format-specific limits.

![FilePetal crop editor](docs/images/crop-1.10.2-dark.png)

### File actions

Hold **Ctrl+Shift** while dragging files to open the actions wheel:

- **Share:** opens the Windows share interface when supported.
- **Float:** pins files to a small, always-on-top shelf so they can be dragged elsewhere later.
- **Copy files:** places file references on the clipboard for pasting into Explorer or another app.
- **Move to:** moves files to a chosen folder and resolves name collisions safely.
- **Copy path:** copies the full file paths.
- **Terminal:** opens Windows Terminal or PowerShell in the file's folder.

Keyboard navigation is supported in the wheels. See [offline setup](docs/offline-setup.md) for installation and local engine details.

## Screenshots

<p align="center">
  <img src="docs/images/wheel-light.png" alt="FilePetal conversion wheel in light theme" width="360">
  &nbsp;&nbsp;
  <img src="docs/images/image-pdf-dark.png" alt="FilePetal image to PDF editor" width="360">
</p>

## Install and build

Use a Windows release package from **Releases** when one is available. The portable ZIP can be extracted to a folder; the per-user installer does not require administrator rights.

To build from source, use Windows x64 and Python 3.11 or later. Install the Python dependencies, provision FFmpeg and FFprobe for audio/video features, and optionally install Inno Setup 6 to build the installer.

```powershell
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.txt -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python .venv\Scripts\python.exe
```

See the [release and packaging guide](docs/release.md) and [offline setup guide](docs/offline-setup.md) for complete instructions.

## Documentation

- [Format compatibility and conversion engines](docs/compatibility.md)
- [Offline setup and operation](docs/offline-setup.md)
- [Third-party software notices](docs/third-party-notices.md)
- [Packaging and release guide](docs/release.md)

## Privacy and safety

File conversion and editing run locally; FilePetal has no account, cloud conversion service, or analytics. The app's tools create output files alongside their inputs or in a selected destination. Archive extraction checks that entries stay inside the destination folder.

## License

FilePetal's source code is licensed under the [MIT License](LICENSE). Third-party libraries and bundled components have their own terms; see [third-party notices](docs/third-party-notices.md).
