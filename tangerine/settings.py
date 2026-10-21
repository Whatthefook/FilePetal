"""Persistent settings, mirroring the macOS app's UserDefaults keys."""

from __future__ import annotations

import json
import logging
import os
import string
import threading
from typing import Any

from . import paths

log = logging.getLogger("tangerine")

DEFAULTS: dict[str, Any] = {
    "language": "en",
    "appearanceTheme": "system",
    "conversionWheelDragModifierMask": "shift",
    "toolsWheelDragModifierMask": "alt+shift",
    "actionsWheelDragModifierMask": "ctrl+shift",
    "wheelToggleHotkey": "ctrl+shift+w",
    "soundsAndHapticsEnabled": True,
    "conversionFanTheme": "glass",
    "touchLongPressEnabled": False,
    "defaultImageCompressionStrength": "balanced",
    "defaultImageCompressionSize": "original",
    "defaultVideoCompressionStrength": "balanced",
    "defaultVideoCompressionSize": "original",
    "defaultAudioCompressionStrength": "balanced",
    "imageCompressionTargetEnabled": False,
    "imageCompressionTargetKB": 0,
    "collageLayout": "grid",
    "collageSpacing": 12,
    "collagePadding": 24,
    "collageCornerRadius": 12,
    "collageBackground": "white",
    "collageCellShape": "square",
    "collageResolution": "source",
    "collageFit": "fill",
    "joinVideosFPSCap": 30,
    "videoCompressionAccurate": True,
    "pdfPageSize": "a4",
    "pdfMarginPreset": "normal",
    "pdfPageNumbers": True,
    "imagePdfOrder": "name",
    "toolSkipOptions": {},
    "toolDefaultOptions": {},
    "suppressInFullscreen": True,
    "welcomeShown": False,
}

_lock = threading.Lock()
_cache: dict[str, Any] | None = None

APPEARANCE_DEFAULT = "system"
APPEARANCE_VALUES = ("system", "light", "dark")

#: Paper and margin keys must mirror ``render.PAGE_SIZES_MM``/``MARGIN_PRESETS_MM``.
PAGE_SIZE_VALUES = ("a4", "letter")
MARGIN_PRESET_VALUES = ("normal", "compact", "wide")


def appearance_theme() -> str:
    """The validated appearance override: ``system``, ``light`` or ``dark``."""
    return get("appearanceTheme", APPEARANCE_DEFAULT)


def load() -> dict[str, Any]:
    with _lock:
        return _ensure_cache()


def _ensure_cache() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    data = dict(DEFAULTS)
    path = paths.settings_file()
    try:
        if path.exists():
            stored = json.loads(path.read_text("utf-8"))
            if isinstance(stored, dict):
                data.update(stored)
    except json.JSONDecodeError:
        log.exception("Settings file is corrupt; restoring defaults")
        try:
            os.replace(path, path.with_suffix(".json.bak"))
        except OSError:
            log.exception("Could not back up corrupt settings file")
    except Exception:
        pass
    _cache = data
    return _cache


def get(key: str, default: Any = None) -> Any:
    data = load()
    if key in data:
        return _normalize(key, data[key])
    if default is not None:
        return _normalize(key, default)
    return _normalize(key, DEFAULTS.get(key))


def _normalize(key: str, value: Any) -> Any:
    """Coerce stored values that users (or older builds) may have corrupted."""
    if key == "appearanceTheme":
        text = str(value or "").lower()
        return text if text in APPEARANCE_VALUES else APPEARANCE_DEFAULT
    if key in ("touchLongPressEnabled", "pdfPageNumbers", "suppressInFullscreen", "welcomeShown"):
        return bool(value)
    if key == "pdfPageSize":
        text = str(value or "").lower()
        return text if text in PAGE_SIZE_VALUES else DEFAULTS["pdfPageSize"]
    if key == "pdfMarginPreset":
        text = str(value or "").lower()
        return text if text in MARGIN_PRESET_VALUES else DEFAULTS["pdfMarginPreset"]
    return value


def set(key: str, value: Any) -> None:
    with _lock:
        data = _ensure_cache()
        if data.get(key) == value:
            return
        data[key] = value
        _save()


def update(values: dict[str, Any]) -> None:
    with _lock:
        data = _ensure_cache()
        changed = False
        for key, value in values.items():
            if data.get(key) != value:
                data[key] = value
                changed = True
        if changed:
            _save()


def save() -> None:
    with _lock:
        _save()


def _save() -> None:
    try:
        payload = json.dumps(_cache or DEFAULTS, indent=2, ensure_ascii=False)
        final = paths.settings_file()
        tmp = final.with_suffix(".json.tmp")
        tmp.write_text(payload, "utf-8")
        os.replace(tmp, final)
    except Exception:
        pass


MODIFIER_ORDER = ["ctrl", "alt", "shift", "win"]
MODIFIER_LABELS = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
}
MODIFIER_QT = {
    "ctrl": "Control",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Meta",
}


_ALIASES = {
    "control": "ctrl",
    "option": "alt",
    "cmd": "win",
    "command": "win",
    "meta": "win",
}


def parse_mask(text: str) -> set[str]:
    parts = {p.strip().lower() for p in str(text or "").split("+")}
    return {_ALIASES.get(p, p) for p in parts if _ALIASES.get(p, p) in MODIFIER_ORDER}


def format_mask(mask: set[str]) -> str:
    ordered = [m for m in MODIFIER_ORDER if m in mask]
    return "+".join(ordered)


def mask_label(text: str) -> str:
    from . import i18n

    mask = parse_mask(text)
    if not mask:
        return i18n.tr("settings.mask.none")
    return " + ".join(MODIFIER_LABELS[m] for m in MODIFIER_ORDER if m in mask)


HOTKEY_KEYS = (
    {letter for letter in string.ascii_lowercase}
    | {digit for digit in string.digits}
    | {f"f{number}" for number in range(1, 13)}
    | {"space"}
)


def _key_label(key: str) -> str:
    return "Space" if key == "space" else key.upper()


def parse_hotkey(text: str) -> tuple[set[str], str] | None:
    """Parse ``ctrl+shift+w`` into (modifier mask, key). None when invalid."""
    tokens = [token.strip().lower() for token in str(text or "").split("+")]
    tokens = [token for token in tokens if token]
    mask: list[str] = []
    key: str | None = None
    for token in tokens:
        name = _ALIASES.get(token, token)
        if name in MODIFIER_ORDER:
            if name not in mask:
                mask.append(name)
        elif name in HOTKEY_KEYS and key is None:
            key = name
        else:
            return None
    if not mask or key is None:
        return None
    return {name for name in mask}, key


def format_hotkey(mask: set[str], key: str) -> str:
    return "+".join([part for part in (format_mask(mask), key) if part])


def hotkey_label(text: str) -> str:
    from . import i18n

    combo = parse_hotkey(text)
    if combo is None:
        return i18n.tr("settings.mask.none")
    mask, key = combo
    parts = [MODIFIER_LABELS[m] for m in MODIFIER_ORDER if m in mask]
    parts.append(_key_label(key))
    return " + ".join(parts)
