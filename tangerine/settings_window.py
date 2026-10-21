"""Tabbed settings window (persisted through tangerine.settings)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import settings
from .media import ffmpeg_path, ffprobe_path, rar_path, unrar_path
from . import i18n, paths, theme, tool_defaults

_WINDOW = None


class ModifierChecks(QGroupBox):
    def __init__(self, title, key, parent=None):
        super().__init__(title, parent)
        self._key = key
        self._boxes: dict[str, QCheckBox] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(14)
        for mod in settings.MODIFIER_ORDER:
            box = QCheckBox(settings.MODIFIER_LABELS.get(mod, mod.title()))
            box.toggled.connect(self._changed)
            self._boxes[mod] = box
            layout.addWidget(box)
        layout.addStretch(1)
        self._load()

    def _load(self):
        mask = settings.parse_mask(str(settings.get(self._key, "")))
        if not mask:
            mask = {"shift"}
        for mod, box in self._boxes.items():
            box.blockSignals(True)
            box.setChecked(mod in mask)
            box.blockSignals(False)

    def _changed(self):
        mask = {mod for mod, box in self._boxes.items() if box.isChecked()}
        if not mask:
            sender = self.sender()
            if isinstance(sender, QCheckBox):
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
            mask = {mod for mod, box in self._boxes.items() if box.isChecked()}
        settings.set(self._key, settings.format_mask(mask))
        settings.save()


def _key_name(key: int) -> str | None:
    """Map a Qt key code to the token used by ``settings.parse_hotkey``."""
    letters = (int(Qt.Key.Key_A), int(Qt.Key.Key_Z))
    digits = (int(Qt.Key.Key_0), int(Qt.Key.Key_9))
    functions = (int(Qt.Key.Key_F1), int(Qt.Key.Key_F12))
    if letters[0] <= key <= letters[1]:
        return chr(key).lower()
    if digits[0] <= key <= digits[1]:
        return chr(key)
    if functions[0] <= key <= functions[1]:
        return f"f{key - functions[0] + 1}"
    if key == int(Qt.Key.Key_Space):
        return "space"
    return None


class HotkeyEdit(QLineEdit):
    """Read-only recorder: press the desired combo to bind the sticky wheel."""

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self._key = key
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._refresh()

    def _refresh(self):
        self.setText(settings.hotkey_label(str(settings.get(self._key, ""))))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clearFocus()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            settings.set(self._key, "")
            settings.save()
            self._refresh()
            event.accept()
            return
        mods = set()
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mods.add("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mods.add("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mods.add("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            mods.add("win")
        name = _key_name(int(event.key()))
        if mods and name:
            settings.set(self._key, settings.format_hotkey(mods, name))
            settings.save()
            self._refresh()
            event.accept()
            return
        event.ignore()


class _Row(QWidget):
    """A labelled combo row that can be filtered by the search box."""

    def __init__(self, label, combo, keywords="", parent=None):
        super().__init__(parent)
        self.keywords = (label + " " + keywords).lower()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        text = QLabel(label)
        text.setMinimumWidth(170)
        layout.addWidget(text)
        layout.addWidget(combo, 1)
        self.combo = combo


def _combo(entry: _Row, key: str, choices: list[tuple[str, str]]):
    combo = entry.combo
    for value, label in choices:
        combo.addItem(label, value)

    def _sync():
        index = combo.findData(str(settings.get(key, "")))
        if index >= 0 and index != combo.currentIndex():
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    _sync()
    combo._tangerine_sync = _sync

    def _changed():
        settings.set(key, combo.currentData())
        settings.save()

    combo.currentIndexChanged.connect(_changed)


def _make_row(label, key, choices, keywords=""):
    combo = QComboBox()
    row = _Row(label, combo, keywords)
    _combo(row, key, choices)
    return row


def _strength_choices():
    return [
        ("balanced", i18n.tr("settings.strength.balanced")),
        ("strong", i18n.tr("settings.strength.strong")),
    ]


def _size_choices():
    return [
        ("original", i18n.tr("settings.size.original")),
        ("2560", i18n.tr("settings.size.2560")),
        ("1920", i18n.tr("settings.size.1920")),
        ("1280", i18n.tr("settings.size.1280")),
    ]


def _page_size_choices():
    return [
        ("a4", i18n.tr("settings.formats.page_size.a4")),
        ("letter", i18n.tr("settings.formats.page_size.letter")),
    ]


def _margin_choices():
    return [
        ("normal", i18n.tr("settings.formats.margins.normal")),
        ("compact", i18n.tr("settings.formats.margins.compact")),
        ("wide", i18n.tr("settings.formats.margins.wide")),
    ]


class SettingsWindow(QWidget):
    def __init__(self, parent=None, pdf_callback=None):
        super().__init__(parent)
        self.setObjectName("SettingsRoot")
        self.pdf_callback = pdf_callback
        self.setWindowTitle(i18n.tr("settings.title"))
        self.resize(560, 620)
        self.setMinimumSize(500, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        tabs.addTab(self._wheels_tab(), i18n.tr("settings.tab.wheels"))
        tabs.addTab(self._formats_tab(), i18n.tr("settings.tab.formats"))
        tabs.addTab(self._defaults_tab(), i18n.tr("defaults.tab"))
        tabs.addTab(self._about_tab(), i18n.tr("settings.tab.about"))
        tabs.addTab(self._general_tab(), i18n.tr("settings.tab.general"))

    # ------------------------------------------------------------------

    def _defaults_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(i18n.tr("defaults.settings_hint"))
        hint.setWordWrap(True)
        hint.setProperty("dim", True)
        layout.addWidget(hint)
        labels = {"img.compress": "defaults.image_compress", "vid.compress": "defaults.video_compress",
                  "aud.compress": "defaults.audio_compress", "img.collage": "dlg.collage.title",
                  "img.background": "dlg.background.title"}
        self.default_option_checks = {}
        for key in tool_defaults.SUPPORTED:
            checkbox = QCheckBox(i18n.tr(labels[key]))
            checkbox.setChecked(tool_defaults.is_enabled(key))
            checkbox.setEnabled(tool_defaults.load_options(key) is not None)
            checkbox.setToolTip(i18n.tr("defaults.settings_tooltip"))
            checkbox.toggled.connect(lambda checked, k=key: tool_defaults.set_enabled(k, checked))
            self.default_option_checks[key] = checkbox
            layout.addWidget(checkbox)
        show_all = QPushButton(i18n.tr("defaults.show_all"))
        show_all.setCursor(Qt.CursorShape.PointingHandCursor)
        show_all.clicked.connect(self._show_all_options)
        layout.addWidget(show_all)
        layout.addStretch(1)
        return page

    def _show_all_options(self):
        for key, box in self.default_option_checks.items():
            tool_defaults.set_enabled(key, False)
            box.setChecked(False)

    def showEvent(self, event):
        for key, box in self.default_option_checks.items():
            box.blockSignals(True)
            box.setChecked(tool_defaults.is_enabled(key))
            box.setEnabled(tool_defaults.load_options(key) is not None)
            box.blockSignals(False)
        super().showEvent(event)

    def _general_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        form = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem(i18n.tr("settings.language.system"), "system")
        for code, label in i18n.LANGUAGES:
            self.language_combo.addItem(label, code)
        current = str(settings.get("language", i18n.DEFAULT_LANGUAGE) or i18n.DEFAULT_LANGUAGE)
        index = self.language_combo.findData(current)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        form.addRow(i18n.tr("settings.language.label"), self.language_combo)

        self.appearance_combo = QComboBox()
        self.appearance_combo.addItem(i18n.tr("settings.appearance.system"), "system")
        self.appearance_combo.addItem(i18n.tr("settings.appearance.light"), "light")
        self.appearance_combo.addItem(i18n.tr("settings.appearance.dark"), "dark")
        index = self.appearance_combo.findData(settings.appearance_theme())
        if index >= 0:
            self.appearance_combo.setCurrentIndex(index)
        self.appearance_combo.currentIndexChanged.connect(
            lambda _index: self._appearance_changed())
        form.addRow(i18n.tr("settings.appearance.label"), self.appearance_combo)
        layout.addLayout(form)

        hint = QLabel(i18n.tr("settings.language.hint"))
        hint.setWordWrap(True)
        hint.setObjectName("dim")
        layout.addWidget(hint)

        appearance_hint = QLabel(i18n.tr("settings.appearance.hint"))
        appearance_hint.setWordWrap(True)
        appearance_hint.setObjectName("dim")
        layout.addWidget(appearance_hint)

        self._fullscreen_box = QCheckBox(i18n.tr("settings.general.fullscreen"))
        self._fullscreen_box.setChecked(
            bool(settings.get("suppressInFullscreen", True))
        )

        def _fullscreen_changed(checked):
            settings.set("suppressInFullscreen", bool(checked))
            settings.save()

        self._fullscreen_box.toggled.connect(_fullscreen_changed)
        layout.addWidget(self._fullscreen_box)

        fullscreen_hint = QLabel(i18n.tr("settings.general.fullscreen_hint"))
        fullscreen_hint.setWordWrap(True)
        fullscreen_hint.setObjectName("dim")
        layout.addWidget(fullscreen_hint)
        explorer = QGroupBox(i18n.tr("shell.title"))
        explorer_layout = QVBoxLayout(explorer)
        explorer_hint = QLabel(i18n.tr("shell.hint"))
        explorer_hint.setWordWrap(True)
        explorer_layout.addWidget(explorer_hint)
        pdf_button = QPushButton(i18n.tr("pdf.images.title"))
        pdf_button.clicked.connect(self._open_images_pdf)
        explorer_layout.addWidget(pdf_button)
        repair_button = QPushButton(i18n.tr("shell.repair"))
        repair_button.clicked.connect(self._repair_explorer)
        explorer_layout.addWidget(repair_button)
        self._explorer_status = QLabel()
        self._explorer_status.setWordWrap(True)
        explorer_layout.addWidget(self._explorer_status)
        layout.addWidget(explorer)
        layout.addStretch(1)
        return page

    def _open_images_pdf(self):
        if self.pdf_callback is not None:
            return self.pdf_callback()
        from .editors.pdf import open_images_pdf
        return open_images_pdf()

    def _repair_explorer(self):
        import sys
        if not getattr(sys, "frozen", False):
            self._explorer_status.setText(i18n.tr("shell.source"))
            return
        try:
            from .shell_integration import register_shell
            register_shell()
            self._explorer_status.setText(i18n.tr("shell.ready"))
        except Exception as exc:
            self._explorer_status.setText(str(exc))

    def _language_changed(self):
        code = self.language_combo.currentData()
        if code:
            i18n.set_language(str(code))

    def _appearance_changed(self):
        settings.set("appearanceTheme", str(self.appearance_combo.currentData()))
        settings.save()
        theme.apply_app_theme()

    def _wheels_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        intro = QLabel(i18n.tr("settings.wheels.intro"))
        intro.setWordWrap(True)
        intro.setObjectName("dim")
        layout.addWidget(intro)

        self._conversion_checks = ModifierChecks(
            i18n.tr("settings.wheels.conversions"), "conversionWheelDragModifierMask")
        self._tools_checks = ModifierChecks(
            i18n.tr("settings.wheels.tools"), "toolsWheelDragModifierMask")
        self._actions_checks = ModifierChecks(
            i18n.tr("settings.wheels.actions"), "actionsWheelDragModifierMask")
        layout.addWidget(self._conversion_checks)
        layout.addWidget(self._tools_checks)
        layout.addWidget(self._actions_checks)

        sticky_group = QGroupBox(i18n.tr("settings.wheels.sticky"))
        sticky_layout = QVBoxLayout(sticky_group)
        sticky_hint = QLabel(i18n.tr("settings.wheels.sticky_hint"))
        sticky_hint.setWordWrap(True)
        sticky_hint.setObjectName("dim")
        sticky_layout.addWidget(sticky_hint)
        self._sticky_edit = HotkeyEdit("wheelToggleHotkey")
        sticky_layout.addWidget(self._sticky_edit)
        layout.addWidget(sticky_group)

        sounds = QCheckBox(i18n.tr("settings.wheels.sound"))
        sounds.setChecked(bool(settings.get("soundsAndHapticsEnabled", True)))

        def _toggle_sound(state):
            settings.set("soundsAndHapticsEnabled", bool(state))
            settings.save()

        sounds.toggled.connect(_toggle_sound)
        layout.addWidget(sounds)

        hint = QLabel(i18n.tr("settings.wheels.hint"))
        hint.setObjectName("dim")
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _formats_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        search = QLineEdit()
        search.setPlaceholderText(i18n.tr("settings.formats.search"))
        layout.addWidget(search)

        self._rows: list[_Row] = []
        self._groups: list[tuple[QGroupBox, list[tuple[QWidget, str]]]] = []

        image_group = QGroupBox(i18n.tr("settings.formats.images"))
        image_layout = QVBoxLayout(image_group)
        self._add_row(image_layout, i18n.tr("settings.formats.preset"),
                      "defaultImageCompressionStrength", _strength_choices(),
                      "compress jpg png quality")
        self._add_row(image_layout, i18n.tr("settings.formats.size"),
                      "defaultImageCompressionSize", _size_choices(),
                      "resize dimensions pixels")
        layout.addWidget(image_group)

        video_group = QGroupBox(i18n.tr("settings.formats.videos"))
        video_layout = QVBoxLayout(video_group)
        self._add_row(video_layout, i18n.tr("settings.formats.preset"),
                      "defaultVideoCompressionStrength", _strength_choices(),
                      "compress mp4 hevc bitrate")
        self._add_row(video_layout, i18n.tr("settings.formats.size"),
                      "defaultVideoCompressionSize", _size_choices(),
                      "resize dimensions pixels")
        layout.addWidget(video_group)

        audio_group = QGroupBox(i18n.tr("settings.formats.audio"))
        audio_layout = QVBoxLayout(audio_group)
        self._add_row(audio_layout, i18n.tr("settings.formats.preset"),
                      "defaultAudioCompressionStrength", _strength_choices(),
                      "compress mp3 m4a bitrate")
        layout.addWidget(audio_group)

        document_group = QGroupBox(i18n.tr("settings.formats.documents"))
        document_layout = QVBoxLayout(document_group)
        self._add_row(
            document_layout, i18n.tr("settings.formats.page_size"),
            "pdfPageSize", _page_size_choices(), "paper a4 letter print pdf")
        self._add_row(
            document_layout, i18n.tr("settings.formats.margins"),
            "pdfMarginPreset", _margin_choices(), "margins print pdf paper")
        self._page_numbers_box = QCheckBox(i18n.tr("settings.formats.page_numbers"))
        self._page_numbers_box.setChecked(bool(settings.get("pdfPageNumbers", True)))

        def _page_numbers_changed(checked):
            settings.set("pdfPageNumbers", bool(checked))
            settings.save()

        self._page_numbers_box.toggled.connect(_page_numbers_changed)
        document_layout.addWidget(self._page_numbers_box)
        self._track(document_group, self._page_numbers_box, "page numbers numbering pdf")

        documents_hint = QLabel(i18n.tr("settings.formats.documents_hint"))
        documents_hint.setWordWrap(True)
        documents_hint.setObjectName("dim")
        document_layout.addWidget(documents_hint)
        self._track(document_group, documents_hint, "documents pdf paper print margins")
        layout.addWidget(document_group)

        def _filter(text):
            needle = text.strip().lower()
            for row in self._rows:
                row.setVisible(not needle or needle in row.keywords)
            for group, widgets in self._groups:
                group_visible = False
                for widget, keywords in widgets:
                    matches = not needle or needle in keywords
                    widget.setVisible(matches)
                    group_visible = group_visible or matches
                group.setVisible(group_visible)

        search.textChanged.connect(_filter)
        layout.addStretch(1)
        return page

    def _track(self, group, widget, keywords=""):
        text = str(getattr(widget, "keywords", keywords)).lower()
        for known_group, widgets in self._groups:
            if known_group is group:
                widgets.append((widget, text))
                return
        self._groups.append((group, [(widget, text)]))

    def _add_row(self, parent_layout, label, key, choices, keywords="", group=None):
        row = _make_row(label, key, choices, keywords)
        parent_layout.addWidget(row)
        self._rows.append(row)
        if group is None:
            group = parent_layout.parentWidget()
        if isinstance(group, QGroupBox):
            self._track(group, row)
        return row

    def _about_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        title = QLabel(i18n.tr(
            "settings.about.title",
            version=paths.APP_VERSION, build=paths.APP_BUILD,
        ))
        font = title.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        blurb = QLabel(i18n.tr("settings.about.blurb"))
        blurb.setWordWrap(True)
        blurb.setObjectName("dim")
        layout.addWidget(blurb)

        not_found = i18n.tr("settings.about.not_found")

        # Dependency and Offline Status
        dep_group = QGroupBox("Dependencies & Status")
        dep_layout = QVBoxLayout(dep_group)
        dep_layout.setSpacing(4)

        import importlib.util
        def _pkg_status(pkg):
            return "Active (Local)" if importlib.util.find_spec(pkg) else not_found

        dep_rows = [
            ("Offline Mode", "Enabled (Zero network / Zero cloud)"),
            (i18n.tr("settings.about.ffmpeg"), ffmpeg_path() or not_found),
            (i18n.tr("settings.about.ffprobe"), ffprobe_path() or not_found),
            ("Pillow / HEIF", _pkg_status("PIL") + " / " + _pkg_status("pillow_heif")),
            ("PDFium / ReportLab", _pkg_status("pypdfium2") + " / " + _pkg_status("reportlab")),
            ("Office (Docx / XLSX / PPTX)", _pkg_status("docx") + " / " + _pkg_status("openpyxl") + " / " + _pkg_status("pptx")),
            ("OCR (ONNXRuntime)", _pkg_status("onnxruntime")),
            (i18n.tr("settings.about.settings_file"), str(paths.settings_file())),
            (i18n.tr("settings.about.log"), str(paths.log_file())),
        ]
        for name, value in dep_rows:
            row = QLabel(f"<b>{name}:</b> {value}")
            row.setWordWrap(True)
            row.setObjectName("dim")
            dep_layout.addWidget(row)
        layout.addWidget(dep_group)

        buttons = QHBoxLayout()
        folder = QPushButton(i18n.tr("settings.about.open_folder"))
        folder.setProperty("flat", "true")
        folder.clicked.connect(self._open_folder)
        reset = QPushButton(i18n.tr("settings.about.restore"))
        reset.setProperty("flat", "true")
        reset.clicked.connect(self._reset)
        buttons.addWidget(folder)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def _open_folder(self):
        import subprocess

        data = paths.data_dir()
        subprocess.Popen(["explorer", str(data)])

    def _reset(self):
        confirm = QMessageBox.question(
            self,
            i18n.tr("settings.restore.title"),
            i18n.tr("settings.restore.confirm"),
        )
        if confirm != QMessageBox.Yes:
            return
        settings.update(dict(settings.DEFAULTS))
        settings.save()
        for checks in (getattr(self, "_conversion_checks", None), getattr(self, "_tools_checks", None)):
            if checks is not None:
                checks._load()
        for row in getattr(self, "_rows", []):
            sync = getattr(row.combo, "_tangerine_sync", None)
            if callable(sync):
                sync()
        box = getattr(self, "_page_numbers_box", None)
        if box is not None:
            box.blockSignals(True)
            box.setChecked(bool(settings.get("pdfPageNumbers", True)))
            box.blockSignals(False)
        box = getattr(self, "_fullscreen_box", None)
        if box is not None:
            box.blockSignals(True)
            box.setChecked(bool(settings.get("suppressInFullscreen", True)))
            box.blockSignals(False)
        self._sync_language_combo()
        self._sync_appearance_combo()
        theme.apply_app_theme()
        QMessageBox.information(
            self, i18n.tr("app.name"), i18n.tr("settings.restore.done"))

    def _sync_language_combo(self):
        combo = getattr(self, "language_combo", None)
        if combo is None:
            return
        current = str(settings.get("language", i18n.DEFAULT_LANGUAGE) or i18n.DEFAULT_LANGUAGE)
        index = combo.findData(current)
        if index >= 0 and index != combo.currentIndex():
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        i18n.set_language(current)

    def _sync_appearance_combo(self):
        combo = getattr(self, "appearance_combo", None)
        if combo is None:
            return
        index = combo.findData(settings.appearance_theme())
        if index >= 0 and index != combo.currentIndex():
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)


def open_settings(parent=None, pdf_callback=None):
    global _WINDOW
    if _WINDOW is None:
        _WINDOW = SettingsWindow(parent, pdf_callback=pdf_callback)
    elif pdf_callback is not None:
        _WINDOW.pdf_callback = pdf_callback
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW
