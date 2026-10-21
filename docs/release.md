# FilePetal Release & Packaging Guide

This guide details how to build, test, and package FilePetal for Windows releases.

---

## 1. Prerequisites

- **Operating System:** Windows 10 (1809+) or Windows 11 (x64)
- **Python:** Python 3.11, 3.12, or 3.14 (Python 3.12 recommended)
- **Visual Studio Build Tools:** C++ CMake tools and MSVC x64 compiler (or MinGW g++)
- **Inno Setup 6:** Required to build `FilePetal-Setup.exe`
  ```powershell
  winget install --id JRSoftware.InnoSetup -e
  ```
- **FFmpeg Full Build:** Required in `tools\` for audio/video bundling
  ```powershell
  winget install --id Gyan.FFmpeg -e
  ```

---

## 2. Setting Up the Development Environment

1. Clone or extract the repository:
   ```powershell
   git clone <repo-url> filepetal
   cd filepetal
   ```

2. Create virtual environment and install dependencies:
   ```powershell
   uv venv --python 3.12
   .venv\Scripts\activate
   uv pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Copy FFmpeg and FFprobe binaries to `tools\`:
   ```powershell
   New-Item -ItemType Directory -Path tools -Force
   $wingetDir = (Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe").DirectoryName
   Copy-Item (Join-Path $wingetDir "ffmpeg.exe") "tools\ffmpeg.exe"
   Copy-Item (Join-Path $wingetDir "ffprobe.exe") "tools\ffprobe.exe"
   ```

---

## 3. Running Verification & Test Suite

Run the full pytest suite before building packages:
```powershell
.venv\Scripts\python.exe -m pytest
```
Expected: All 272+ tests pass with 0 failures.

---

## 4. Building the Production Release

FilePetal features an automated, one-shot packaging pipeline (`packaging\build.ps1`) that:
1. Compiles the native Explorer C++ shell bridge (`build\shell\TangerineShell.dll`).
2. Runs native selection contract tests (`ValidateShell.exe`).
3. Freezes the application with PyInstaller into `dist\FilePetal\`.
4. Bundles `tools\` (`ffmpeg.exe`, `ffprobe.exe`) and `assets\`.
5. Executes headless smoke tests:
   - Qt WebEngine render check (`--smoke-webengine`)
   - Image-to-PDF ordering and engine IPC check (`--smoke-image-pdf`)
   - Image editors & batch controls check (`--smoke-editors`)
6. Generates portable archive `dist\FilePetal-<version>-windows-portable.zip`.
7. Compiles Inno Setup per-user installer `dist\FilePetal-Setup.exe`.

### Command:
```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python .venv\Scripts\python.exe
```

---

## 5. Artifact Verification Checklist

After building, inspect the contents of `dist\`:
- [ ] `dist\FilePetal\FilePetal.exe` launches correctly.
- [ ] `dist\FilePetal\tools\ffmpeg.exe` and `ffprobe.exe` exist.
- [ ] `dist\FilePetal\shell\TangerineShell.dll` exists.
- [ ] `dist\FilePetal-Setup.exe` installs cleanly without requiring administrative privileges.
- [ ] `dist\FilePetal-1.11.0-windows-portable.zip` contains all runtime dependencies.
- [ ] Settings window (`Settings > About`) indicates all required engines are available.
