"""Tangerine visual theme: colors, palette helpers, shared stylesheets.

The macOS app draws a frosted "liquid glass" fan with an orange accent taken
from the app icon. On Windows the same language is expressed with rounded
corners, translucent surfaces and the orange accent.

Two token families are exposed:

* :func:`palette` — the QSS palette used by the settings window and dialogs.
* :func:`hud` — the HUD material tokens (translucent washes, halo, hub and
  chips) shared by the wheel, the progress card and the editors.

The appearance is resolved by :func:`appearance_mode` / :func:`is_dark` and
can be overridden with the ``appearanceTheme`` setting (``system``, ``light``
or ``dark``).  :func:`apply_app_theme` republishes the stylesheet on the
running ``QApplication`` and notifies every :func:`add_theme_listener`
callback so open windows can repaint.
"""

from __future__ import annotations

import logging

log = logging.getLogger("tangerine")

ACCENT = "#F87800"
ACCENT_BRIGHT = "#F8A850"
ACCENT_DARK = "#D96800"

FAN_PETAL_RADIUS = 148.0
FAN_CENTER_RADIUS = 46.0
FAN_HOVER_LIFT = 10.0

APPEARANCE_DEFAULT = "system"
APPEARANCE_VALUES = ("system", "light", "dark")

LIGHT = {
    "window": "#F5F3F0",
    "card": "#FFFFFF",
    "card_alt": "#F7F5F2",
    "text": "#1D1B18",
    "text_dim": "#6E6A64",
    "border": "#E2DED8",
    "field": "#FFFFFF",
    "hover": "#F1EDE8",
    "glass": (250, 248, 245, 235),
    "glass_edge": (200, 193, 184, 220),
    "petal": (255, 255, 255, 240),
    "petal_edge": (214, 208, 200, 235),
    "petal_text": "#26231F",
    "shadow": (0, 0, 0, 70),
    "slider_track": "rgba(0, 0, 0, 40)",
    "slider_thumb": "#FFFFFF",
    "slider_thumb_edge": "rgba(0, 0, 0, 55)",
}

DARK = {
    "window": "#1C1A18",
    "card": "#26241F",
    "card_alt": "#2E2B26",
    "text": "#F2EFEA",
    "text_dim": "#A6A099",
    "border": "#3A3733",
    "field": "#2A2723",
    "hover": "#332F2A",
    "glass": (32, 30, 27, 235),
    "glass_edge": (90, 84, 77, 220),
    "petal": (44, 41, 37, 240),
    "petal_edge": (96, 89, 81, 235),
    "petal_text": "#F2EFEA",
    "shadow": (0, 0, 0, 120),
    "slider_track": "rgba(255, 255, 255, 45)",
    "slider_thumb": "#FFFFFF",
    "slider_thumb_edge": "rgba(255, 255, 255, 75)",
}

# HUD material tokens (v1.7.0).  Colors are ``(r, g, b, a)`` tuples except
# ``peach`` and ``icon``, which are opaque ``#rrggbb`` strings.
HUD_LIGHT = {
    "wash": (255, 248, 242, 135),
    "halo": (125, 110, 100, 95),
    "hub": (255, 252, 249, 215),
    "peach": "#FFD9C2",
    "track": (0, 0, 0, 50),
    "icon": "#3A2416",
}

HUD_DARK = {
    "wash": (24, 21, 19, 130),
    "halo": (20, 16, 14, 120),
    "hub": (36, 30, 26, 215),
    "peach": "#3A2A20",
    "track": (255, 255, 255, 40),
    "icon": "#F3E7DE",
}

_theme_listeners: list = []


def palette(dark: bool) -> dict:
    """The QSS palette (window, card, text, borders, slider tokens)."""
    return DARK if dark else LIGHT


def hud(dark: bool) -> dict:
    """The HUD material tokens for *dark* or light surfaces.

    Keys: ``wash`` (warm wash painted over the blurred backdrop), ``halo``
    (translucent disc behind the wheel), ``hub`` (wheel hub capsule),
    ``peach`` (chip fill), ``track`` (progress rails, slider grooves) and
    ``icon`` (monochrome line icons, chip text).
    """
    return HUD_DARK if dark else HUD_LIGHT


def qcolor(token):
    """Convert a palette token (``#rrggbb`` or ``(r, g, b[, a])``) to QColor."""
    from PySide6.QtGui import QColor

    if isinstance(token, QColor):
        return QColor(token)
    if isinstance(token, (tuple, list)):
        return QColor(*token)
    return QColor(str(token))


def appearance_mode() -> str:
    """The persisted appearance override: ``system``, ``light`` or ``dark``.

    Unknown values fall back to ``system``; missing settings packages (during
    headless imports) resolve the same way.
    """
    try:
        from . import settings

        value = settings.get("appearanceTheme", APPEARANCE_DEFAULT)
    except Exception:
        value = APPEARANCE_DEFAULT
    mode = str(value or APPEARANCE_DEFAULT).lower()
    return mode if mode in APPEARANCE_VALUES else APPEARANCE_DEFAULT


def is_dark() -> bool:
    """Whether surfaces should use the dark palette.

    ``appearanceTheme`` wins when it is ``light`` or ``dark``; ``system``
    follows the Qt color-scheme hint and defaults to light without a
    ``QGuiApplication``.
    """
    mode = appearance_mode()
    if mode == "light":
        return False
    if mode == "dark":
        return True
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return False
        from PySide6.QtCore import Qt

        scheme = app.styleHints().colorScheme()
        return scheme == Qt.ColorScheme.Dark
    except Exception:
        return False


def add_theme_listener(callback) -> None:
    """Register *callback*, invoked with the resolved ``dark`` flag."""
    if callback not in _theme_listeners:
        _theme_listeners.append(callback)


def remove_theme_listener(callback) -> None:
    """Unregister a callback added with :func:`add_theme_listener`."""
    if callback in _theme_listeners:
        _theme_listeners.remove(callback)


def refresh_listeners(dark: bool | None = None) -> None:
    """Notify every theme listener; *dark* defaults to the current mode."""
    if dark is None:
        dark = is_dark()
    for callback in list(_theme_listeners):
        try:
            callback(bool(dark))
        except Exception:
            log.exception("Theme listener failed")


def apply_app_theme() -> bool:
    """Apply :func:`stylesheet` for the resolved appearance to the application.

    Safe to call headless (returns ``False`` when there is no ``QApplication``)
    and safe to call repeatedly.  Listeners registered with
    :func:`add_theme_listener` are notified afterwards.
    """
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
    except Exception:
        log.debug("Qt widgets unavailable; the app stylesheet was not applied",
                  exc_info=True)
        return False
    if app is None:
        return False
    dark = is_dark()
    app.setStyleSheet(stylesheet(dark))
    refresh_listeners(dark)
    return True


def rgba(c) -> str:
    if isinstance(c, str):
        return c
    r, g, b, a = c
    return f"rgba({r}, {g}, {b}, {a})"


def stylesheet(dark: bool) -> str:
    p = palette(dark)
    h = hud(dark)
    return f"""
    QWidget {{
        color: {p['text']};
        font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog, #SettingsRoot {{
        background: {p['window']};
    }}
    QTabWidget::pane {{
        border: 1px solid {p['border']};
        border-radius: 10px;
        background: {p['card']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {p['text_dim']};
        padding: 7px 14px;
        margin-right: 4px;
        border-radius: 7px;
    }}
    QTabBar::tab:selected {{
        background: {p['card']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-bottom-color: {p['card']};
    }}
    QTabBar::tab:hover:!selected {{
        background: {p['hover']};
        color: {p['text']};
    }}
    QGroupBox {{
        border: 1px solid {p['border']};
        border-radius: 10px;
        background: {p['card_alt']};
        margin-top: 12px;
        padding: 12px 10px 10px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {p['text_dim']};
    }}
    QPushButton {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background: {p['hover']};
    }}
    QPushButton:pressed {{
        background: {p['card_alt']};
    }}
    QPushButton:disabled {{
        color: {p['text_dim']};
    }}
    QPushButton[accent="true"] {{
        background: {ACCENT};
        border: 1px solid {ACCENT_DARK};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{
        background: {ACCENT_BRIGHT};
    }}
    QPushButton[accent="true"]:disabled {{
        background: {p['card_alt']};
        border-color: {p['border']};
        color: {p['text_dim']};
    }}
    QPushButton[flat="true"] {{
        background: transparent;
        border: none;
        color: {ACCENT};
        padding: 4px 6px;
    }}
    QPushButton[flat="true"]:hover {{
        color: {ACCENT_BRIGHT};
    }}
    QPushButton[chip="true"] {{
        background: {h['peach']};
        border: none;
        border-radius: 9px;
        padding: 5px 12px;
        color: {h['icon']};
        font-weight: 600;
    }}
    QPushButton[chip="true"]:hover {{
        background: {ACCENT_BRIGHT};
        color: #FFFFFF;
    }}
    QPushButton[chip="true"]:pressed {{
        background: {ACCENT};
        color: #FFFFFF;
    }}
    QPushButton[chip="true"]:disabled {{
        background: {p['card_alt']};
        color: {p['text_dim']};
    }}
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {p['field']};
        border: 1px solid {p['border']};
        border-radius: 7px;
        padding: 5px 8px;
        selection-background-color: {ACCENT};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {ACCENT};
    }}
    QSpinBox[numericControl="true"], QDoubleSpinBox[numericControl="true"] {{
        min-height: 50px;
        min-width: 92px;
        padding: 4px 6px;
    }}
    QToolButton[numericStepButton="true"] {{
        background: {p['card_alt']};
        border: none;
        padding: 0;
        color: {p['text_dim']};
    }}
    QToolButton[numericStepButton="true"][stepDirection="up"] {{
        border-top-right-radius: 6px;
    }}
    QToolButton[numericStepButton="true"][stepDirection="down"] {{
        border-bottom-right-radius: 6px;
        border-top: 1px solid {p['border']};
    }}
    QToolButton[numericStepButton="true"]:hover {{
        background: {ACCENT_BRIGHT};
        color: #3A2416;
    }}
    QToolButton[numericStepButton="true"]:pressed {{
        background: {ACCENT_DARK};
        color: #FFFFFF;
    }}
    QToolButton[numericStepButton="true"]:disabled {{
        background: {p['field']};
        color: {p['border']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['card']};
        border: 1px solid {p['border']};
        selection-background-color: {ACCENT};
        selection-color: #FFFFFF;
        outline: none;
    }}
    QCheckBox, QRadioButton {{
        spacing: 7px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p['border']};
        background: {p['field']};
    }}
    QCheckBox::indicator {{
        border-radius: 4px;
    }}
    QRadioButton::indicator {{
        border-radius: 8px;
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT_DARK};
        image: none;
    }}
    QRadioButton::indicator:checked {{
        background: {ACCENT};
        border: 4px solid {ACCENT};
    }}
    QSlider::groove:horizontal {{
        height: 5px;
        background: {p['slider_track']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {p['slider_thumb']};
        border: 1px solid {p['slider_thumb_edge']};
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{
        border-color: {ACCENT};
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border']}; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['text_dim']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['border']}; border-radius: 4px; min-width: 24px;
    }}
    QMenu {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 22px 6px 12px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {ACCENT};
        color: #FFFFFF;
    }}
    QMenu::separator {{
        height: 1px; background: {p['border']}; margin: 4px 8px;
    }}
    QLabel[muted="true"], QLabel[dim="true"], QLabel#dim {{ color: {p['text_dim']}; }}
    QToolTip {{
        background: {p['card']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    QListWidget, QTreeWidget, QTableWidget {{
        background: {p['field']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        outline: none;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 5px 6px;
        border-radius: 6px;
    }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background: {ACCENT};
        color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: {p['card_alt']};
        border: none;
        border-bottom: 1px solid {p['border']};
        padding: 5px 8px;
        font-weight: 600;
    }}
    QProgressBar {{
        border: 1px solid {p['border']};
        border-radius: 6px;
        background: {p['card_alt']};
        text-align: center;
        color: {p['text']};
        height: 12px;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 5px;
    }}
    """
