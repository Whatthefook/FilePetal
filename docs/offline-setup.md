# Offline Setup and Local Processing

FilePetal processes selected files on the local computer. The application does not upload files or include download analytics. Once a package and its optional engines are installed, conversions do not require a FilePetal account or a FilePetal server.

## Download packages

Get the latest ZIP from [GitHub Releases](https://github.com/Whatthefook/FilePetal/releases/latest). Choose the matching package:

- `windows-x64`: Windows 10 (1809+) or Windows 11, 64-bit.
- `macos-arm64`: Apple silicon Mac, macOS 13 or later.
- `macos-x64`: Intel Mac, macOS 13 or later.
- `linux-x64`: x86_64 Linux, Ubuntu 22.04 or later (glibc 2.34 or later).

Windows provides its Explorer drag interaction. macOS and Linux use the small FilePetal companion window: drop files there or choose them, then select **Convert**, **Tools**, or **Actions**. On Linux, a system tray icon depends on the desktop environment; the companion window remains the primary entry point.

macOS releases are currently unsigned and not notarized. Depending on Gatekeeper settings, the first launch may require Control-clicking `FilePetal.app` in Finder and choosing **Open**. Linux packages are portable folders; launch `FilePetal` inside the extracted folder.

## Processing engines

Python packages, Qt, image, PDF, document, archive, and subtitle engines are included in the platform bundles. FilePetal checks for optional command-line engines locally:

| Engine | Used for | Distribution status |
| --- | --- | --- |
| FFmpeg and FFprobe | Audio/video/GIF conversion, media inspection, waveform extraction | Install separately and make both commands available on `PATH`, or put the binaries in FilePetal's `tools` folder. These binaries are not currently included in the release ZIPs. |
| WinRAR / UnRAR | Optional `.rar` extraction and creation | Install a compatible utility separately. ZIP and TAR-family archive support uses Python's included standard library. |
| RapidOCR | OCR for scanned PDFs | Included in release builds; runs locally. |

Without FFmpeg/FFprobe, image, PDF, document, subtitle, and standard archive features remain available, while audio/video features that require FFmpeg are unavailable. The `.rar` formats need their external engine.

## Local data

Settings, logs, and single-instance state are kept in the user's application-data folder:

- Windows: `%APPDATA%\FilePetal`
- macOS: `~/Library/Application Support/FilePetal`
- Linux: `$XDG_CONFIG_HOME/FilePetal`, or `~/.config/FilePetal`

The FilePetal process does not send selected files or conversion results to a service. Releases are downloaded from GitHub; the later project website may count download-link requests, but that website is separate from the desktop application.

## Safety behavior

- Conversions and tools write a new output file rather than replacing the source.
- Archive extraction validates destinations to block path traversal outside the chosen folder.
- Cancelled or failed jobs clean up temporary outputs when the engine permits it.

For the supported format combinations and their fidelity limits, see the [compatibility matrix](compatibility.md).
