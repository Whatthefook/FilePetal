# FilePetal

**A local-first file utility for Windows, macOS, and Linux.** Open a radial wheel to convert files, use a focused tool, or take a quick file action.

![FilePetal conversion wheel](docs/images/wheel-dark.png)

FilePetal converts, edits, and organizes files locally. Operations create output files without replacing the originals.

> **Project history:** FilePetal is a renamed and extended continuation of [Tangerine for Windows](https://github.com/CristianO2601/tangerine-windows), and preserves its MIT license and contributor attribution. The radial drag-to-convert interaction was inspired by [Tangerine for Mac](https://tangerineformac.com/) by thmmhnsn. FilePetal is a community project with no official affiliation with the Mac app or its developer.

## Availability

- **Windows:** Windows 10 (version 1809 or later) and Windows 11, x64. Drag from File Explorer with a modifier key to open the wheel beside the pointer.
- **macOS:** macOS 13 or later, Intel and Apple silicon. Each architecture has its own ZIP. Drop files on the FilePetal companion window to open the wheel.
- **Linux:** x86_64 on Ubuntu 22.04 or newer (glibc 2.34 or newer), with the host's Qt/X11 or Wayland libraries and PulseAudio client library (`libpulse0`). Drop files on the companion window. Tray availability depends on the desktop environment.
- **Downloads:** ZIP packages are published on [GitHub Releases](https://github.com/Whatthefook/FilePetal/releases/latest). The macOS release has separate Apple silicon and Intel downloads.
- **Website:** a lightweight project website and download tracking are planned for a later phase. The application itself does not include download analytics.

macOS and Linux cannot use the Windows Explorer drag monitor. Their companion window accepts local file drops and provides buttons for the same conversion, tools, and actions wheels. The native share action is currently Windows-only; the terminal action appears only when a supported terminal is available.

## What FilePetal does

### Convert

On Windows, hold **Shift** while dragging files out of File Explorer. On macOS and Linux, drop files onto the companion window or choose files there, then select **Convert**. The radial conversion wheel shows compatible output formats. Multiple files can be processed in a batch.

Supported families include images, audio, video, GIF, PDF, text, Office and OpenDocument files, EPUB, subtitles, and archives. The exact input/output combinations and fidelity notes are in the [compatibility matrix](docs/compatibility.md).

### Tools

On Windows, hold **Alt+Shift** while dragging files to open the tools wheel. In the macOS/Linux companion, choose **Tools** after dropping or selecting files. Available tools depend on the file type and include:

- **Images:** compress, view/edit/remove location metadata, adjust photos, annotate, add a background, crop, redact, make PDFs or collages, and read QR codes.
- **Video:** compress, inspect metadata, remove audio, trim, crop, change speed, extract frames, split, redact, and join.
- **Audio:** compress, inspect metadata, normalize volume, create a waveform video, trim, change channels, and bleep selected sections.
- **PDFs and documents:** compress, inspect metadata, split or merge PDFs, and compress supported Office files.
- **Archives:** extract ZIP, TAR, GZ, and supported RAR files with path-traversal protection.

Editors show a small progress window while background jobs run. Read the [compatibility matrix](docs/compatibility.md) for engine requirements and format-specific limits.

![FilePetal crop editor](docs/images/crop-1.10.2-dark.png)

### File actions

On Windows, hold **Ctrl+Shift** while dragging files to open the actions wheel. On macOS/Linux, choose **Actions** in the companion window:

- **Share:** opens the Windows share interface when supported (Windows only).
- **Float:** pins files to a small, always-on-top shelf so they can be dragged to other apps.
- **Copy files:** places file references on the clipboard for pasting into a file manager or another app.
- **Move to:** moves files to a chosen folder and resolves name collisions safely.
- **Copy path:** copies the full file paths.
- **Terminal:** opens Windows Terminal/PowerShell, macOS Terminal, or an available Linux terminal in the file's folder.

See [offline setup](docs/offline-setup.md) for local engine details.

## Screenshots

<p align="center">
  <img src="docs/images/wheel-light.png" alt="FilePetal conversion wheel in light theme" width="360">
  &nbsp;&nbsp;
  <img src="docs/images/image-pdf-dark.png" alt="FilePetal image to PDF editor" width="360">
</p>

## Install and build

Download the ZIP for your operating system from [GitHub Releases](https://github.com/Whatthefook/FilePetal/releases/latest) and extract it. The macOS ZIP contains `FilePetal.app`; the Linux ZIP contains a portable app folder; Windows uses the existing portable bundle. macOS packages are not notarized, so Gatekeeper may require **Control-click → Open** the first time. Audio/video features need FFmpeg and FFprobe installed locally; `.rar` extraction needs an external RAR utility. Other included Python and Qt engines run locally after installation.

Build each platform package on that operating system, using Python 3.12. macOS Intel and Apple silicon packages are built separately. Install the Python dependencies and FFmpeg/FFprobe if you need audio/video features.

```sh
python -m venv .venv
# Activate the environment, then:
python -m pip install -r requirements.txt -r requirements-ocr.txt pyinstaller pyinstaller-hooks-contrib
python -m PyInstaller --noconfirm --clean packaging/filepetal.spec
```

The Windows `packaging/build.ps1` script also creates its portable ZIP and can optionally create the per-user installer. GitHub Actions builds release ZIPs when a `v*` version tag is pushed.

See the [release and packaging guide](docs/release.md) and [offline setup guide](docs/offline-setup.md) for details.

## Documentation

- [Format compatibility and conversion engines](docs/compatibility.md)
- [Offline setup and operation](docs/offline-setup.md)
- [Third-party software notices](docs/third-party-notices.md)
- [Packaging and release guide](docs/release.md)

## Privacy and safety

FilePetal has no account, cloud conversion service, or in-app download analytics. File conversion runs on the local computer. Some audio/video features need the separately installed FFmpeg/FFprobe binaries; the app does not fetch them. Archive extraction checks that entries stay inside the destination folder.

## License

FilePetal's source code is licensed under the [MIT License](LICENSE). Third-party libraries and components have their own terms; see [third-party notices](docs/third-party-notices.md).
