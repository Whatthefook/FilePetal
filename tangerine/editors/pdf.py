"""Image PDF ordering editor using Tangerine's shared dialog and progress card."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
)

from .. import engines, i18n, progress, settings
from ..image_pdf import PdfOptions, is_pdf_image, ordered_paths
from .ui.controls import NumericSpinBox, NumericDoubleSpinBox
from .base import ToolDialog, align_form, chip_button

_OPEN = set()


class ImagesPdfDialog(ToolDialog):
    def __init__(self, files, parent=None, order=None):
        super().__init__(i18n.tr("pdf.images.title"), parent)
        self._paths = list(dict.fromkeys(Path(p) for p in files if is_pdf_image(Path(p)) and Path(p).is_file()))
        if not self._paths:
            raise engines.EngineError(i18n.tr("err.no_images"))
        self.resize(510, 520)
        self.setMinimumSize(440, 440)
        self.job_window = None
        self.intro = QLabel(i18n.tr("pdf.images.intro", count=len(self._paths)))
        self.intro.setWordWrap(True)
        self.intro.setProperty("dim", True)
        self._body.addWidget(self.intro)
        self.order = QComboBox()
        for value in ("name", "received", "manual"):
            self.order.addItem(i18n.tr("pdf.order." + value), value)
        initial = order or settings.get("imagePdfOrder", "name")
        if initial not in ("name", "received", "manual"):
            initial = "name"
        self.order.setCurrentIndex(max(0, self.order.findData(initial)))
        self._body.addWidget(self.order)
        hint = QLabel(i18n.tr("pdf.order.hint"))
        hint.setWordWrap(True)
        hint.setProperty("dim", True)
        self._body.addWidget(hint)

        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files.setMinimumHeight(120)
        self._body.addWidget(self.files, 1)
        row = QHBoxLayout()
        self.up = chip_button(i18n.tr("pdf.move.up"))
        self.down = chip_button(i18n.tr("pdf.move.down"))
        row.addWidget(self.up)
        row.addWidget(self.down)
        row.addStretch()
        add = chip_button(i18n.tr("pdf.add_images"))
        remove = chip_button(i18n.tr("pdf.remove_images"))
        add.clicked.connect(self.add_images)
        remove.clicked.connect(self.remove_images)
        row.addWidget(add)
        row.addWidget(remove)
        self._body.addLayout(row)
        self.up.clicked.connect(lambda: self.move_item(-1))
        self.down.clicked.connect(lambda: self.move_item(1))
        self.order.currentIndexChanged.connect(self._order_changed)
        self._render(ordered_paths(self._paths, initial))
        self._update_move_buttons()

        form = QFormLayout()
        align_form(form)
        layout_row = QHBoxLayout()
        self.rows = NumericSpinBox()
        self.columns = NumericSpinBox()
        for spin in (self.rows, self.columns):
            spin.setRange(1, 20)
        layout_row.addWidget(QLabel(i18n.tr("pdf.rows")))
        layout_row.addWidget(self.rows)
        layout_row.addWidget(QLabel(i18n.tr("pdf.columns")))
        layout_row.addWidget(self.columns)
        layout_row.addStretch()
        form.addRow(i18n.tr("pdf.layout"), layout_row)
        self.filenames = QCheckBox(i18n.tr("pdf.filenames"))
        form.addRow("", self.filenames)
        self.font_scale = NumericDoubleSpinBox()
        self.font_scale.setRange(0.2, 4.0)
        self.font_scale.setSingleStep(0.2)
        self.font_scale.setValue(1.0)
        self.font_scale.setEnabled(False)
        self.filenames.toggled.connect(self.font_scale.setEnabled)
        form.addRow(i18n.tr("pdf.font_scale"), self.font_scale)
        self.output = QLineEdit()
        self.output.setPlaceholderText(i18n.tr("pdf.output.auto"))
        self.output.setToolTip(i18n.tr("pdf.output.hint"))
        output_row = QHBoxLayout()
        output_row.addWidget(self.output, 1)
        browse = chip_button(i18n.tr("pdf.output.browse"))
        browse.clicked.connect(self._browse)
        output_row.addWidget(browse)
        form.addRow(i18n.tr("pdf.output"), output_row)
        self._body.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty("dim", True)
        self.error.hide()
        self._body.addWidget(self.error)
        self.add_buttons(i18n.tr("pdf.create"))

    def selected_paths(self):
        return [Path(self.files.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.files.count())]

    def _render(self, paths):
        self.files.clear()
        for index, path in enumerate(paths, 1):
            item = QListWidgetItem(f"{index:02d}   {path.name}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.files.addItem(item)

    def _order_changed(self):
        mode = self.order.currentData()
        if mode != "manual":
            self._render(ordered_paths(self._paths, mode))
        self._update_move_buttons()

    def _update_move_buttons(self):
        manual = self.order.currentData() == "manual"
        self.up.setEnabled(manual)
        self.down.setEnabled(manual)

    def move_item(self, delta):
        if self.order.currentData() != "manual":
            return
        selected = {self.files.row(item) for item in self.files.selectedItems()}
        if not selected:
            return
        if (delta < 0 and min(selected) == 0) or (delta > 0 and max(selected) == self.files.count() - 1):
            return
        paths = self.selected_paths()
        for index in sorted(selected, reverse=delta > 0):
            target = index + delta
            paths[index], paths[target] = paths[target], paths[index]
        self._render(paths)
        for index in selected:
            self.files.item(index + delta).setSelected(True)

    def add_images(self):
        selected, _ = QFileDialog.getOpenFileNames(self, i18n.tr("pdf.add_images"), "",
            "Images (*.jpg *.jpeg *.jpe *.jfif *.png *.bmp *.dib *.gif *.tif *.tiff *.webp *.ico *.heic *.heif *.avif *.svg)")
        visible = self.selected_paths()
        for name in selected:
            path = Path(name)
            if path.is_file() and is_pdf_image(path) and path not in self._paths:
                self._paths.append(path)
                visible.append(path)
        mode = self.order.currentData()
        self._render(visible if mode == "manual" else ordered_paths(self._paths, mode))
        self.intro.setText(i18n.tr("pdf.images.intro", count=len(self._paths)))

    def remove_images(self):
        removed = {Path(item.data(Qt.ItemDataRole.UserRole)) for item in self.files.selectedItems()}
        visible = [path for path in self.selected_paths() if path not in removed]
        self._paths = [path for path in self._paths if path not in removed]
        self._render(visible)
        self.intro.setText(i18n.tr("pdf.images.intro", count=len(self._paths)))

    def _browse(self):
        suggested = self._paths[0].with_suffix(".pdf") if self._paths else Path.home() / "images.pdf"
        path, _ = QFileDialog.getSaveFileName(self, i18n.tr("pdf.output"),
                    str(suggested), "PDF (*.pdf)")
        if path:
            self.output.setText(path)

    def _accept_clicked(self):
        if not self.files.count():
            self.error.setText(i18n.tr("err.no_images"))
            self.error.show()
            return
        chosen = self.output.text().strip()
        output = Path(chosen).with_suffix(".pdf") if chosen else None
        if output is not None and output.exists():
            self.error.setText(i18n.tr("pdf.output.exists"))
            self.error.show()
            return
        mode = self.order.currentData()
        options = PdfOptions(order="manual", rows=self.rows.value(), columns=self.columns.value(),
                             with_filenames=self.filenames.isChecked(), font_scale=self.font_scale.value(), output=output)
        files = self.selected_paths()
        settings.set("imagePdfOrder", mode)
        settings.save()
        self.job_window = progress.run_job(i18n.tr("action.creating_pdf"),
            lambda ctx: [engines.images_to_pdf(files, ctx, set(), options)], anchor=QCursor.pos())
        self.accept()


def open_images_pdf(files=None, parent=None, order=None):
    if not files:
        selected, _ = QFileDialog.getOpenFileNames(parent, i18n.tr("pdf.images.title"), "",
            "Images (*.jpg *.jpeg *.jpe *.jfif *.png *.bmp *.dib *.gif *.tif *.tiff *.webp *.ico *.heic *.heif *.avif *.svg)")
        if not selected:
            return None
        files = selected
    dialog = ImagesPdfDialog(files, parent, order)
    _OPEN.add(dialog)
    dialog.finished.connect(lambda *_: _OPEN.discard(dialog))
    dialog.open()
    return dialog
