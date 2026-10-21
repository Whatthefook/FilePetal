from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from tangerine import engines, image_pdf
from tangerine.image_pdf import PdfOptions


def _ctx(cancel: threading.Event | None = None, progress=None, status=None) -> engines.Ctx:
    return engines.Ctx(progress or (lambda _value: None), status or (lambda _text: None), cancel)


def _write_rgb(path: Path, color: tuple[int, int, int] = (200, 40, 20), size=(24, 16)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _windows_error(code: int) -> OSError:
    error = PermissionError(f"simulated Windows error {code}")
    error.winerror = code
    return error


def test_is_pdf_image_includes_requested_legacy_extensions():
    for suffix in (".jpg", ".svg", ".gif", ".jpe", ".jfif", ".dib", ".ico"):
        assert image_pdf.is_pdf_image(Path(f"photo{suffix}"))
    assert not image_pdf.is_pdf_image(Path("notes.txt"))


def test_ordered_paths_received_natural_and_manual():
    paths = [Path("photo10.jpg"), Path("photo2.jpg"), Path("photo1.jpg")]
    assert image_pdf.ordered_paths(paths, "received") == paths
    assert image_pdf.ordered_paths(paths, "manual") == paths
    assert image_pdf.ordered_paths(paths, "name") == [paths[2], paths[1], paths[0]]
    with pytest.raises(ValueError):
        image_pdf.ordered_paths(paths, "random")


def test_create_pdf_deduplicates_canonical_inputs_and_keeps_order(tmp_path):
    first = _write_rgb(tmp_path / "photo10.jpg", (240, 20, 10))
    second = _write_rgb(tmp_path / "photo2.jpg", (10, 240, 20))
    output = image_pdf.create_image_pdf(
        [first, second, tmp_path / "." / first.name], _ctx(),
        options=PdfOptions(order="received"),
    )
    assert output == tmp_path / "photo10 PDF.pdf"
    assert len(PdfReader(output).pages) == 2


def test_name_order_and_manual_order_drive_page_order(tmp_path, monkeypatch):
    paths = [
        _write_rgb(tmp_path / "page10.png"),
        _write_rgb(tmp_path / "page2.png"),
        _write_rgb(tmp_path / "page1.png"),
    ]
    observed: list[str] = []
    prepare = image_pdf._prepare_image

    def record(path, with_filename, font_scale):
        observed.append(path.name)
        return prepare(path, with_filename, font_scale)

    monkeypatch.setattr(image_pdf, "_prepare_image", record)
    image_pdf.create_image_pdf(paths, _ctx(), options=PdfOptions(order="name"))
    assert observed == ["page1.png", "page2.png", "page10.png"]

    observed.clear()
    image_pdf.create_image_pdf(paths, _ctx(), options=PdfOptions(order="manual"))
    assert observed == [path.name for path in paths]


def test_prepare_image_flattens_transparency_and_applies_exif_orientation(tmp_path):
    transparent = tmp_path / "transparent.png"
    rgba = Image.new("RGBA", (12, 8), (255, 0, 0, 0))
    rgba.putpixel((4, 3), (0, 120, 10, 255))
    rgba.save(transparent)
    prepared = image_pdf._prepare_image(transparent, False, 1.0)
    try:
        assert prepared.mode == "RGB"
        assert prepared.getpixel((0, 0)) == (255, 255, 255)
        assert prepared.getpixel((4, 3)) == (0, 120, 10)
    finally:
        prepared.close()

    oriented = tmp_path / "oriented.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (12, 8), (20, 40, 200)).save(oriented, exif=exif)
    prepared = image_pdf._prepare_image(oriented, False, 1.0)
    try:
        assert prepared.size == (8, 12)
    finally:
        prepared.close()


def test_filename_label_and_grid_layout(tmp_path):
    paths = [_write_rgb(tmp_path / f"scan-{index}.png") for index in range(5)]
    plain = image_pdf._prepare_image(paths[0], False, 1.0)
    labeled = image_pdf._prepare_image(paths[0], True, 1.0)
    try:
        assert labeled.height > plain.height
    finally:
        plain.close()
        labeled.close()

    output = image_pdf.create_image_pdf(
        paths, _ctx(), options=PdfOptions(rows=2, columns=2, with_filenames=True),
    )
    assert len(PdfReader(output).pages) == 2


def test_explicit_existing_output_is_not_overwritten(tmp_path):
    source = _write_rgb(tmp_path / "source.png")
    output = tmp_path / "chosen.pdf"
    output.write_bytes(b"keep existing bytes")
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([source], _ctx(), options=PdfOptions(output=output))
    assert output.read_bytes() == b"keep existing bytes"


def test_auto_output_reservation_uses_unique_sibling(tmp_path):
    source = _write_rgb(tmp_path / "source.png")
    original = tmp_path / "source.pdf"
    original.write_bytes(b"already here")
    output = image_pdf.create_image_pdf([source], _ctx())
    assert output == tmp_path / "source 2.pdf"
    assert original.read_bytes() == b"already here"
    assert len(PdfReader(output).pages) == 1


def test_concurrent_jobs_reserve_distinct_outputs(tmp_path):
    source = _write_rgb(tmp_path / "parallel.png")
    reserved: set[Path] = set()

    def run():
        return image_pdf.create_image_pdf([source], _ctx(), reserved)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda _index: run(), range(2)))
    assert len(set(outputs)) == 2
    assert {path.name for path in outputs} == {"parallel.pdf", "parallel 2.pdf"}
    assert {path.name for path in reserved} == {"parallel.pdf", "parallel 2.pdf"}
    assert all(len(PdfReader(path).pages) == 1 for path in outputs)


def test_corrupt_input_does_not_leave_output_or_reservation(tmp_path, monkeypatch):
    good = _write_rgb(tmp_path / "good.png")
    corrupt = tmp_path / "broken.jpg"
    corrupt.write_bytes(b"not an image")
    reserved: set[Path] = set()
    prepared: list[Image.Image] = []
    original_prepare = image_pdf._prepare_image

    def track_prepared(path, with_filename, font_scale):
        image = original_prepare(path, with_filename, font_scale)
        prepared.append(image)
        return image

    # The first loaded image must be closed when a later source is corrupt.
    monkeypatch.setattr(image_pdf, "_prepare_image", track_prepared)
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([good, corrupt], _ctx(), reserved)
    assert reserved == set()
    assert len(prepared) == 1
    with pytest.raises(ValueError):
        prepared[0].getpixel((0, 0))
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_empty_selection_raises_without_creating_files(tmp_path):
    reserved: set[Path] = set()
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([], _ctx(), reserved)
    assert reserved == set()
    assert list(tmp_path.iterdir()) == []


def test_cancel_before_processing_leaves_no_outputs(tmp_path):
    source = _write_rgb(tmp_path / "cancel.png")
    cancel = threading.Event()
    cancel.set()
    reserved: set[Path] = set()
    with pytest.raises(engines.EngineError, match="Cancelled|Cancelado"):
        image_pdf.create_image_pdf([source], _ctx(cancel), reserved)
    assert reserved == set()
    assert list(tmp_path.glob("*.pdf")) == []


def test_cancel_after_temp_save_cleans_temp_and_reservation(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "after-save.png")
    cancel = threading.Event()
    original_save = Image.Image.save

    def save_then_cancel(self, *args, **kwargs):
        result = original_save(self, *args, **kwargs)
        cancel.set()
        return result

    monkeypatch.setattr(Image.Image, "save", save_then_cancel)
    reserved: set[Path] = set()
    with pytest.raises(engines.EngineError, match="Cancelled|Cancelado"):
        image_pdf.create_image_pdf([source], _ctx(cancel), reserved)
    assert reserved == set()
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_read_only_input_is_accepted_and_wrapper_remains_compatible(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "readonly.png")
    source.chmod(0o444)
    monkeypatch.setattr(
        engines, "verify_writable",
        lambda _path: (_ for _ in ()).throw(AssertionError("source must be read-only")),
    )
    try:
        output = engines.images_to_pdf([source], _ctx(), set())
    finally:
        source.chmod(0o666)
    assert output == tmp_path / "readonly.pdf"
    assert len(PdfReader(output).pages) == 1


def test_progress_reaches_one_only_after_pdf_is_published(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "progress.png")
    values: list[float] = []
    output = tmp_path / "progress.pdf"
    original_replace = image_pdf.os.replace

    def assert_before_publish(src, dst):
        assert values and values[-1] < 1.0
        placeholder = Path(dst).read_bytes()
        assert placeholder and not placeholder.startswith(b"%PDF")
        return original_replace(src, dst)

    monkeypatch.setattr(image_pdf.os, "replace", assert_before_publish)
    result = image_pdf.create_image_pdf(
        [source], _ctx(progress=values.append), options=PdfOptions(output=output),
    )
    assert result == output
    assert values[-1] == 1.0
    assert len(PdfReader(output).pages) == 1


@pytest.mark.parametrize("winerror", [5, 32])
def test_publish_retries_transient_windows_sharing_errors(tmp_path, monkeypatch, winerror):
    source = _write_rgb(tmp_path / "retry.png")
    output = tmp_path / "retry.pdf"
    original_replace = image_pdf.os.replace
    attempts = 0
    monkeypatch.setattr(image_pdf, "_PUBLISH_RETRY_DELAYS", (0.0, 0.0))

    def fail_twice_then_replace(src, dst):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise _windows_error(winerror)
        return original_replace(src, dst)

    monkeypatch.setattr(image_pdf.os, "replace", fail_twice_then_replace)
    result = image_pdf.create_image_pdf([source], _ctx(), options=PdfOptions(output=output))

    assert result == output
    assert attempts == 3
    assert len(PdfReader(output).pages) == 1
    assert list(tmp_path.glob(".*.tmp")) == []


def test_persistent_windows_access_denied_is_not_swallowed(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "persistent.png")
    output = tmp_path / "persistent.pdf"
    reserved: set[Path] = set()
    attempts = 0
    monkeypatch.setattr(image_pdf, "_PUBLISH_RETRY_DELAYS", (0.0, 0.0))

    def always_denied(_src, _dst):
        nonlocal attempts
        attempts += 1
        raise _windows_error(5)

    monkeypatch.setattr(image_pdf.os, "replace", always_denied)
    with pytest.raises(engines.EngineError) as caught:
        image_pdf.create_image_pdf([source], _ctx(), reserved, PdfOptions(output=output))

    assert isinstance(caught.value.__cause__, OSError)
    assert getattr(caught.value.__cause__, "winerror", None) == 5
    assert attempts == 3
    assert reserved == set()
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_cancel_during_publish_retry_cleans_temp_and_reservation(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "cancel-retry.png")
    output = tmp_path / "cancel-retry.pdf"
    cancel = threading.Event()
    reserved: set[Path] = set()
    attempts = 0
    monkeypatch.setattr(image_pdf, "_PUBLISH_RETRY_DELAYS", (0.5, 0.5))

    def deny_and_cancel(_src, _dst):
        nonlocal attempts
        attempts += 1
        cancel.set()
        raise _windows_error(32)

    monkeypatch.setattr(image_pdf.os, "replace", deny_and_cancel)
    with pytest.raises(engines.EngineError, match="Cancelled|Cancelado"):
        image_pdf.create_image_pdf([source], _ctx(cancel), reserved, PdfOptions(output=output))

    assert attempts == 1
    assert reserved == set()
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_publish_retry_does_not_delete_replaced_foreign_reservation(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "foreign.png")
    output = tmp_path / "foreign.pdf"
    original_replace = image_pdf.os.replace
    reserved: set[Path] = set()
    attempts = 0
    foreign_bytes = b"another process owns this path"
    monkeypatch.setattr(image_pdf, "_PUBLISH_RETRY_DELAYS", (0.0, 0.0))

    def replace_reservation_then_deny(_src, dst):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            Path(dst).unlink()
            Path(dst).write_bytes(foreign_bytes)
            raise _windows_error(5)
        return original_replace(_src, dst)

    monkeypatch.setattr(image_pdf.os, "replace", replace_reservation_then_deny)
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([source], _ctx(), reserved, PdfOptions(output=output))

    assert attempts == 1
    assert output.read_bytes() == foreign_bytes
    assert reserved == set()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_publish_does_not_retry_winerror_33_byte_range_lock(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "range-lock.png")
    output = tmp_path / "range-lock.pdf"
    reserved: set[Path] = set()
    attempts = 0

    def range_locked(_src, _dst):
        nonlocal attempts
        attempts += 1
        raise _windows_error(33)

    monkeypatch.setattr(image_pdf.os, "replace", range_locked)
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([source], _ctx(), reserved, PdfOptions(output=output))

    assert attempts == 1
    assert reserved == set()
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_publish_does_not_retry_errno_5_without_windows_winerror(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "io-error.png")
    output = tmp_path / "io-error.pdf"
    attempts = 0

    def generic_io_error(_src, _dst):
        nonlocal attempts
        attempts += 1
        raise OSError(5, "simulated non-Windows I/O error")

    monkeypatch.setattr(image_pdf.os, "replace", generic_io_error)
    with pytest.raises(engines.EngineError):
        image_pdf.create_image_pdf([source], _ctx(), options=PdfOptions(output=output))

    assert attempts == 1
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_temp_cleanup_error_does_not_mask_persistent_publish_error(tmp_path, monkeypatch):
    source = _write_rgb(tmp_path / "cleanup.png")
    output = tmp_path / "cleanup.pdf"
    reserved: set[Path] = set()
    original_unlink = Path.unlink

    def fail_publish(_src, _dst):
        raise _windows_error(5)

    monkeypatch.setattr(image_pdf.os, "replace", fail_publish)

    def deny_temp_cleanup(path, missing_ok=False):
        if path.suffix == ".tmp":
            raise PermissionError("simulated temporary-file lock")
        return original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", deny_temp_cleanup)
    with pytest.raises(engines.EngineError) as caught:
        image_pdf.create_image_pdf([source], _ctx(), reserved, PdfOptions(output=output))

    assert getattr(caught.value.__cause__, "winerror", None) == 5
    assert reserved == set()
    assert not output.exists()
    leftovers = list(tmp_path.glob(".*.tmp"))
    assert len(leftovers) == 1
    # The simulated lock is released here so the test itself leaves no artifact.
    original_unlink(leftovers[0], missing_ok=True)
