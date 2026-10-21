"""Portable filesystem locations used by FilePetal."""

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "FilePetal"
APP_VERSION = "1.11.1"
APP_BUILD = 17


def app_root() -> Path:
    """Directory containing the application (frozen exe or source tree)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_root())) / "assets"


def tools_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "tools").is_dir():
        return Path(meipass) / "tools"
    return app_root() / "tools"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    # Migrate legacy settings from Tangerine if present and not yet in FilePetal
    old_path = base / "Tangerine"
    old_settings = old_path / "settings.json"
    new_settings = path / "settings.json"
    if old_settings.exists() and not new_settings.exists():
        try:
            shutil.copy2(old_settings, new_settings)
        except Exception:
            pass
    return path


def settings_file() -> Path:
    return data_dir() / "settings.json"


def log_file() -> Path:
    return data_dir() / "filepetal.log"


def icon_path() -> Path:
    return assets_dir() / ("tray.ico" if sys.platform == "win32" else "tray.png")


def icon_png() -> Path:
    return assets_dir() / "tray.png"


def highlight_sound() -> Path:
    return assets_dir() / "highlight.wav"
