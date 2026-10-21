"""Headless runtime smoke checks for the image editor paths."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import traceback


def editors_smoke() -> int:
    """Exercise real editor controls and image tools without a visible UI.

    The receipt is written to ``%TEMP%/Tangerine-editors-smoke.json``. All
    settings writes made by the checks are redirected to a disposable folder.
    """
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    receipt_path = Path(tempfile.gettempdir()) / "Tangerine-editors-smoke.json"
    checks: list[dict] = []
    receipt: dict = {"version": "unknown", "ok": False, "checks": checks}
    old_settings_file = None
    old_settings_cache = None
    settings_module = None
    paths_module = None

    def check(name, operation):
        try:
            detail = operation()
        except Exception:
            checks.append({"name": name, "ok": False,
                           "traceback": traceback.format_exc()})
            raise
        checks.append({"name": name, "ok": True, "detail": detail})

    try:
        # Keep Qt imports below the environment assignment above.
        from PySide6.QtCore import QPoint, QEventLoop, QSignalBlocker, Qt, QTimer
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from PIL import Image, ImageChops, ImageDraw

        from . import paths as paths_module
        from . import settings as settings_module
        from .editors.images import (
            AnnotateDialog,
            BackgroundDialog,
            CropImageDialog,
            render_annotations,
        )
        from .editors.ui.controls import NumericSpinBox
        from . import tools

        receipt["version"] = paths_module.APP_VERSION
        old_settings_file = paths_module.settings_file
        old_settings_cache = settings_module._cache

        with tempfile.TemporaryDirectory(prefix="tangerine_editors_smoke_") as temp:
            root = Path(temp)
            settings_path = root / "settings.json"
            paths_module.settings_file = lambda: settings_path
            settings_module._cache = None

            app = QApplication.instance() or QApplication(["Tangerine editor smoke"])
            source_paths = [root / "smoke-one.png", root / "smoke-two.png"]
            for index, path in enumerate(source_paths):
                image = Image.new("RGB", (96, 72), (35 + index * 35, 90, 160))
                draw = ImageDraw.Draw(image)
                draw.rectangle((8, 8, 87, 63), outline=(240, 130, 20), width=3)
                draw.line((8, 60, 85, 10), fill=(250, 240, 40), width=2)
                image.save(path)

            def annotation_check():
                dialog = AnnotateDialog(source_paths[0])
                canvas = dialog.canvas
                try:
                    canvas.tool = "rect"
                    canvas.show()
                    app.processEvents()
                    before = canvas.grab().toImage()
                    start_f = canvas.to_widget(14, 14)
                    end_f = canvas.to_widget(78, 56)
                    start = QPoint(round(start_f.x()), round(start_f.y()))
                    end = QPoint(round(end_f.x()), round(end_f.y()))
                    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
                    QTest.mouseMove(canvas, end)
                    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
                    app.processEvents()
                    after = canvas.grab().toImage()
                    assert canvas.ops, "Annotate canvas did not record the drag operation"
                    assert any(
                        before.pixel(x, y) != after.pixel(x, y)
                        for y in range(after.height())
                        for x in range(after.width())
                    ), "Annotate canvas did not render its operation"

                    output = render_annotations(source_paths[0], list(canvas.ops))
                    with Image.open(source_paths[0]) as original, Image.open(output) as saved:
                        assert saved.size == original.size == (96, 72)
                        difference = ImageChops.difference(
                            original.convert("RGB"), saved.convert("RGB"))
                        assert difference.getbbox(), "Rendered annotation has no changed pixels"
                    return {"ops": len(canvas.ops), "size": list(saved.size),
                            "output": output.name}
                finally:
                    canvas.close()
                    dialog.close()

            check("annotate_canvas_render_and_output", annotation_check)

            def crop_check():
                dialog = CropImageDialog(source_paths[0])
                canvas = dialog.canvas
                try:
                    dialog.aspect.setCurrentIndex(2)  # 3:2
                    assert canvas.aspect_ratio == 1.5
                    canvas.show()
                    app.processEvents()
                    handles = canvas._handles()
                    assert len(handles) == 8
                    start_f = handles["rm"]
                    start = QPoint(round(start_f.x()), round(start_f.y()))
                    end = QPoint(start.x() - 24, start.y())
                    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
                    QTest.mouseMove(canvas, end)
                    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
                    app.processEvents()
                    x, y, width, height = canvas.rect
                    assert width < 96 and height > 8, f"Crop handle did not resize: {canvas.rect}"
                    assert dialog.w_spin._up_button.isEnabled(), "Crop drag left numeric increase disabled"
                    previous_width = dialog.w_spin.value()
                    QTest.mouseClick(dialog.w_spin._up_button, Qt.MouseButton.LeftButton)
                    assert dialog.w_spin.value() == previous_width + 1
                    x, y, width, height = canvas.rect
                    box = (round(x), round(y), round(x + width), round(y + height))
                    output = tools.crop_image(
                        source_paths[0], box,
                        tools.Ctx(progress=lambda _value: None, status=lambda _text: None),
                        set(),
                    )
                    with Image.open(output) as cropped:
                        expected = (box[2] - box[0], box[3] - box[1])
                        assert cropped.size == expected and min(cropped.size) > 8
                    return {"aspect": canvas.aspect_ratio, "handles": len(handles),
                            "size": list(cropped.size), "output": output.name}
                finally:
                    canvas.close()
                    dialog.close()

            check("crop_aspect_handles_and_output", crop_check)

            def numeric_check():
                spin = NumericSpinBox()
                annotate = AnnotateDialog(source_paths[0])
                try:
                    spin.setRange(0, 5)
                    spin.setValue(5)
                    assert not spin._up_button.isEnabled()
                    with QSignalBlocker(spin):
                        spin.setValue(2)
                    assert spin._up_button.isEnabled(), "Signal-blocked updates left the step button disabled"
                    spin.resize(180, 50)
                    spin.show()
                    app.processEvents()
                    QTest.mouseClick(spin._up_button, Qt.MouseButton.LeftButton)
                    assert spin.value() == 3, f"Up button gave {spin.value()}"
                    QTest.mouseClick(spin._down_button, Qt.MouseButton.LeftButton)
                    assert spin.value() == 2, f"Down button gave {spin.value()}"
                    annotate.width_slider.setValue(7)
                    assert annotate.canvas.stroke_width == 7
                    assert callable(annotate.canvas.width)
                    assert annotate.canvas.width() == 520
                    return {"step_value": spin.value(), "blocked_signal_refresh": True, "stroke_width": 7,
                            "canvas_width": annotate.canvas.width()}
                finally:
                    spin.close()
                    annotate.close()

            check("numeric_buttons_and_annotation_width", numeric_check)

            def wait_progress(window, label: str) -> dict:
                deadline = time.monotonic() + 14.0
                loop = QEventLoop()
                poll = QTimer()
                poll.setInterval(20)

                def done():
                    if getattr(window, "failed", False):
                        loop.quit()
                    elif getattr(window, "_job_done", False) and not window.isVisible():
                        loop.quit()

                poll.timeout.connect(done)
                window.job.finished.connect(done)
                window.job.failed.connect(done)
                poll.start()
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(loop.quit)
                timeout.start(14000)
                try:
                    done()
                    if not (getattr(window, "failed", False)
                            or (getattr(window, "_job_done", False) and not window.isVisible())):
                        loop.exec()
                finally:
                    poll.stop()
                    timeout.stop()
                if time.monotonic() >= deadline and window.isVisible():
                    raise TimeoutError(f"{label} progress did not auto-close within 14 seconds")
                if getattr(window, "failed", False):
                    raise RuntimeError(f"{label} progress failed")
                if not getattr(window, "_job_done", False) or window.isVisible():
                    raise TimeoutError(f"{label} progress did not auto-close")
                outputs = [Path(path) for path in window.outputs]
                if len(outputs) != 2 or not all(path.is_file() for path in outputs):
                    raise AssertionError(f"{label} expected two completed outputs, got {outputs}")
                sizes = []
                for path in outputs:
                    with Image.open(path) as image:
                        sizes.append(list(image.size))
                        if image.size != (108, 108):
                            raise AssertionError(f"{label} unexpected output dimensions: {image.size}")
                return {"outputs": [path.name for path in outputs], "sizes": sizes,
                        "autoclosed": True}

            def background_check():
                first = BackgroundDialog(source_paths)
                try:
                    first.reuse_options.setChecked(True)
                    first.aspect.setCurrentIndex(1)  # 1:1
                    first.margin.setValue(6)
                    first._accept_clicked()
                    first_window = first.job_window
                    first_detail = wait_progress(first_window, "Background first run")

                    second = BackgroundDialog(source_paths)
                    try:
                        assert second.reuse_options.isChecked()
                        called_exec = {"value": False}

                        def forbidden_exec():
                            called_exec["value"] = True
                            raise AssertionError("exec() should be bypassed when replay is enabled")

                        second.exec = forbidden_exec
                        result = second.exec_with_defaults()
                        assert result == second.DialogCode.Accepted
                        assert not called_exec["value"]
                        second_detail = wait_progress(second.job_window,
                                                      "Background replay run")
                    finally:
                        second.close()
                    return {"first": first_detail, "replay": second_detail,
                            "exec_bypassed": True}
                finally:
                    first.close()

            check("background_batch_defaults_replay_and_autoclose", background_check)

        receipt["ok"] = all(item.get("ok") is True for item in checks)
    except Exception:
        receipt["ok"] = False
        receipt["traceback"] = traceback.format_exc()
    finally:
        if paths_module is not None and old_settings_file is not None:
            paths_module.settings_file = old_settings_file
        if settings_module is not None:
            settings_module._cache = old_settings_cache
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        temp_receipt = receipt_path.with_suffix(".json.tmp")
        temp_receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        os.replace(temp_receipt, receipt_path)

    print(json.dumps({"receipt": str(receipt_path), "ok": receipt["ok"],
                      "checks": checks}, indent=2))
    return 0 if receipt["ok"] else 1
