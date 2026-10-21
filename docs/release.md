# Release and Packaging Guide

FilePetal packages are built on native GitHub Actions runners. PyInstaller builds a separate package on each operating system, and the macOS app is built once per CPU architecture.

## Supported package targets

| ZIP asset | Build runner | Runtime target |
| --- | --- | --- |
| `FilePetal-<version>-windows-x64.zip` | Windows x64 | Windows 10 1809+ and Windows 11 |
| `FilePetal-<version>-macos-arm64.zip` | macOS 15 Apple silicon | macOS 13+, Apple silicon |
| `FilePetal-<version>-macos-x64.zip` | macOS 15 Intel | macOS 13+, Intel |
| `FilePetal-<version>-linux-x64.zip` | Ubuntu 22.04 x64 | x86_64 Linux with glibc 2.34+; Ubuntu 22.04+ is the supported baseline |

The app bundles its Python and Qt dependencies, plus RapidOCR for offline scanned-PDF OCR. FFmpeg/FFprobe and RAR utilities are not included in release ZIPs and must be installed separately for those optional features. The Windows package retains the existing native Explorer shell bridge; macOS and Linux use the companion drop window.

## Build from source

Build on the target OS, using Python 3.12. Install base and OCR dependencies:

```sh
python -m venv .venv
python -m pip install -r requirements.txt -r requirements-ocr.txt
python -m pip install pyinstaller pyinstaller-hooks-contrib
```

On macOS, create `assets/icon.icns` from the project PNG icon before building. The release workflow does this with `sips` and `iconutil`. Then build the platform bundle:

```sh
python -m PyInstaller --noconfirm --clean packaging/filepetal.spec
```

The macOS output is `dist/FilePetal.app`; Linux output is `dist/FilePetal/`. ZIP the macOS app with `ditto` to preserve bundle metadata. Zip the Linux folder after building.

On Windows, use the packaging script to build the native Explorer bridge, frozen app, smoke receipts, and portable ZIP:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python .venv\Scripts\python.exe -SkipInstaller
```

Omit `-SkipInstaller` to create the optional per-user Inno Setup installer when Inno Setup 6 is installed.

## Publish a GitHub release

1. Set `APP_VERSION` in `tangerine/paths.py` and commit all release source changes to `main`.
2. Push an annotated version tag that matches it, such as `v1.11.1` for `APP_VERSION = "1.11.1"`.
3. The **Build FilePetal downloads** workflow builds four ZIPs (Windows, Linux, macOS Apple silicon, macOS Intel), then attaches them to a GitHub Release for that tag.
4. Check each ZIP is present on the release before linking it from the project website.

The source repository is MIT licensed. Keep third-party notices and the applicable component licenses with the distribution; see [third-party notices](third-party-notices.md).

## Platform notes

- macOS ZIPs are currently unsigned and not notarized. Users may need to approve the first launch in Finder.
- Linux's portable ZIP still relies on a compatible host desktop and system Qt/X11 or Wayland libraries, plus `libpulse0`. Ubuntu 22.04 x64 is the minimum supported baseline.
- These packages do not bundle FFmpeg or RAR binaries. That keeps external codec licensing and source distribution explicit; users can install the required engine locally.
