"""Photo editors: compress, collage, crop, redact, background, edit,
annotate and metadata.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PIL import ImageOps

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import i18n, progress, settings, tools
from .base import (
    ToolDialog,
    align_form,
    chip_button,
    pil_to_qimage,
    run_batch,
    section_label,
)
from .ui.canvas import AnnotateCanvas, CropCanvas, RedactCanvas, _draw_op
from .ui.controls import NumericSpinBox


# ---------------------------------------------------------------------------
# Compress
# ---------------------------------------------------------------------------

class CompressDialog(ToolDialog):
    def __init__(self, paths, family: str, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.compress.title"), parent)
        self._paths = [Path(p) for p in paths]
        self._family = family
        count = len(self._paths)
        heading = QLabel(
            self._paths[0].name if count == 1
            else i18n.tr("dlg.count_files", count=count)
        )
        heading.setProperty("dim", True)
        self._body.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(10)
        align_form(form)
        self.strength = QComboBox()
        self.strength.addItems([i18n.tr("opt.balanced"), i18n.tr("opt.strong")])
        form.addRow(i18n.tr("lbl.compression_preset"), self.strength)

        self.size = QComboBox()
        self.size.addItems([i18n.tr("opt.original"), i18n.tr("opt.limit_2560"),
                            i18n.tr("opt.limit_1920"), i18n.tr("opt.limit_1280")])
        self.size_row = self.size
        form.addRow(i18n.tr("lbl.dimensions"), self.size)

        self.target_check = QCheckBox(i18n.tr("dlg.compress.target"))
        self.target_kb = NumericSpinBox()
        self.target_kb.setRange(1, 1024 * 1024)
        self.target_kb.setValue(500)
        self.target_kb.setSuffix(" KB")
        self.target_kb.setEnabled(False)
        self.target_check.toggled.connect(self.target_kb.setEnabled)
        form.addRow(self.target_check, self.target_kb)
        self._body.addLayout(form)

        note = QLabel(i18n.tr("dlg.compress.note"))
        note.setWordWrap(True)
        note.setProperty("dim", True)
        self._body.addWidget(note)

        if family == "image":
            self.strength.setCurrentIndex(
                1 if settings.get("defaultImageCompressionStrength") == "strong" else 0)
            sizes = ["original", "2560", "1920", "1280"]
            current = str(settings.get("defaultImageCompressionSize", "original"))
            self.size.setCurrentIndex(sizes.index(current) if current in sizes else 0)
        else:
            self.size_row.setVisible(False)
            self.target_check.setVisible(False)
            self.target_kb.setVisible(False)
            key = "defaultVideoCompressionStrength" if family == "video" else "defaultAudioCompressionStrength"
            self.strength.setCurrentIndex(1 if settings.get(key) == "strong" else 0)
        options = self.configure_defaults({"image": "img", "video": "vid", "audio": "aud"}[family] + ".compress")
        if options:
            self.strength.setCurrentIndex(int(options["strength"] == "strong"))
            if family == "image":
                self.size.setCurrentIndex(["original", "2560", "1920", "1280"].index(options["size"]))
                self.target_kb.setValue(options["target_kb"])
                self.target_check.setChecked(options["target_enabled"])
        self.add_buttons(i18n.tr("dlg.compress.title"))

    def save_defaults(self) -> None:
        strength = "strong" if self.strength.currentIndex() == 1 else "balanced"
        if self._family == "image":
            settings.set("defaultImageCompressionStrength", strength)
            size = ["original", "2560", "1920", "1280"][self.size.currentIndex()]
            settings.set("defaultImageCompressionSize", size)
        elif self._family == "video":
            settings.set("defaultVideoCompressionStrength", strength)
        else:
            settings.set("defaultAudioCompressionStrength", strength)
        settings.save()

    def _accept_clicked(self) -> None:
        strength = "strong" if self.strength.currentIndex() == 1 else "balanced"
        max_edge = None
        if self._family == "image" and self.size.currentIndex() > 0:
            max_edge = int(["", "2560", "1920", "1280"][self.size.currentIndex()])
        target = None
        if self._family == "image" and self.target_check.isChecked():
            target = max(1024, self.target_kb.value() * 1024)
        self.save_defaults()

        options = {"strength": strength}
        if self._family == "image":
            options.update(size=["original", "2560", "1920", "1280"][self.size.currentIndex()],
                           target_enabled=self.target_check.isChecked(), target_kb=self.target_kb.value())
        self.remember_options(options)

        if self._family == "image":
            self.job_window = run_batch(self._paths, lambda p, ctx, reserved: tools.compress_image(
                p, strength, max_edge, target, ctx, reserved), i18n.tr("action.compressing_generic"))
        elif self._family == "video":
            self.job_window = run_batch(self._paths, lambda p, ctx, reserved: tools.compress_video(
                p, strength, ctx, reserved), i18n.tr("action.compressing_generic"))
        else:
            self.job_window = run_batch(self._paths, lambda p, ctx, reserved: tools.compress_audio(
                p, strength, ctx, reserved), i18n.tr("action.compressing_generic"))
        self.accept()


# ---------------------------------------------------------------------------
# Collage
# ---------------------------------------------------------------------------

class CollageDialog(ToolDialog):
    def __init__(self, paths, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.collage.title"), parent)
        self._paths = [Path(p) for p in paths]
        self._thumb_dir = Path(tempfile.mkdtemp(prefix="tangerine_collage_"))
        self._thumbs: dict[Path, Path] = {}
        self._make_thumbs()
        self.finished.connect(self._cleanup_thumbs)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(280)
        self._preview_timer.timeout.connect(self._refresh_preview)

        top = QHBoxLayout()
        top.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(9)
        align_form(form)
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([i18n.tr("opt.grid"), i18n.tr("opt.horizontal"),
                                    i18n.tr("opt.vertical"), i18n.tr("opt.featured")])
        form.addRow(i18n.tr("lbl.layout"), self.layout_combo)

        self.resolution = QComboBox()
        self.resolution.addItems([i18n.tr("opt.source_size"), i18n.tr("opt.px2000"),
                                  i18n.tr("opt.px1500"), i18n.tr("opt.px1080")])
        form.addRow(i18n.tr("lbl.image_area"), self.resolution)

        self.fit = QComboBox()
        self.fit.addItems([i18n.tr("opt.fill"), i18n.tr("opt.contain")])
        form.addRow(i18n.tr("lbl.image_fit"), self.fit)

        self.spacing = NumericSpinBox()
        self.spacing.setRange(0, 96)
        form.addRow(i18n.tr("lbl.spacing"), self.spacing)

        self.padding = NumericSpinBox()
        self.padding.setRange(0, 160)
        form.addRow(i18n.tr("lbl.padding"), self.padding)

        self.radius = NumericSpinBox()
        self.radius.setRange(0, 64)
        form.addRow(i18n.tr("lbl.rounded_corners"), self.radius)

        self.background = QComboBox()
        self.background.addItems([i18n.tr("opt.white"), i18n.tr("opt.black"),
                                  i18n.tr("opt.transparent")])
        form.addRow(i18n.tr("lbl.background"), self.background)
        top.addLayout(form)

        self.preview = QLabel()
        self.preview.setFixedSize(330, 250)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setProperty("card", True)
        self.preview.setStyleSheet(
            "background: rgba(127,127,127,0.12); border-radius: 10px;"
        )
        top.addWidget(self.preview)
        self._body.addLayout(top)

        order_group = QGroupBox(i18n.tr("lbl.order"))
        order_layout = QHBoxLayout(order_group)
        self.order_list = QListWidget()
        self.order_list.setFixedHeight(96)
        order_layout.addWidget(self.order_list, 1)
        buttons = QVBoxLayout()
        up = chip_button(i18n.tr("btn.move_up"))
        down = chip_button(i18n.tr("btn.move_down"))
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        buttons.addWidget(up)
        buttons.addWidget(down)
        order_layout.addLayout(buttons)
        self._body.addWidget(order_group)

        for path in self._paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.order_list.addItem(item)

        defaults = {
            "layout": settings.get("collageLayout", "grid"),
            "spacing": settings.get("collageSpacing", 12),
            "padding": settings.get("collagePadding", 24),
            "corner_radius": settings.get("collageCornerRadius", 12),
            "background": settings.get("collageBackground", "white"),
            "resolution": settings.get("collageResolution", "source"),
            "fit": settings.get("collageFit", "fill"),
        }
        defaults.update(self.configure_defaults("img.collage") or {})
        layouts = ["grid", "horizontal", "vertical", "featured"]
        self.layout_combo.setCurrentIndex(
            layouts.index(defaults["layout"]) if defaults["layout"] in layouts else 0)
        self.spacing.setValue(int(defaults["spacing"]))
        self.padding.setValue(int(defaults["padding"]))
        self.radius.setValue(int(defaults["corner_radius"]))
        backgrounds = ["white", "black", "transparent"]
        self.background.setCurrentIndex(
            backgrounds.index(defaults["background"]) if defaults["background"] in backgrounds else 0)
        if str(defaults["resolution"]) == "source":
            self.resolution.setCurrentIndex(0)
        else:
            match = {"2000": 1, "1500": 2, "1080": 3}.get(str(defaults["resolution"]), 0)
            self.resolution.setCurrentIndex(match)
        self.fit.setCurrentIndex(0 if defaults["fit"] == "fill" else 1)

        for widget in (self.layout_combo, self.resolution, self.fit, self.background):
            widget.currentIndexChanged.connect(self._queue_preview)
        for widget in (self.spacing, self.padding, self.radius):
            widget.valueChanged.connect(self._queue_preview)
        self.order_list.model().rowsMoved.connect(self._queue_preview)

        self.add_buttons(i18n.tr("dlg.collage.title"))
        QTimer.singleShot(80, self._refresh_preview)

    def _make_thumbs(self) -> None:
        for index, path in enumerate(self._paths):
            try:
                image = tools.load_image(path).convert("RGBA")
                image.thumbnail((480, 480))
                thumb = self._thumb_dir / f"thumb_{index:03d}.png"
                image.save(thumb, "PNG")
                self._thumbs[path] = thumb
            except Exception:
                self._thumbs[path] = path

    def _cleanup_thumbs(self) -> None:
        directory = getattr(self, "_thumb_dir", None)
        if directory is None:
            return
        self._thumb_dir = None
        shutil.rmtree(directory, ignore_errors=True)

    def _ordered_paths(self) -> list[Path]:
        ordered = []
        pool = list(self._paths)
        for index in range(self.order_list.count()):
            data = self.order_list.item(index).data(Qt.ItemDataRole.UserRole)
            if data is None:
                continue
            path = Path(data)
            if path in pool:
                ordered.append(path)
                pool.remove(path)
        ordered.extend(pool)
        return ordered

    def _thumb_paths(self) -> list[Path]:
        return [self._thumbs.get(path, path) for path in self._ordered_paths()]

    def _move(self, delta: int) -> None:
        row = self.order_list.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self.order_list.count():
            return
        item = self.order_list.takeItem(row)
        self.order_list.insertItem(new_row, item)
        self.order_list.setCurrentRow(new_row)

    def _options(self) -> dict:
        resolution = "source"
        if self.resolution.currentIndex() > 0:
            resolution = int(["", "2000", "1500", "1080"][self.resolution.currentIndex()])
        return {
            "layout": ["grid", "horizontal", "vertical", "featured"][self.layout_combo.currentIndex()],
            "spacing": self.spacing.value(),
            "padding": self.padding.value(),
            "corner_radius": self.radius.value(),
            "background": ["white", "black", "transparent"][self.background.currentIndex()],
            "resolution": resolution,
            "fit": "fill" if self.fit.currentIndex() == 0 else "contain",
        }

    def _queue_preview(self) -> None:
        self._preview_timer.start()

    def _refresh_preview(self) -> None:
        options = self._options()
        if options["resolution"] != "source":
            options["resolution"] = min(int(options["resolution"]), 480)
        try:
            out = tools.make_collage(
                self._thumb_paths(), options,
                tools.Ctx(progress=lambda v: None, status=lambda s: None),
                set(),
            )
            pixmap = QPixmap(str(out))
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(
                    self.preview.size() - QSize(12, 12),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
        except Exception:
            self.preview.setText(i18n.tr("msg.preview_unavailable"))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cleanup_thumbs()
        super().closeEvent(event)

    def __del__(self) -> None:
        try:
            self._cleanup_thumbs()
        except Exception:
            pass

    def save_defaults(self) -> None:
        options = self._options()
        settings.update({
            "collageLayout": options["layout"],
            "collageSpacing": options["spacing"],
            "collagePadding": options["padding"],
            "collageCornerRadius": options["corner_radius"],
            "collageBackground": options["background"],
            "collageResolution": options["resolution"],
            "collageFit": options["fit"],
        })
        settings.save()

    def _accept_clicked(self) -> None:
        self.save_defaults()
        options = self._options()
        self.remember_options(options)
        ordered = self._ordered_paths()
        self.job_window = progress.run_job(i18n.tr("action.building_collage"), lambda ctx: [
            tools.make_collage(ordered, options, ctx, set())
        ])
        self.accept()


# ---------------------------------------------------------------------------
# Crop image
# ---------------------------------------------------------------------------

class CropImageDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.crop.title"), parent)
        self._path = Path(path)
        self.canvas = CropCanvas(self._path)
        self.canvas.setMinimumSize(360, 240)
        self.canvas.resize(520, 350)
        self.resize(560, 470)
        self._body.addWidget(self.canvas)

        row = QHBoxLayout()
        self.aspect = QComboBox()
        self.aspect.addItems([i18n.tr("opt.free"), "1:1", "3:2", "4:3", "16:9", "9:16"])
        row.addWidget(section_label(i18n.tr("lbl.aspect")))
        row.addWidget(self.aspect)
        row.addSpacing(12)
        self.w_spin = NumericSpinBox()
        self.w_spin.setRange(1, self.canvas.image_size[0])
        self.w_spin.setValue(self.canvas.image_size[0])
        self.h_spin = NumericSpinBox()
        self.h_spin.setRange(1, self.canvas.image_size[1])
        self.h_spin.setValue(self.canvas.image_size[1])
        row.addWidget(QLabel(i18n.tr("lbl.w")))
        row.addWidget(self.w_spin)
        row.addWidget(QLabel(i18n.tr("lbl.h")))
        row.addWidget(self.h_spin)
        row.addStretch(1)
        reset = chip_button(i18n.tr("btn.select_all"))
        reset.clicked.connect(self._select_all)
        row.addWidget(reset)
        self._body.addLayout(row)

        self.canvas.changed = self._rect_changed
        self.w_spin.valueChanged.connect(self._size_changed)
        self.h_spin.valueChanged.connect(self._size_changed)
        self.aspect.currentIndexChanged.connect(self._aspect_changed)
        self.add_buttons(i18n.tr("dlg.crop.title"))

    def _select_all(self) -> None:
        self.aspect.setCurrentIndex(0)
        self.canvas.rect = [0.0, 0.0, float(self.canvas.image_size[0]),
                            float(self.canvas.image_size[1])]
        self.w_spin.setValue(self.canvas.image_size[0])
        self.h_spin.setValue(self.canvas.image_size[1])
        self.canvas.update()

    def _rect_changed(self, rect) -> None:
        self.w_spin.blockSignals(True)
        self.h_spin.blockSignals(True)
        self.w_spin.setValue(max(1, int(rect[2])))
        self.h_spin.setValue(max(1, int(rect[3])))
        self.w_spin.blockSignals(False)
        self.h_spin.blockSignals(False)

    def _size_changed(self) -> None:
        x, y, _, _ = self.canvas.rect
        w = self.w_spin.value()
        h = self.h_spin.value()
        ratio = self.canvas.aspect_ratio
        if ratio:
            if self.sender() is self.h_spin:
                w = h * ratio
            else:
                h = w / ratio
            factor = min(1.0, (self.canvas.image_size[0] - x) / w,
                         (self.canvas.image_size[1] - y) / h)
            w, h = w * factor, h * factor
        x, y, w, h = self.canvas.clamp_box(x, y, float(w), float(h))
        self.canvas.rect = [x, y, w, h]
        self._rect_changed(self.canvas.rect)
        self.canvas.update()

    def _aspect_changed(self) -> None:
        ratios = {0: None, 1: 1.0, 2: 1.5, 3: 4 / 3, 4: 16 / 9, 5: 9 / 16}
        ratio = ratios[self.aspect.currentIndex()]
        self.canvas.aspect_ratio = ratio
        if ratio is None:
            return
        img_w, img_h = self.canvas.image_size
        cx, cy = img_w / 2, img_h / 2
        w = min(img_w, img_h * ratio)
        h = w / ratio
        if h > img_h:
            h = img_h
            w = h * ratio
        self.canvas.rect = [cx - w / 2, cy - h / 2, w, h]
        self._rect_changed(self.canvas.rect)
        self.canvas.update()

    def _accept_clicked(self) -> None:
        x, y, w, h = self.canvas.rect
        box = (int(round(x)), int(round(y)),
               int(round(x + w)), int(round(y + h)))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            QMessageBox.warning(
                self, i18n.tr("dlg.crop.title"),
                i18n.tr("msg.crop.need_area"))
            return
        self.job_window = progress.run_job(
            i18n.tr("action.cropping", name=self._path.name),
            lambda ctx: [tools.crop_image(self._path, box, ctx, set())],
        )
        self.accept()


# ---------------------------------------------------------------------------
# Redact photo
# ---------------------------------------------------------------------------

class RedactPhotoDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.redact.title"), parent)
        self._path = Path(path)
        self.canvas = RedactCanvas(self._path)
        self.canvas.setMinimumSize(360, 240)
        self.canvas.resize(520, 350)
        self.resize(560, 470)
        self._body.addWidget(self.canvas)

        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems([i18n.tr("opt.solid"), i18n.tr("opt.blur"),
                            i18n.tr("opt.pixelate")])
        row.addWidget(section_label(i18n.tr("lbl.effect")))
        row.addWidget(self.mode)
        self.color_button = QPushButton(i18n.tr("btn.color"))
        self.color_button.clicked.connect(self._pick_color)
        self._color = QColor("#000000")
        self._sync_color()
        row.addWidget(self.color_button)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        row.addStretch(1)
        detect = chip_button(i18n.tr("btn.detect_faces"))
        detect.clicked.connect(self._detect_faces)
        row.addWidget(detect)
        remove = chip_button(i18n.tr("btn.remove_selected"))
        remove.clicked.connect(self._remove_selected)
        row.addWidget(remove)
        self._body.addLayout(row)

        hint = QLabel(i18n.tr("dlg.redact.hint"))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        self._body.addWidget(hint)
        self.add_buttons(i18n.tr("btn.save_redacted"))

    def _sync_color(self) -> None:
        self.color_button.setStyleSheet(
            f"border-left: 16px solid {self._color.name()}; padding-left: 8px;")

    def _mode_changed(self) -> None:
        index = self.mode.currentIndex()
        self.color_button.setEnabled(index == 0)
        self.canvas.mode = ["solid", "blur", "pixelate"][index]
        self.canvas.update()

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self, i18n.tr("dlg.redact.color_title"))
        if chosen.isValid():
            self._color = chosen
            self._sync_color()
            for index in range(len(self.canvas.boxes)):
                self.canvas.boxes[index]["color"] = self._color.name()
            self.canvas.update()

    def _detect_faces(self) -> None:
        try:
            faces = tools.detect_faces(self._path)
        except Exception as error:
            QMessageBox.warning(self, i18n.tr("btn.detect_faces"), str(error))
            return
        if not faces:
            QMessageBox.information(
            self, i18n.tr("btn.detect_faces"),
            i18n.tr("dlg.redact.no_faces"))
            return
        for x, y, w, h in faces:
            self.canvas.boxes.append({
                "x": float(x), "y": float(y), "w": float(w), "h": float(h),
                "mode": "blur", "color": self._color.name(),
            })
        self.canvas.update()

    def _remove_selected(self) -> None:
        if self.canvas.selected >= 0:
            self.canvas.boxes.pop(self.canvas.selected)
            self.canvas.selected = -1
            self.canvas.update()

    def _accept_clicked(self) -> None:
        if not self.canvas.boxes:
            QMessageBox.warning(
            self, i18n.tr("dlg.redact.title"),
            i18n.tr("dlg.redact.need_box"))
            return
        mode = ["solid", "blur", "pixelate"][self.mode.currentIndex()]
        boxes = [
            (int(b["x"]), int(b["y"]), int(b["w"]), int(b["h"]),
             mode, self._color.name())
            for b in self.canvas.boxes
        ]
        self.job_window = progress.run_job(
            i18n.tr("action.redacting", name=self._path.name),
            lambda ctx: [tools.redact_photo(self._path, boxes, ctx, set())],
        )
        self.accept()


# ---------------------------------------------------------------------------
# Add background
# ---------------------------------------------------------------------------

class BackgroundDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.background.title"), parent)
        self._paths = [Path(p) for p in path] if isinstance(path, (list, tuple)) else [Path(path)]
        if not self._paths:
            raise tools.EngineError(i18n.tr("err.no_images"))
        self._path = self._paths[0]
        if len(self._paths) > 1:
            heading = QLabel(i18n.tr("defaults.batch", count=len(self._paths)))
            heading.setWordWrap(True)
            heading.setProperty("dim", True)
            self._body.addWidget(heading)
        self._thumb_dir = Path(tempfile.mkdtemp(prefix="tangerine_background_"))
        self.finished.connect(self._cleanup_thumbs)
        image = tools.load_image(self._path)
        self._img_w, self._img_h = image.width, image.height
        image.thumbnail((480, 480))
        self._thumb_path = self._thumb_dir / "thumb.png"
        image.convert("RGBA").save(self._thumb_path, "PNG")
        self._scale = (image.width / self._img_w) if self._img_w else 1.0

        self._color = QColor("#FFFFFF")
        self._from_color = QColor("#F87800")
        self._to_color = QColor("#3A2416")
        self._image_path: Path | None = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(280)
        self._preview_timer.timeout.connect(self._refresh_preview)

        top = QHBoxLayout()
        top.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(9)
        align_form(form)

        self.fill_type = QComboBox()
        self.fill_type.addItems([i18n.tr("opt.bg_color"),
                                 i18n.tr("opt.bg_gradient"),
                                 i18n.tr("opt.bg_image")])
        form.addRow(i18n.tr("lbl.background"), self.fill_type)

        rows: list[tuple[QLabel, QWidget]] = []

        def add_row(label_text: str, field: QWidget) -> None:
            label = QLabel(label_text)
            form.addRow(label, field)
            rows.append((label, field))

        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._pick_color)
        self._sync_button(self.color_button, self._color)
        add_row(i18n.tr("btn.color"), self.color_button)

        gradient = QWidget()
        gradient_row = QHBoxLayout(gradient)
        gradient_row.setContentsMargins(0, 0, 0, 0)
        self.from_button = QPushButton()
        self.from_button.clicked.connect(self._pick_from_color)
        self.to_button = QPushButton()
        self.to_button.clicked.connect(self._pick_to_color)
        self._sync_button(self.from_button, self._from_color)
        self._sync_button(self.to_button, self._to_color)
        gradient_row.addWidget(self.from_button, 1)
        gradient_row.addWidget(self.to_button, 1)
        self.angle = NumericSpinBox()
        self.angle.setRange(0, 360)
        self.angle.setSuffix("°")
        gradient_row.addWidget(self.angle)
        add_row(i18n.tr("lbl.gradient_from"), gradient)

        image_picker = QWidget()
        image_row = QHBoxLayout(image_picker)
        image_row.setContentsMargins(0, 0, 0, 0)
        choose = chip_button(i18n.tr("btn.choose_image"))
        choose.clicked.connect(self._pick_image)
        self.image_label = QLabel("—")
        self.image_label.setProperty("dim", True)
        image_row.addWidget(choose)
        image_row.addWidget(self.image_label, 1)
        add_row(i18n.tr("opt.bg_image"), image_picker)

        self.aspect = QComboBox()
        self.aspect.addItems([i18n.tr("opt.aspect_original"), "1:1", "4:3",
                              "3:2", "16:9", "9:16"])
        form.addRow(i18n.tr("lbl.aspect"), self.aspect)

        self.margin = NumericSpinBox()
        self.margin.setRange(0, 512)
        self.margin.setSuffix(" px")
        form.addRow(i18n.tr("lbl.margin"), self.margin)

        self.radius = NumericSpinBox()
        self.radius.setRange(0, 256)
        self.radius.setSuffix(" px")
        form.addRow(i18n.tr("lbl.rounded_corners"), self.radius)
        top.addLayout(form)

        self.preview = QLabel()
        self.preview.setFixedSize(330, 250)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setProperty("card", True)
        self.preview.setStyleSheet(
            "background: rgba(127,127,127,0.12); border-radius: 10px;")
        top.addWidget(self.preview)
        self._body.addLayout(top)

        note = QLabel(i18n.tr("dlg.background.note"))
        note.setProperty("dim", True)
        note.setWordWrap(True)
        self._body.addWidget(note)

        self._fill_rows = rows
        self.fill_type.currentIndexChanged.connect(self._fill_changed)
        for widget in (self.aspect,):
            widget.currentIndexChanged.connect(self._queue_preview)
        for widget in (self.margin, self.radius, self.angle):
            widget.valueChanged.connect(self._queue_preview)
        options = self.configure_defaults("img.background")
        if options:
            self._restore_options(options)
        self.add_buttons(i18n.tr("btn.save_background"))
        self._fill_changed()
        QTimer.singleShot(80, self._refresh_preview)

    def _cleanup_thumbs(self) -> None:
        directory = getattr(self, "_thumb_dir", None)
        if directory is None:
            return
        self._thumb_dir = None
        shutil.rmtree(directory, ignore_errors=True)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cleanup_thumbs()
        super().closeEvent(event)

    def __del__(self) -> None:
        try:
            self._cleanup_thumbs()
        except Exception:
            pass

    def _sync_button(self, button: QPushButton, color: QColor) -> None:
        swatch = QPixmap(16, 16)
        swatch.fill(color)
        button.setIcon(QIcon(swatch))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumWidth(128)
        button.setText(color.name())

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self, i18n.tr("dlg.background.color_title"))
        if chosen.isValid():
            self._color = chosen
            self._sync_button(self.color_button, self._color)
            self._queue_preview()

    def _pick_from_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._from_color, self, i18n.tr("dlg.background.color_title"))
        if chosen.isValid():
            self._from_color = chosen
            self._sync_button(self.from_button, self._from_color)
            self._queue_preview()

    def _pick_to_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._to_color, self, i18n.tr("dlg.background.color_title"))
        if chosen.isValid():
            self._to_color = chosen
            self._sync_button(self.to_button, self._to_color)
            self._queue_preview()

    def _pick_image(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, i18n.tr("dlg.background.image_title"), "",
            i18n.tr("fmt.images_filter"))
        if chosen:
            self._image_path = Path(chosen)
            self.image_label.setText(self._image_path.name)
            self._queue_preview()

    def _fill_changed(self) -> None:
        index = self.fill_type.currentIndex()
        for row_index, (label, widget) in enumerate(self._fill_rows):
            visible = row_index == index
            label.setVisible(visible)
            widget.setVisible(visible)
        self._queue_preview()

    def _queue_preview(self) -> None:
        self._preview_timer.start()

    def _options(self, scale: float = 1.0) -> dict:
        kind = ["color", "gradient", "image"][self.fill_type.currentIndex()]
        if kind == "gradient":
            fill = {"type": "gradient", "from": self._from_color.name(),
                    "to": self._to_color.name(), "angle": self.angle.value()}
        elif kind == "image":
            fill = {"type": "image",
                    "path": str(self._image_path) if self._image_path else ""}
        else:
            fill = {"type": "color", "color": self._color.name()}
        return {
            "fill": fill,
            "aspect": ["original", "1:1", "4:3", "3:2", "16:9", "9:16"][
                self.aspect.currentIndex()],
            "margin": max(0, int(round(self.margin.value() * scale))),
            "radius": max(0, int(round(self.radius.value() * scale))),
            "fit": "contain",
        }

    def _restore_options(self, options: dict) -> None:
        fill = options["fill"]
        self.fill_type.setCurrentIndex(["color", "gradient", "image"].index(fill["type"]))
        if fill["type"] == "color":
            self._color = QColor(fill["color"])
            self._sync_button(self.color_button, self._color)
        elif fill["type"] == "gradient":
            self._from_color, self._to_color = QColor(fill["from"]), QColor(fill["to"])
            self._sync_button(self.from_button, self._from_color)
            self._sync_button(self.to_button, self._to_color)
            self.angle.setValue(fill["angle"])
        else:
            self._image_path = Path(fill["path"])
            self.image_label.setText(self._image_path.name)
        self.aspect.setCurrentIndex(["original", "1:1", "4:3", "3:2", "16:9", "9:16"].index(options["aspect"]))
        self.margin.setValue(options["margin"])
        self.radius.setValue(options["radius"])

    def _refresh_preview(self) -> None:
        options = self._options(self._scale)
        if options["fill"]["type"] == "image" and not options["fill"]["path"]:
            self.preview.setText(i18n.tr("msg.preview_unavailable"))
            return
        try:
            out = tools.add_background(
                self._thumb_path, options,
                tools.Ctx(progress=lambda v: None, status=lambda s: None), set())
            pixmap = QPixmap(str(out))
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(
                    self.preview.size() - QSize(12, 12),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
        except Exception:
            self.preview.setText(i18n.tr("msg.preview_unavailable"))

    def _accept_clicked(self) -> None:
        if self.fill_type.currentIndex() == 2 and (self._image_path is None or not self._image_path.is_file()):
            QMessageBox.warning(
                self, i18n.tr("dlg.background.title"),
                i18n.tr("msg.background.no_image"))
            return
        options = self._options()
        self.remember_options(options)
        self.job_window = run_batch(self._paths, lambda path, ctx, reserved:
            tools.add_background(path, options, ctx, reserved))
        self.accept()


# ---------------------------------------------------------------------------
# Edit photo
# ---------------------------------------------------------------------------

class EditPhotoDialog(ToolDialog):
    PRESETS = ["none", "mono", "sepia", "noir", "vivid", "cool", "warm"]

    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.edit.title"), parent)
        self._path = Path(path)
        self._image = tools.load_image(self._path)
        self._image.thumbnail((440, 250))
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(140)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self.preview = QLabel()
        self.preview.setMinimumSize(360, 220)
        self.preview.resize(470, 270)
        self.resize(520, 560)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "background: rgba(127,127,127,0.12); border-radius: 10px;")
        self._body.addWidget(self.preview)

        form = QFormLayout()
        form.setSpacing(10)
        align_form(form)

        def slider_row(label: str, min_v: int, max_v: int, value: int):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setValue(value)
            spin = NumericSpinBox()
            spin.setRange(min_v, max_v)
            spin.setValue(value)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(self._queue_preview)
            row = QHBoxLayout()
            row.addWidget(slider, 1)
            row.addWidget(spin)
            form.addRow(label, row)
            return slider

        self.preset = QComboBox()
        self.preset.addItems([i18n.tr("opt.preset_none"), i18n.tr("opt.preset_mono"),
                              i18n.tr("opt.preset_sepia"), i18n.tr("opt.preset_noir"),
                              i18n.tr("opt.preset_vivid"), i18n.tr("opt.preset_cool"),
                              i18n.tr("opt.preset_warm")])
        self.preset.currentIndexChanged.connect(self._queue_preview)
        form.addRow(i18n.tr("lbl.preset"), self.preset)

        self.exposure = slider_row(i18n.tr("lbl.exposure"), -100, 100, 0)
        self.contrast = slider_row(i18n.tr("lbl.contrast"), -100, 100, 0)
        self.saturation = slider_row(i18n.tr("lbl.saturation"), -100, 100, 0)
        self.temperature = slider_row(i18n.tr("lbl.temperature"), -100, 100, 0)
        self.vibrance = slider_row(i18n.tr("lbl.vibrance"), -100, 100, 0)
        self.sharpness = slider_row(i18n.tr("lbl.sharpness"), 0, 100, 0)
        self.vignette = slider_row(i18n.tr("lbl.vignette"), 0, 100, 0)
        self.grain = slider_row(i18n.tr("lbl.grain"), 0, 100, 0)
        self._body.addLayout(form)

        bottom = QHBoxLayout()
        reset = chip_button(i18n.tr("btn.reset"))
        reset.clicked.connect(self._reset)
        bottom.addWidget(reset)
        bottom.addStretch(1)
        self._body.addLayout(bottom)

        self.add_buttons(i18n.tr("btn.save_copy"))
        QTimer.singleShot(60, self._refresh_preview)

    def _options(self) -> dict:
        return {
            "preset": self.PRESETS[self.preset.currentIndex()],
            "exposure": self.exposure.value(),
            "contrast": self.contrast.value(),
            "saturation": self.saturation.value(),
            "temperature": self.temperature.value(),
            "vibrance": self.vibrance.value(),
            "sharpness": self.sharpness.value(),
            "vignette": self.vignette.value(),
            "grain": self.grain.value(),
        }

    def _reset(self) -> None:
        for slider in (self.exposure, self.contrast, self.saturation,
                       self.temperature, self.vibrance, self.sharpness,
                       self.vignette, self.grain):
            slider.setValue(0)
        self.preset.setCurrentIndex(0)
        self._queue_preview()

    def _queue_preview(self) -> None:
        self._preview_timer.start()

    def _refresh_preview(self) -> None:
        preview = self._image.copy()
        preview.thumbnail((520, 290))
        edited = tools._apply_edits(preview, self._options())
        self.preview.setPixmap(QPixmap.fromImage(pil_to_qimage(edited)))

    def _accept_clicked(self) -> None:
        path = self._path
        options = self._options()
        self.job_window = progress.run_job(
            i18n.tr("action.editing", name=path.name),
            lambda ctx: [tools.edit_image(path, options, ctx, set())],
        )
        self.accept()


# ---------------------------------------------------------------------------
# Annotate photo
# ---------------------------------------------------------------------------

def render_annotations(path: Path, ops: list[dict]) -> Path:
    """Render annotation ops onto a transient full-resolution copy of *path*."""
    full = tools.load_image(path)
    if full.getexif().get(274, 1) != 1:
        full = ImageOps.exif_transpose(full)
    qimage = pil_to_qimage(full)
    del full
    painter = QPainter(qimage)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for op in ops:
        _draw_op(painter, op, 1.0, QPointF(0.0, 0.0))
    painter.end()
    out = tools._unique(path.parent, f"{path.stem} Annotated", ".png", set())
    if not qimage.save(str(out), "PNG"):
        raise tools.EngineError(i18n.tr("err.annotate_save"))
    return out


class AnnotateDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.annotate.title"), parent)
        self._path = Path(path)
        self.canvas = AnnotateCanvas(self._path)
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.canvas.setMinimumSize(360, 240)
        self.canvas.resize(520, 350)
        self.resize(560, 480)
        self._body.addWidget(self.canvas)

        row = QHBoxLayout()
        self.tool_buttons = {}
        for key, label in (
                ("arrow", i18n.tr("opt.arrow")), ("pen", i18n.tr("opt.pen")),
                ("rect", i18n.tr("opt.rect")), ("ellipse", i18n.tr("opt.ellipse")),
                ("text", i18n.tr("opt.text")),
                ("highlight", i18n.tr("opt.highlight")),
                ("callout", i18n.tr("opt.callout"))
        ):
            button = chip_button(label)
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, k=key: self._select_tool(k))
            self.tool_buttons[key] = button
            row.addWidget(button)
        self.tool_buttons["arrow"].setChecked(True)
        row.addStretch(1)
        self._body.addLayout(row)
        style_row = QHBoxLayout()
        color_button = chip_button(i18n.tr("btn.color"))
        color_button.clicked.connect(self._pick_color)
        style_row.addWidget(color_button)
        style_row.addWidget(QLabel(i18n.tr("lbl.size")))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 12)
        self.width_slider.setValue(3)
        self.width_slider.setFixedWidth(90)
        self.width_slider.valueChanged.connect(
            lambda v: setattr(self.canvas, "stroke_width", v))
        style_row.addWidget(self.width_slider)
        style_row.addStretch(1)
        self._body.addLayout(style_row)

        bottom = QHBoxLayout()
        undo = chip_button(i18n.tr("btn.undo"))
        undo.clicked.connect(self.canvas.undo)
        reset = chip_button(i18n.tr("btn.reset"))
        reset.clicked.connect(self.canvas.reset_ops)
        bottom.addWidget(undo)
        bottom.addWidget(reset)
        bottom.addStretch(1)
        self._body.addLayout(bottom)
        self._color_button = color_button
        self._sync_color()
        self.add_buttons(i18n.tr("btn.save_annotated"))

    def _select_tool(self, key: str) -> None:
        self.canvas.tool = key
        self.canvas.setCursor(Qt.CursorShape.IBeamCursor if key == "text" else Qt.CursorShape.CrossCursor)
        for name, button in self.tool_buttons.items():
            button.setChecked(name == key)

    def _sync_color(self) -> None:
        swatch = QPixmap(16, 16)
        swatch.fill(QColor(self.canvas.color))
        self._color_button.setIcon(QIcon(swatch))

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(
            QColor(self.canvas.color), self,
            i18n.tr("dlg.annotate.color_title"))
        if chosen.isValid():
            self.canvas.color = chosen.name()
            self._sync_color()

    def _accept_clicked(self) -> None:
        if not self.canvas.ops:
            QMessageBox.warning(
            self, i18n.tr("dlg.annotate.title"),
            i18n.tr("dlg.annotate.need_op"))
            return
        path = self._path
        ops = list(self.canvas.ops)

        def work(ctx):
            ctx.status(i18n.tr("action.rendering_annotations", name=path.name))
            out = render_annotations(path, ops)
            ctx.progress(1.0)
            return [out]

        self.job_window = progress.run_job(i18n.tr("action.annotating", name=path.name), work)
        self.accept()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class MetadataDialog(ToolDialog):
    EDITABLE = {name: tag for tag, name in tools.EXIF_TAGS.items()}
    LOCATION_KEYS = (("meta.latitude", "latitude"),
                     ("meta.longitude", "longitude"),
                     ("meta.altitude", "altitude"))

    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.metadata.title"), parent)
        self._path = Path(path)
        self._rows = tools.read_metadata(self._path)

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

        labels = [i18n.tr(key) for key, _ in self.LOCATION_KEYS]
        rows = [row for row in self._rows if row[0] not in labels]
        if self._is_image():
            location = tools.read_location(self._path)
            rows.append((labels[0], f"{location['latitude']:.6f}" if location else ""))
            rows.append((labels[1], f"{location['longitude']:.6f}" if location else ""))
            altitude = location.get("altitude") if location else None
            rows.append((labels[2], "" if altitude is None else f"{altitude:.2f}"))

        self.table = QTableWidget(len(rows), 2)
        self.table.setHorizontalHeaderLabels(
            [i18n.tr("lbl.field"), i18n.tr("lbl.value")])
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumSize(460, 290)
        self.resize(500, 430)
        for row, (name, value) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(value))
        self.table.resizeColumnToContents(0)
        self._body.addWidget(self.table)

        self._status = QLabel()
        self._status.setProperty("dim", True)
        self._body.addWidget(self._status)

        box = QDialogButtonBox()
        save = box.addButton(
            i18n.tr("btn.save_copy"), QDialogButtonBox.ButtonRole.AcceptRole)
        save.setProperty("accent", True)
        if self._is_image():
            remove_location = box.addButton(
                i18n.tr("btn.remove_location"),
                QDialogButtonBox.ButtonRole.DestructiveRole)
            remove_location.clicked.connect(self._remove_location)
        if self._can_strip():
            remove_all = box.addButton(
                i18n.tr("btn.remove_all"),
                QDialogButtonBox.ButtonRole.DestructiveRole)
            remove_all.clicked.connect(self._remove_all)
        close = box.addButton(
            i18n.tr("btn.close"), QDialogButtonBox.ButtonRole.RejectRole)
        save.clicked.connect(self._save_copy)
        close.clicked.connect(self.reject)
        self._body.addWidget(box)
        self._refresh_status()

    def _can_strip(self) -> bool:
        return self._path.suffix.lower() not in (".pdf", ".txt")

    def _refresh_status(self) -> None:
        if self._is_image():
            self._status.setText(i18n.tr(
                "dlg.metadata.status_image",
                name=self._path.stem, ext=self._path.suffix))
        elif self._can_strip():
            self._status.setText(i18n.tr("dlg.metadata.status_ro_strip"))
        else:
            self._status.setText(i18n.tr("dlg.metadata.status_ro"))

    def _fields(self) -> dict[int, str]:
        fields: dict[int, str] = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            if name_item is None or value_item is None:
                continue
            tag = self.EDITABLE.get(name_item.text())
            if tag is not None:
                fields[tag] = value_item.text()
        return fields

    def _location(self) -> dict | None:
        mapping = {i18n.tr(i18n_key): key for i18n_key, key in self.LOCATION_KEYS}
        values: dict[str, float] = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            if name_item is None or value_item is None:
                continue
            key = mapping.get(name_item.text())
            if key is None:
                continue
            text = value_item.text().strip()
            if text:
                try:
                    values[key] = float(text.replace(",", "."))
                except ValueError:
                    raise ValueError(key)
        return values or None

    def _is_image(self) -> bool:
        return self._path.suffix.lower() in tools.IMAGE_META_EXTS

    def _save_copy(self) -> None:
        if not self._is_image():
            message = i18n.tr("dlg.metadata.save_image_only")
            if self._can_strip():
                message += i18n.tr("dlg.metadata.save_image_only_strip")
            QMessageBox.information(self, i18n.tr("dlg.metadata.title"), message)
            return
        try:
            location = self._location()
        except ValueError:
            location = None
            QMessageBox.warning(
                self, i18n.tr("dlg.metadata.title"),
                i18n.tr("dlg.metadata.location_invalid"))
            return
        if location and ("latitude" not in location or "longitude" not in location):
            QMessageBox.warning(
                self, i18n.tr("dlg.metadata.title"),
                i18n.tr("dlg.metadata.location_invalid"))
            return
        fields = self._fields()
        path = self._path
        self.job_window = progress.run_job(
            i18n.tr("action.writing_metadata", name=path.name),
            lambda ctx: [tools.write_metadata_image(
                path, fields, False, ctx, set(), location)],
        )
        self.accept()

    def _remove_location(self) -> None:
        path = self._path
        self.job_window = progress.run_job(
            i18n.tr("action.removing_location", name=path.name),
            lambda ctx: [tools.remove_location(path, ctx, set())],
        )
        self.accept()

    def _remove_all(self) -> None:
        path = self._path
        self.job_window = progress.run_job(
            i18n.tr("action.removing_metadata", name=path.name),
            lambda ctx: [tools.strip_metadata(path, ctx, set())],
        )
        self.accept()
