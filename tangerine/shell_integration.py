"""Per-user Explorer integration for the packaged Tangerine application."""
from __future__ import annotations

import ctypes
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
import winreg

from . import paths

log = logging.getLogger("tangerine")
CLSID = "{7E2C14A9-8D31-4B76-A5F0-3C9D8216E4B2}"
OWNER = "FilePetal.ImagePdf"
HANDLER_KEY = r"Software\Classes\*\shellex\ContextMenuHandlers\FilePetal"
CLASS_KEY = rf"Software\Classes\CLSID\{CLSID}"
CONFIG_KEY = r"Software\FilePetal\ShellIntegration"
SHORTCUTS = {
    "FilePetal - Crear PDF.lnk": "--images-to-pdf",
    "FilePetal - PDF por nombre.lnk": "--images-to-pdf --pdf-order name --pdf-quick",
}


def _sendto_dir():
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/SendTo"


def _read(path, name=""):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None


def _delete_tree(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
        for child in children:
            _delete_tree(path + "\\" + child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


def _snapshot(path):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        count, values, _ = winreg.QueryInfoKey(key)
        return {"values": [winreg.EnumValue(key, i) for i in range(values)],
                "children": {name: _snapshot(path + "\\" + name)
                             for name in [winreg.EnumKey(key, i) for i in range(count)]}}


def _migrate_standalone():
    candidates = [
        (r"Software\Classes\*\shellex\ContextMenuHandlers\CrisImageToPdf", "CrisManagedBy", "CrisImageToPdfContextMenu"),
        (r"Software\Classes\CLSID\{AC3DB44B-09C1-4C40-9B71-71DD1BBF6D28}", "CrisManagedBy", "CrisImageToPdfContextMenu"),
        (r"Software\Classes\SystemFileAssociations\image\shell\CrisImageToPdf", "CrisManagedBy", "CrisImageToPdfContextMenu"),
        (r"Software\Classes\CLSID\{2E1C3A8E-8C4B-4B4B-996A-602B4F63E923}", "", "Cris Image to PDF Context Menu"),
    ]
    owned = [path for path, name, expected in candidates if _read(path, name) == expected]
    if not owned:
        return
    backup = paths.data_dir() / "backups" / ("standalone-shell-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps({path: _snapshot(path) for path in owned}, indent=2), encoding="utf-8")
    for path in owned:
        _delete_tree(path)
    log.info("Retired standalone PDF registrations; registry snapshot: %s", backup)


def _notify():
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)


def register_shell(executable=None):
    if executable is None:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Explorer integration requires a packaged FilePetal.exe.")
        executable = sys.executable
    executable = Path(executable).resolve()
    dll = executable.parent / "_internal/shell/TangerineShell.dll"
    if not executable.is_file() or not dll.is_file():
        raise FileNotFoundError("FilePetal.exe and its bundled shell/TangerineShell.dll are required.")
    # Validate every owned destination before changing the registration.
    for path in (HANDLER_KEY, CLASS_KEY, CONFIG_KEY):
        existing = _read(path, "TangerineOwner")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path):
                if existing != OWNER:
                    raise RuntimeError("Explorer registry key belongs to another application: " + path)
        except FileNotFoundError:
            pass
    from comtypes.client import CreateObject
    shell = CreateObject("WScript.Shell", dynamic=True)
    sendto = _sendto_dir()
    sendto.mkdir(parents=True, exist_ok=True)
    for filename, args in SHORTCUTS.items():
        link_path = sendto / filename
        shortcut = shell.CreateShortcut(str(link_path))
        if link_path.exists() and shortcut.TargetPath and Path(shortcut.TargetPath).name.casefold() not in ("filepetal.exe", "tangerine.exe"):
            raise RuntimeError("Send to shortcut belongs to another application: " + str(link_path))
        shortcut.TargetPath = str(executable)
        shortcut.Arguments = args
        shortcut.WorkingDirectory = str(executable.parent)
        shortcut.IconLocation = str(executable) + ",0"
        shortcut.WindowStyle = 7
        shortcut.Save()
    for path in (HANDLER_KEY, CLASS_KEY, CONFIG_KEY):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, "TangerineOwner", 0, winreg.REG_SZ, OWNER)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, HANDLER_KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, CLSID)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLASS_KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "FilePetal Image PDF menu")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLASS_KEY + r"\InprocServer32") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(dll))
        winreg.SetValueEx(key, "ThreadingModel", 0, winreg.REG_SZ, "Apartment")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CONFIG_KEY) as key:
        winreg.SetValueEx(key, "ExecutablePath", 0, winreg.REG_SZ, str(executable))
        winreg.SetValueEx(key, "DiagnosticLogging", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, paths.APP_VERSION)
    _migrate_standalone()
    _notify()
    return {"executable": str(executable), "dll": str(dll), "sendto": str(sendto)}


def unregister_shell():
    for path in (HANDLER_KEY, CLASS_KEY, CONFIG_KEY):
        if _read(path, "TangerineOwner") == OWNER:
            _delete_tree(path)
    from comtypes.client import CreateObject
    shell = CreateObject("WScript.Shell", dynamic=True)
    for filename in SHORTCUTS:
        link = _sendto_dir() / filename
        if link.exists() and Path(shell.CreateShortcut(str(link)).TargetPath).name.casefold() in ("filepetal.exe", "tangerine.exe"):
            link.unlink()
    _notify()
