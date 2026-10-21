"""Video editors: trim, crop, speed, snapshots, split, redact and join."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
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

from .. import i18n, progress, tools
from ..media import CREATE_NO_WINDOW, ffmpeg_path
from .ui.controls import NumericSpinBox, NumericDoubleSpinBox
from .base import ToolDialog, align_form, chip_button, section_label
from .ui.canvas import CropCanvas
from .ui.video import BoxDrawDialog, VideoPane


# ---------------------------------------------------------------------------
# Video: preview pane and editors
# ---------------------------------------------------------------------------

def _grab_frame(path: Path, seconds: float = 0.0) -> Path | None:
    exe = ffmpeg_path()
    if not exe:
        return None
    tmp = Path(tempfile.gettempdir()) / f"tangerine_frame_{os.getpid()}_{int(seconds * 1000)}.png"
    tmp.unlink(missing_ok=True)
    args = [exe, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, seconds):.3f}",
            "-i", str(path), "-frames:v", "1", "-y", str(tmp)]
    try:
        subprocess.run(args, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=60)
    except Exception:
        return None
    return tmp if tmp.exists() else None


def _frame_pixmap(path: Path, seconds: float, width: int = 160) -> QPixmap | None:
    exe = ffmpeg_path()
    if not exe:
        return None
    args = [exe, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, seconds):.3f}",
            "-i", str(path), "-frames:v", "1", "-vf", f"scale={width}:-2",
            "-vcodec", "png", "-f", "image2pipe", "pipe:1"]
    try:
        proc = subprocess.run(args, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=60)
    except Exception:
        return None
    pixmap = QPixmap()
    if pixmap.loadFromData(proc.stdout, "PNG"):
        return pixmap
    return None


class TrimVideoDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.trim_video.title"), parent)
        self._path = Path(path)
        self._duration = tools.probe_duration_seconds(self._path) or 0.0
        self.pane = VideoPane(self._path, height=230)
        self.resize(520, 420)
        self._body.addWidget(self.pane)

        form = QFormLayout()
        form.setSpacing(10)
        align_form(form)
        self.start_spin = NumericDoubleSpinBox()
        self.start_spin.setRange(0.0, max(self._duration, 0.01))
        self.start_spin.setDecimals(3)
        self.start_spin.setSuffix(" s")
        self.end_spin = NumericDoubleSpinBox()
        self.end_spin.setRange(0.0, max(self._duration, 0.01))
        self.end_spin.setDecimals(3)
        self.end_spin.setValue(self._duration)
        self.end_spin.setSuffix(" s")
        form.addRow(i18n.tr("lbl.start"), self.start_spin)
        form.addRow(i18n.tr("lbl.end"), self.end_spin)
        self._body.addLayout(form)

        row = QHBoxLayout()
        set_in = chip_button(i18n.tr("btn.set_in"))
        set_in.clicked.connect(lambda: self.start_spin.setValue(
            self.pane._player.position() / 1000.0))
        set_out = chip_button(i18n.tr("btn.set_out"))
        set_out.clicked.connect(lambda: self.end_spin.setValue(
            self.pane._player.position() / 1000.0))
        play = chip_button(i18n.tr("btn.play_selection"))
        play.clicked.connect(self._play_selection)
        row.addWidget(set_in)
        row.addWidget(set_out)
        row.addWidget(play)
        row.addStretch(1)
        self._body.addLayout(row)

        self._limit_active = False
        self.pane._player.positionChanged.connect(self._enforce_limit)
        self.add_buttons(i18n.tr("btn.save_trimmed"))

    def _play_selection(self) -> None:
        self._limit_active = True
        self.pane.seek(self.start_spin.value())
        self.pane.play()

    def _enforce_limit(self, position: int) -> None:
        if self._limit_active and position / 1000.0 >= self.end_spin.value():
            self.pane._player.pause()
            self._limit_active = False

    def _accept_clicked(self) -> None:
        start, end = self.start_spin.value(), self.end_spin.value()
        if end - start < 0.05:
            QMessageBox.warning(
            self, i18n.tr("dlg.trim_video.title"),
            i18n.tr("msg.range_too_short"))
            return
        path = self._path
        progress.run_job(
            i18n.tr("action.trimming", name=path.name),
            lambda ctx: [tools.trim_video(path, start, end, ctx, set())],
        )
        self.accept()


class CropVideoDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.crop_video.title"), parent)
        self._path = Path(path)
        self._duration = tools.probe_duration_seconds(self._path) or 0.0
        self._frame = None
        self.canvas = None
        self.loading = QLabel(i18n.tr("lbl.loading_preview"))
        self.loading.setProperty("dim", True)
        self._body.addWidget(self.loading)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("lbl.frame_at")))
        self.time_spin = NumericDoubleSpinBox()
        self.time_spin.setRange(0.0, max(self._duration, 0.01))
        self.time_spin.setDecimals(2)
        self.time_spin.setValue(min(self._duration / 2.0, 3.0))
        self.time_spin.setSuffix(" s")
        row.addWidget(self.time_spin)
        refresh = chip_button(i18n.tr("btn.refresh_frame"))
        refresh.clicked.connect(self._refresh_frame)
        row.addWidget(refresh)
        row.addSpacing(12)
        self.aspect = QComboBox()
        self.aspect.addItems([i18n.tr("opt.free"), "1:1", "3:2", "4:3", "16:9", "9:16"])
        row.addWidget(section_label(i18n.tr("lbl.aspect")))
        row.addWidget(self.aspect)
        row.addStretch(1)
        self._body.addLayout(row)

        self.aspect.currentIndexChanged.connect(self._aspect_changed)
        select_all = chip_button(i18n.tr("btn.select_all"))
        select_all.clicked.connect(self._select_all)
        row.addWidget(select_all)
        self.add_buttons(i18n.tr("btn.crop_video"))
        QTimer.singleShot(50, self._load_frame)

    def _load_frame(self) -> None:
        frame = _grab_frame(self._path, min(self._duration / 2.0, 3.0))
        if frame is None:
            self.loading.setText(i18n.tr("dlg.crop_video.no_frame"))
            return
        self._frame = frame
        self.canvas = CropCanvas(frame)
        self.canvas.setMinimumSize(360, 220)
        self.canvas.resize(520, 320)
        self.resize(560, 460)
        self.canvas.changed = lambda rect: None
        self._body.insertWidget(self._body.indexOf(self.loading), self.canvas)
        self.loading.setVisible(False)

    def _select_all(self) -> None:
        if self.canvas is None:
            return
        self.canvas.rect = [0.0, 0.0, float(self.canvas.image_size[0]),
                            float(self.canvas.image_size[1])]
        self.canvas.update()

    def _refresh_frame(self) -> None:
        frame = _grab_frame(self._path, self.time_spin.value())
        if frame is None or self.canvas is None:
            return
        self.canvas.load(frame)
        self._select_all()

    def _aspect_changed(self) -> None:
        if self.canvas is None:
            return
        ratios = {0: None, 1: 1.0, 2: 1.5, 3: 4 / 3, 4: 16 / 9, 5: 9 / 16}
        ratio = ratios[self.aspect.currentIndex()]
        if ratio is None:
            return
        img_w, img_h = self.canvas.image_size
        w = min(img_w, img_h * ratio)
        h = w / ratio
        if h > img_h:
            h = img_h
            w = h * ratio
        self.canvas.rect = [(img_w - w) / 2, (img_h - h) / 2, w, h]
        self.canvas.update()

    def _accept_clicked(self) -> None:
        if self.canvas is None:
            QMessageBox.warning(
            self, i18n.tr("dlg.crop_video.title"),
            i18n.tr("msg.crop_video.not_ready"))
            return
        x, y, w, h = self.canvas.rect
        box = (int(round(x)), int(round(y)), int(round(w)), int(round(h)))
        if box[2] < 16 or box[3] < 16:
            QMessageBox.warning(
            self, i18n.tr("dlg.crop_video.title"),
            i18n.tr("msg.crop_video.larger"))
            return
        full = (box[0] <= 0 and box[1] <= 0
                and box[2] >= self.canvas.image_size[0]
                and box[3] >= self.canvas.image_size[1])
        path = self._path
        progress.run_job(
            i18n.tr("action.cropping", name=path.name),
            lambda ctx: [tools.crop_video(path, box, ctx, set())],
        )
        if full:
            QMessageBox.information(
                self, i18n.tr("dlg.crop_video.title"),
                i18n.tr("msg.crop_video.full_frame"))
        self.accept()


class SpeedDialog(ToolDialog):
    SNAPS = [25, 50, 75, 100, 125, 150, 200, 300, 400]

    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.speed.title"), parent)
        self._path = Path(path)
        self.pane = VideoPane(self._path, height=220)
        self.resize(520, 400)
        self._body.addWidget(self.pane)

        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(25, 400)
        self.slider.setValue(100)
        self.value_label = QLabel("1.00x")
        self.value_label.setFixedWidth(60)
        row.addWidget(self.slider, 1)
        row.addWidget(self.value_label)
        self._body.addLayout(row)
        self.slider.valueChanged.connect(self._value_changed)

        hint = QLabel(i18n.tr("dlg.speed.hint"))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        self._body.addWidget(hint)
        self.add_buttons(i18n.tr("btn.save_speed"))

    def _value_changed(self, value: int) -> None:
        for snap in self.SNAPS:
            if abs(value - snap) <= 3:
                if value != snap:
                    self.slider.blockSignals(True)
                    self.slider.setValue(snap)
                    self.slider.blockSignals(False)
                value = snap
                break
        factor = value / 100.0
        self.value_label.setText(f"{factor:.2f}x")
        try:
            self.pane._player.setPlaybackRate(factor)
        except Exception:
            pass

    def factor(self) -> float:
        return self.slider.value() / 100.0

    def _accept_clicked(self) -> None:
        factor = self.factor()
        if abs(factor - 1.0) < 0.001:
            QMessageBox.information(
            self, i18n.tr("dlg.speed.title"), i18n.tr("dlg.speed.same"))
            return
        path = self._path
        progress.run_job(
            i18n.tr("action.changing_speed", name=path.name),
            lambda ctx: [tools.change_speed(path, factor, ctx, set())],
        )
        self.accept()


class SnapshotsDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.snapshots.title"), parent)
        self._path = Path(path)
        self._duration = tools.probe_duration_seconds(self._path) or 0.0
        self.pane = VideoPane(self._path, height=210)
        self.resize(520, 390)
        self._body.addWidget(self.pane)

        row = QHBoxLayout()
        play = chip_button(i18n.tr("btn.play"))
        play.clicked.connect(self.pane.play)
        stop = chip_button(i18n.tr("btn.stop"))
        stop.clicked.connect(self.pane._player.stop)
        back = chip_button(i18n.tr("btn.frame_back"))
        back.clicked.connect(lambda: self._step(-1))
        forward = chip_button(i18n.tr("btn.frame_forward"))
        forward.clicked.connect(lambda: self._step(1))
        capture = QPushButton(i18n.tr("btn.add_frame"))
        capture.setProperty("accent", True)
        capture.clicked.connect(self._capture)
        for widget in (play, stop, back, forward, capture):
            row.addWidget(widget)
        row.addStretch(1)
        self._body.addLayout(row)

        self.strip = QListWidget()
        self.strip.setViewMode(QListWidget.ViewMode.IconMode)
        self.strip.setIconSize(QSize(128, 72))
        self.strip.setFixedHeight(112)
        self.strip.setMovement(QListWidget.Movement.Static)
        self._body.addWidget(self.strip)
        remove = chip_button(i18n.tr("btn.remove_selected"))
        remove.clicked.connect(self._remove_selected)
        row2 = QHBoxLayout()
        row2.addWidget(remove)
        row2.addStretch(1)
        self._body.addLayout(row2)
        self._times: list[float] = []
        self._fps = 30.0
        self.loading = QLabel(i18n.tr("lbl.loading"))
        self.loading.setProperty("dim", True)
        self._body.addWidget(self.loading)
        self.add_buttons(i18n.tr("btn.export_snapshots"))
        QTimer.singleShot(50, self._load_media_info)

    def _load_media_info(self) -> None:
        from ..media import probe as media_probe

        info = media_probe(self._path)
        video = info.video()
        if video and video.fps:
            self._fps = video.fps
        self.loading.setVisible(False)

    def _step(self, direction: int) -> None:
        position = self.pane._player.position() + direction * (1000.0 / self._fps)
        self.pane._player.setPosition(int(max(0.0, min(position, self._duration * 1000))))

    def _capture(self) -> None:
        seconds = self.pane._player.position() / 1000.0
        pixmap = _frame_pixmap(self._path, seconds)
        if pixmap is None:
            QMessageBox.warning(
            self, i18n.tr("dlg.snapshots.title"),
            i18n.tr("dlg.snapshots.no_frame"))
            return
        item = QListWidgetItem(QPixmap(pixmap))
        item.setToolTip(f"{seconds:.3f} s")
        self.strip.addItem(item)
        self._times.append(seconds)

    def _remove_selected(self) -> None:
        row = self.strip.currentRow()
        if row >= 0:
            self.strip.takeItem(row)
            self._times.pop(row)

    def _accept_clicked(self) -> None:
        if not self._times:
            QMessageBox.warning(
            self, i18n.tr("dlg.snapshots.title"),
            i18n.tr("dlg.snapshots.need_frame"))
            return
        path = self._path
        timestamps = list(self._times)
        progress.run_job(
            i18n.tr("action.exporting_snapshots", name=path.name),
            lambda ctx: tools.take_snapshots(path, timestamps, ctx, set()),
        )
        self.accept()


class SplitVideoDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.split_video.title"), parent)
        self._path = Path(path)
        self._duration = tools.probe_duration_seconds(self._path) or 0.0

        heading = QLabel(self._path.name)
        heading.setProperty("dim", True)
        self._body.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(10)
        align_form(form)
        self.parts = NumericSpinBox()
        self.parts.setRange(2, 20)
        self.parts.setValue(2)
        form.addRow(i18n.tr("lbl.sections"), self.parts)
        self._body.addLayout(form)
        self.section_label = QLabel()
        self.section_label.setProperty("dim", True)
        self._body.addWidget(self.section_label)
        self.parts.valueChanged.connect(self._update_label)
        self._update_label()
        hint = QLabel(i18n.tr("dlg.split_video.hint"))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        self._body.addWidget(hint)
        self.add_buttons(i18n.tr("btn.split_video"))

    def _update_label(self) -> None:
        if self._duration:
            self.section_label.setText(i18n.tr(
                "dlg.split_video.about",
                per=f"{self._duration / self.parts.value():.2f}",
                total=f"{self._duration:.2f}"))

    def _accept_clicked(self) -> None:
        path = self._path
        parts = self.parts.value()
        progress.run_job(
            i18n.tr("action.splitting", name=path.name),
            lambda ctx: [tools.split_video(path, parts, ctx, set())],
        )
        self.accept()


class RedactVideoDialog(ToolDialog):
    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.redact_video.title"), parent)
        self._path = Path(path)
        self._duration = tools.probe_duration_seconds(self._path) or 0.0
        self.pane = VideoPane(self._path, height=220)
        self.resize(540, 480)
        self._body.addWidget(self.pane)

        from PySide6.QtWidgets import QTableWidget

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [i18n.tr("lbl.start"), i18n.tr("lbl.end"), "X", "Y", "W", "H"])
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(140)
        self._body.addWidget(self.table)

        row = QHBoxLayout()
        draw = chip_button(i18n.tr("btn.draw_box"))
        draw.clicked.connect(self._draw_box)
        extend = chip_button(i18n.tr("btn.extend_end"))
        extend.clicked.connect(self._extend)
        remove = chip_button(i18n.tr("btn.delete_selected"))
        remove.clicked.connect(self._delete)
        row.addWidget(draw)
        row.addWidget(extend)
        row.addWidget(remove)
        row.addStretch(1)
        self._body.addLayout(row)

        row2 = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(
            [i18n.tr("opt.solid"), i18n.tr("opt.blur"), i18n.tr("opt.pixelate")]
        )
        self.color_button = QPushButton(i18n.tr("btn.color"))
        self._color = QColor("#000000")
        self._sync_color()
        self.color_button.clicked.connect(self._pick_color)
        row2.addWidget(section_label(i18n.tr("lbl.effect")))
        row2.addWidget(self.mode)
        row2.addWidget(self.color_button)
        row2.addStretch(1)
        self._body.addLayout(row2)

        hint = QLabel(i18n.tr("dlg.redact_video.hint"))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        self._body.addWidget(hint)
        self._frame_size = (0, 0)
        self.loading = QLabel(i18n.tr("lbl.loading"))
        self.loading.setProperty("dim", True)
        self._body.addWidget(self.loading)
        self.add_buttons(i18n.tr("btn.save_redacted"))
        QTimer.singleShot(50, self._load_frame_size)

    def _load_frame_size(self) -> None:
        video = tools.probe(self._path).video()
        if video:
            self._frame_size = (video.width, video.height)
        self.loading.setVisible(False)

    def _sync_color(self) -> None:
        self.color_button.setStyleSheet(
            f"border-left: 16px solid {self._color.name()}; padding-left: 8px;")

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self, i18n.tr("dlg.redact.color_title"))
        if chosen.isValid():
            self._color = chosen
            self._sync_color()

    def _draw_box(self) -> None:
        seconds = self.pane._player.position() / 1000.0
        frame = _grab_frame(self._path, seconds)
        if frame is None:
            QMessageBox.warning(
            self, i18n.tr("dlg.redact_video.title"),
            i18n.tr("dlg.snapshots.no_frame"))
            return
        dialog = BoxDrawDialog(frame, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.box is not None:
            x, y, w, h = dialog.box
            self._add_row(seconds, min(self._duration, seconds + 2.0), x, y, w, h)

    def _add_row(self, start: float, end: float, x: int, y: int, w: int, h: int) -> None:
        from PySide6.QtWidgets import QTableWidgetItem

        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate((f"{start:.2f}", f"{end:.2f}", str(x), str(y), str(w), str(h))):
            self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def _extend(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        from PySide6.QtWidgets import QTableWidgetItem

        self.table.setItem(row, 1, QTableWidgetItem(f"{self._duration:.2f}"))

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _boxes(self) -> list[dict]:
        boxes = []
        invalid: list[int] = []
        width, height = self._frame_size
        for row in range(self.table.rowCount()):
            try:
                values = [float(self.table.item(row, column).text()) for column in range(6)]
            except (AttributeError, ValueError):
                invalid.append(row + 1)
                continue
            start, end, x, y, w, h = values
            if not (0 <= start < end <= self._duration + 0.005) or w < 1 or h < 1:
                invalid.append(row + 1)
                continue
            if width > 0:
                x = max(0.0, min(x, width - 1.0))
            if height > 0:
                y = max(0.0, min(y, height - 1.0))
            boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h),
                          "start": start, "end": end})
        if invalid:
            rows = ", ".join(str(number) for number in invalid)
            QMessageBox.warning(
                self, i18n.tr("dlg.redact_video.title"),
                i18n.tr("dlg.redact_video.rows_ignored", rows=rows))
        return boxes

    def _accept_clicked(self) -> None:
        boxes = self._boxes()
        if not boxes:
            QMessageBox.warning(
            self, i18n.tr("dlg.redact_video.title"),
            i18n.tr("dlg.redact_video.need_box"))
            return
        mode = ("solid", "blur", "pixelate")[self.mode.currentIndex()]
        path = self._path
        color = self._color.name()
        progress.run_job(
            i18n.tr("action.redacting", name=path.name),
            lambda ctx: [tools.redact_video(path, boxes, mode, color, ctx, set())],
        )
        self.accept()


class JoinDialog(ToolDialog):
    def __init__(self, paths, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.join.title"), parent)
        self._paths = [Path(p) for p in paths]
        order = QGroupBox(i18n.tr("lbl.order"))
        layout = QHBoxLayout(order)
        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        layout.addWidget(self.list, 1)
        buttons = QVBoxLayout()
        up = chip_button(i18n.tr("btn.move_up"))
        down = chip_button(i18n.tr("btn.move_down"))
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        buttons.addWidget(up)
        buttons.addWidget(down)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        for index, path in enumerate(self._paths, start=1):
            item = QListWidgetItem(f"{index}. {path.name}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self._body.addWidget(order)
        hint = QLabel(i18n.tr("dlg.join.hint"))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        self._body.addWidget(hint)
        self.add_buttons(i18n.tr("btn.join_videos"))

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(new_row, item)
        self.list.setCurrentRow(new_row)

    def _ordered(self) -> list[Path]:
        ordered = []
        pool = list(self._paths)
        for index in range(self.list.count()):
            data = self.list.item(index).data(Qt.ItemDataRole.UserRole)
            if data is None:
                continue
            path = Path(data)
            if path in pool:
                ordered.append(path)
                pool.remove(path)
        ordered.extend(pool)
        return ordered

    def _accept_clicked(self) -> None:
        ordered = self._ordered()
        progress.run_job(
            i18n.tr("action.joining"),
            lambda ctx: [tools.join_videos(ordered, ctx, set())],
        )
        self.accept()
