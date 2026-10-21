"""Tests for FilePetal Actions wheel, shelf, actions runner, and archive traversal safety."""

import io
import os
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from tangerine import actions, catalog, engines, monitor, settings, shelf, theme
from tangerine.engines import EngineError


def test_actions_catalog():
    paths = [Path("test1.jpg"), Path("test2.pdf")]
    items = catalog.actions_for(paths)
    assert len(items) == 6
    action_ids = [item.id for item in items]
    assert "act.share" in action_ids
    assert "act.shelf" in action_ids
    assert "act.copy_ref" in action_ids
    assert "act.move" in action_ids
    assert "act.copy_path" in action_ids
    assert "act.terminal" in action_ids


def test_actions_modifier_detection(monkeypatch, qapp):
    mon = monitor.DragMonitor()
    try:
        mon.stop()
        monkeypatch.setattr(mon, "_held_modifiers", lambda: {"shift"})
        assert mon._mode_for_current_modifiers() == "conversion"

        monkeypatch.setattr(mon, "_held_modifiers", lambda: {"alt", "shift"})
        assert mon._mode_for_current_modifiers() == "tools"

        monkeypatch.setattr(mon, "_held_modifiers", lambda: {"ctrl", "shift"})
        assert mon._mode_for_current_modifiers() == "actions"

        monkeypatch.setattr(settings, "get", lambda k, d=None: "win+shift" if k == "actionsWheelDragModifierMask" else settings.DEFAULTS.get(k))
        monkeypatch.setattr(mon, "_held_modifiers", lambda: {"win", "shift"})
        assert mon._mode_for_current_modifiers() == "actions"
    finally:
        mon.stop()
        mon.deleteLater()


def test_copy_paths_action(tmp_path):
    file1 = tmp_path / "a.txt"
    file2 = tmp_path / "b.txt"
    file1.write_text("hello")
    file2.write_text("world")

    fake_cb = MagicMock()
    with patch("PySide6.QtWidgets.QApplication.clipboard", return_value=fake_cb):
        actions.run_copy_paths([str(file1), str(file2)])
    fake_cb.setText.assert_called_once()
    called_text = fake_cb.setText.call_args[0][0]
    assert str(file1.resolve()) in called_text
    assert str(file2.resolve()) in called_text


def test_copy_refs_action(tmp_path):
    file1 = tmp_path / "doc.pdf"
    file1.write_bytes(b"%PDF-1.4 dummy")

    fake_cb = MagicMock()
    with patch("PySide6.QtWidgets.QApplication.clipboard", return_value=fake_cb):
        actions.run_copy_refs([str(file1)])
    fake_cb.setMimeData.assert_called_once()
    mime = fake_cb.setMimeData.call_args[0][0]
    assert mime.hasUrls()
    urls = [u.toLocalFile() for u in mime.urls()]
    assert str(file1.resolve()).replace("\\", "/") in [u.replace("\\", "/") for u in urls]


def test_move_action_safe_collision(tmp_path):
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    src_dir.mkdir()
    dst_dir.mkdir()

    file1 = src_dir / "report.txt"
    file1.write_text("source file")

    existing = dst_dir / "report.txt"
    existing.write_text("existing file")

    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=str(dst_dir)):
        actions.run_move([str(file1)])

    assert existing.read_text() == "existing file"
    dest_collided = dst_dir / "report 2.txt"
    assert dest_collided.exists()
    assert dest_collided.read_text() == "source file"


def test_shelf_add_clear_files(tmp_path):
    file1 = tmp_path / "image.png"
    file1.write_bytes(b"\x89PNG dummy")

    # Construct without GUI loop
    shelf_win = shelf.FilePetalShelf()
    try:
        shelf_win.add_files([file1])
        assert shelf_win.list_widget.count() == 1

        shelf_win.clear_files()
        assert shelf_win.list_widget.count() == 0
    finally:
        theme.remove_theme_listener(shelf_win._apply_theme)
        shelf_win.close()
        shelf_win.deleteLater()


def test_zip_path_traversal_protection(tmp_path):
    malicious_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious_zip, "w") as z:
        z.writestr("../../evil.txt", "pwned")

    dest_dir = tmp_path / "extracted"
    dest_dir.mkdir()

    ctx = engines.Ctx(lambda _: None, lambda _: None, MagicMock(is_set=lambda: False))
    with pytest.raises(EngineError) as exc_info:
        engines._extract_archive(malicious_zip, dest_dir, ctx)
    assert "traversal" in str(exc_info.value).lower() or "rejected" in str(exc_info.value).lower() or "no segura" in str(exc_info.value).lower()


def test_tar_path_traversal_protection(tmp_path):
    malicious_tar = tmp_path / "evil.tar"
    with tarfile.open(malicious_tar, "w") as t:
        ti = tarfile.TarInfo(name="../../evil.txt")
        ti.size = 5
        t.addfile(ti, io.BytesIO(b"pwned"))

    dest_dir = tmp_path / "extracted_tar"
    dest_dir.mkdir()

    ctx = engines.Ctx(lambda _: None, lambda _: None, MagicMock(is_set=lambda: False))
    with pytest.raises(EngineError) as exc_info:
        engines._extract_archive(malicious_tar, dest_dir, ctx)
    assert "traversal" in str(exc_info.value).lower() or "rejected" in str(exc_info.value).lower() or "no segura" in str(exc_info.value).lower()
