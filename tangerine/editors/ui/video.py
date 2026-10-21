"""Video preview widget and the redaction box-drawing dialog."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ... import i18n
from ..base import ToolDialog, chip_button
from .canvas import RedactCanvas
from .waveform import PlayerMixin


class VideoPane(QWidget, PlayerMixin):
    def __init__(self, path: Path, parent: QWidget | None = None, height: int = 240):
        QWidget.__init__(self, parent)
        self._path = Path(path)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.video = QVideoWidget(self)
        self.video.setMinimumHeight(height)
        layout.addWidget(self.video, 1)
        self._setup_player()
        self._player.setVideoOutput(self.video)
        self._load_source(self._path)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        layout.addWidget(self.slider)
        self.slider.sliderMoved.connect(lambda value: self._player.setPosition(value))
        self._player.durationChanged.connect(self._on_duration)
        self._player.positionChanged.connect(self._on_position)

        controls = QHBoxLayout()
        play = chip_button(i18n.tr("btn.play"))
        play.clicked.connect(self.play)
        stop = chip_button(i18n.tr("btn.stop"))
        stop.clicked.connect(self._player.stop)
        self.time_label = QLabel("0:00.0 / 0:00.0")
        self.time_label.setProperty("dim", True)
        controls.addWidget(play)
        controls.addWidget(stop)
        controls.addStretch(1)
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

    def _on_duration(self, duration: int) -> None:
        self.slider.setRange(0, duration)
        self._update_time_label()

    def _on_position(self, position: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(position)
        self.slider.blockSignals(False)
        self._update_time_label()
        self.on_position(position)

    def on_position(self, position: int) -> None:
        pass

    def _update_time_label(self) -> None:
        def stamp(ms: int) -> str:
            seconds, _ = divmod(max(ms, 0) // 100, 10)
            minutes, seconds = divmod(seconds, 60)
            return f"{minutes}:{seconds:04.1f}"

        self.time_label.setText(
            f"{stamp(self._player.position())} / {stamp(self._player.duration())}")

    def play(self) -> None:
        self._player.play()

    def seek(self, seconds: float) -> None:
        self._player.setPosition(int(seconds * 1000))


class BoxDrawDialog(ToolDialog):
    def __init__(self, frame: Path, parent: QWidget | None = None):
        super().__init__(i18n.tr("dlg.boxdraw.title"), parent)
        self.canvas = RedactCanvas(frame)
        self.canvas.setMinimumSize(360, 220)
        self.canvas.resize(500, 320)
        self.resize(540, 440)
        self.box = None
        self._body.addWidget(self.canvas)
        hint = QLabel(i18n.tr("dlg.boxdraw.hint"))
        hint.setProperty("dim", True)
        self._body.addWidget(hint)
        self.add_buttons(i18n.tr("btn.use_box"))

    def _accept_clicked(self) -> None:
        if not self.canvas.boxes:
            QMessageBox.warning(
            self, i18n.tr("dlg.redact_video.title"),
            i18n.tr("dlg.boxdraw.need_box"))
            return
        box = self.canvas.boxes[-1]
        self.box = (int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"]))
        self.accept()
