# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FilePetal for Windows (onedir, windowed, no UPX).

Build from the repository root:

    pyinstaller --noconfirm --clean packaging\\filepetal.spec
"""

import os
import re

from PyInstaller.utils.hooks import collect_all

try:
    SPEC_DIR = os.path.abspath(SPECPATH)
except NameError:  # pragma: no cover
    SPEC_DIR = os.path.dirname(os.path.abspath(__file__))

REPO_ROOT = os.path.dirname(SPEC_DIR)
MAIN_PY = os.path.join(REPO_ROOT, "main.py")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
ICON_FILE = os.path.join(ASSETS_DIR, "icon.ico")


def _read_app_version(repo_root):
    paths_py = os.path.join(repo_root, "tangerine", "paths.py")
    with open(paths_py, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else "1.11.0"


def _version_quad(version):
    numbers = [int(part) for part in re.findall(r"\d+", version)][:4]
    numbers += [0] * (4 - len(numbers))
    return tuple(numbers)


APP_VERSION = _read_app_version(REPO_ROOT)
VERSION_QUAD = _version_quad(APP_VERSION)
VERSION_INFO_TEMPLATE = os.path.join(SPEC_DIR, "version_info.txt")
VERSION_INFO_FILE = os.path.join(SPEC_DIR, "_version_info_generated.txt")

with open(VERSION_INFO_TEMPLATE, "r", encoding="utf-8") as _handle:
    _version_text = _handle.read()
_version_text = _version_text.replace("@@VERSION_TUPLE@@", repr(VERSION_QUAD))
_version_text = _version_text.replace("@@VERSION@@", APP_VERSION)
with open(VERSION_INFO_FILE, "w", encoding="utf-8") as _handle:
    _handle.write(_version_text)
print(f"[filepetal.spec] FilePetal {APP_VERSION} -> {VERSION_INFO_FILE}")


datas = [
    (os.path.join(REPO_ROOT, "build", "shell", "TangerineShell.dll"), "shell"),
    (os.path.join(ASSETS_DIR, "icon.ico"), "assets"),
    (os.path.join(ASSETS_DIR, "icon.png"), "assets"),
    (os.path.join(ASSETS_DIR, "tray.ico"), "assets"),
    (os.path.join(ASSETS_DIR, "tray.png"), "assets"),
    (os.path.join(ASSETS_DIR, "highlight.wav"), "assets"),
]

binaries = []

hiddenimports = [
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSvg",
    "comtypes",
    "comtypes.client",
]

for _package in ("rapidocr_onnxruntime", "onnxruntime"):
    try:
        _package_datas, _package_binaries, _package_hiddenimports = collect_all(_package)
    except Exception as _exc:
        print(f"[filepetal.spec] optional package not bundled ({_package}): {_exc}")
        continue
    print(f"[filepetal.spec] collected optional package: {_package}")
    datas += _package_datas
    binaries += _package_binaries
    hiddenimports += _package_hiddenimports


EXCLUDES = [
    "torch",
    "torchvision",
    "torchaudio",
    "numba",
    "llvmlite",
    "scipy",
    "sklearn",
    "matplotlib",
    "pandas",
    "IPython",
    "pytest",
    "tkinter",
]

a = Analysis(
    [MAIN_PY],
    pathex=[REPO_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FilePetal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
    version=VERSION_INFO_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FilePetal",
)
