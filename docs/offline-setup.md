# FilePetal Offline Setup & Air-Gapped Operation Guide

FilePetal is architected from the ground up to operate completely offline. It makes zero cloud calls, contains zero analytics or telemetry, requires no user accounts, and never connects to the internet at runtime.

---

## 1. Zero-Network Guarantee

- **No Remote Calls:** All format conversions, image manipulation, audio/video encoding, PDF manipulation, and archive extraction run 100% on local hardware.
- **No Cloud Encoders:** No cloud conversion APIs or remote server fallbacks.
- **No Telemetry / Phoning Home:** No crash reporting or analytics beacons.
- **Privacy First:** Your files never leave your computer. Originals are never overwritten or modified without explicit user command; all outputs are written alongside the originals with automatic collision handling (`name (1).ext`).

---

## 2. Offline Distribution Packages

FilePetal provides two distribution options for offline deployment:

### A. Per-User Installer (`FilePetal-Setup.exe`)
- Standard Inno Setup 6 package.
- Installs to `%LOCALAPPDATA%\Programs\FilePetal`.
- **No Administrator Privileges (UAC) Required:** Installs directly under standard user accounts.
- Registers Explorer shell integration (`--register-shell`) locally.
- Creates Start Menu and optional Desktop shortcuts.

### B. Portable Archive (`FilePetal-1.11.0-windows-portable.zip`)
- Self-contained portable folder.
- Can be extracted to any folder or USB drive.
- Run `FilePetal.exe` directly.
- All dependencies, runtime libraries, and tools are bundled.

---

## 3. Bundled Binaries & Local Processing Engines

| Engine | Bundled / Internal | Purpose | Offline Status |
| :--- | :--- | :--- | :--- |
| **FFmpeg & FFprobe** | Bundled in `tools\` (`ffmpeg.exe`, `ffprobe.exe`) | Video, audio, GIF encoding, waveform extraction, duration probing | Fully functional offline |
| **Pillow & pillow-heif** | Embedded in frozen bundle | Image conversion (PNG, JPG, WebP, TIFF, BMP, ICO, HEIC, AVIF), cropping, rotation, metadata | Fully functional offline |
| **pypdf & pypdfium2** | Embedded in frozen bundle | PDF merge, split, page reordering, rasterization, image-to-PDF | Fully functional offline |
| **python-docx / openpyxl / pptx** | Embedded in frozen bundle | Office document reading and export | Fully functional offline |
| **OpenCV Headless** | Embedded in frozen bundle | QR code reading, facial redaction | Fully functional offline |
| **Zip / Tar Engines** | Python standard library (`zipfile`, `tarfile`) | Extraction and compression with directory traversal (Zip Slip) security | Fully functional offline |
| **WinRAR** | Optional external (`Rar.exe`) | Proprietary `.rar` archive extraction | Optional (searches `C:\Program Files\WinRAR`) |

---

## 4. Air-Gapped Installation Steps

1. Copy `FilePetal-Setup.exe` (or the portable `.zip`) onto the air-gapped machine via approved offline media (e.g. encrypted USB drive).
2. Double-click `FilePetal-Setup.exe`.
3. Follow the wizard prompts to install. No internet connection or network interface is required or queried.
4. Launch FilePetal from the Start Menu or System Tray.
5. In **Settings > About**, verify that all engines (FFmpeg, Qt, Pillow, PDF, Office) display green status indicators.

---

## 5. Security & Safety Notes for Offline Environments

- **Zip Slip & Tar Slip Hardening:** The built-in archive extraction engine checks every entry target with strict path resolution. Any archive attempting directory traversal (`../` or escaping the target directory) is immediately blocked with a security exception.
- **Non-Destructive Operations:** Conversions and tools always create a new output file next to the input file, resolving collisions with incrementing counters. Cancelled or failed jobs immediately wipe temporary files to prevent disk clutter.
- **Isolated Settings:** Configuration is saved locally in `%APPDATA%\FilePetal\settings.json`.
