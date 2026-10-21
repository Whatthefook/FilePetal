from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import engines, i18n, settings, tools
from .jobs import Job, batch_ctx
from .progress import ProgressWindow, run_job

_COMPRESS_KEYS = {
    "img.compress": "image",
    "vid.compress": "video",
    "aud.compress": "audio",
}


def run_conversions(file_paths, target, parent=None, label=None, anchor=None):
    paths = [Path(p) for p in file_paths]
    if not paths:
        return None
    if target == "pdf":
        from .image_pdf import is_pdf_image
        if all(is_pdf_image(p) for p in paths):
            from .editors.pdf import open_images_pdf
            return open_images_pdf(paths, parent)
    if label:
        title = label
    elif len(paths) == 1:
        title = i18n.tr("action.file_to", name=paths[0].name, target=target.upper())
    else:
        title = i18n.tr("action.converting_many", n=len(paths), target=target.upper())
    reserved: set[str] = set()

    def work(ctx):
        outputs = []
        total = len(paths)
        for index, path in enumerate(paths):
            fctx = batch_ctx(ctx, total, index) if total > 1 else ctx
            if total > 1:
                ctx.status(i18n.tr(
                    "action.converting_progress",
                    name=path.name, index=index + 1, total=total,
                ))
            else:
                ctx.status(i18n.tr("action.converting_file", name=path.name))
            outputs.extend(engines.convert_single(path, target, fctx, reserved))
        return outputs

    if anchor is not None:
        return run_job(title, work, parent, anchor=anchor)
    return run_job(title, work, parent)


def _clean_text(path, ctx, reserved):
    import subprocess

    source = Path(path)
    data = source.read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    cleaned = "\n".join(lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    out = tools._unique(source.parent, source.stem, " Clean.txt", reserved)
    ctx.status(i18n.tr("action.cleaning", name=source.name))
    out.write_text(cleaned, encoding="utf-8")
    return [out]


_DIRECT = {
    "arc.extract": ("action.extracting_archive", lambda paths, ctx, reserved: [engines.extract_archive(paths[0], ctx, reserved)]),
    "pdf.merge": ("action.merging_pdfs", lambda paths, ctx, reserved: [tools.merge_pdfs(paths, ctx, reserved)]),
    "pdf.split": ("action.splitting_pdf", lambda paths, ctx, reserved: [tools.split_pdf(paths[0], ctx, reserved)]),
    "vid.removeaudio": ("action.removing_audio", lambda paths, ctx, reserved: [tools.remove_audio(paths[0], ctx, reserved)]),
    "aud.normalize": ("action.normalizing_volume", lambda paths, ctx, reserved: [tools.normalize_audio(paths[0], ctx, reserved)]),
    "txt.compress": ("action.tidying_text", lambda paths, ctx, reserved: _clean_text(paths[0], ctx, reserved)),
    "pdf.compress": ("action.compressing_pdf", lambda paths, ctx, reserved: [tools.compress_pdf(paths[0], ctx, reserved)]),
    "doc.compress": ("action.compressing_document", lambda paths, ctx, reserved: [tools.compress_document(paths[0], ctx, reserved)]),
}


def run_tool(file_paths, key, parent=None, label=None, anchor=None):
    paths = [Path(p) for p in file_paths]
    if not paths:
        return None

    if key == "img.pdf":
        from .editors.pdf import open_images_pdf
        return open_images_pdf(paths, parent)

    if key == "qr.read" or key.endswith(".qr"):
        return _run_qr(paths, parent)

    entry = _DIRECT.get(key)
    if entry is not None:
        title_key, fn = entry
        reserved: set[str] = set()
        if anchor is not None:
            return run_job(label or i18n.tr(title_key), lambda ctx: fn(paths, ctx, reserved), parent, anchor=anchor)
        return run_job(label or i18n.tr(title_key), lambda ctx: fn(paths, ctx, reserved), parent)

    family = _COMPRESS_KEYS.get(key)
    if family is not None:
        return _lazy(parent, lambda: __import__("tangerine.editors", fromlist=["editors"]).run_compress(paths, family, parent))

    return _lazy(parent, lambda: __import__("tangerine.editors", fromlist=["editors"]).open_editor(paths, key, parent, label))


def _lazy(parent, call):
    try:
        return call()
    except ImportError:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            parent,
            i18n.tr("app.name"),
            i18n.tr("action.optional_editor_missing"),
        )
        return None


class ResultsWindow(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("action.qr_title"))
        self.setMinimumSize(520, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QLabel(i18n.tr(
            "action.qr_results" if results else "action.qr_empty"))
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(10)

        all_text = []
        for source, where, text in results:
            card = QWidget(objectName="Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)
            tag = QLabel(f"{source}" + (f" — {where}" if where else ""))
            tag.setStyleSheet("font-size: 11px; color: palette(mid);")
            body = QPlainTextEdit(text)
            body.setReadOnly(True)
            body.setFixedHeight(72)
            row = QHBoxLayout()
            row.addStretch(1)
            copy = QPushButton(i18n.tr("action.copy"))
            copy.setProperty("flat", True)
            copy.clicked.connect(lambda _=False, t=text: _copy(t))
            row.addWidget(copy)
            card_layout.addWidget(tag)
            card_layout.addWidget(body)
            card_layout.addLayout(row)
            inner_layout.addWidget(card)
            all_text.append(text)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        copy_all = QPushButton(i18n.tr("action.copy_all"))
        copy_all.setProperty("accent", True)
        copy_all.clicked.connect(lambda: _copy("\n".join(all_text)))
        copy_all.setEnabled(bool(all_text))
        close = QPushButton(i18n.tr("action.done"))
        close.setProperty("flat", True)
        close.clicked.connect(self.accept)
        footer.addWidget(copy_all)
        footer.addWidget(close)
        layout.addLayout(footer)


def _copy(text):
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText(text)


def _run_qr(paths, parent):
    holder = {}

    def work(ctx):
        ctx.status(i18n.tr("action.scanning_qr"))
        holder["results"] = tools.read_qr_codes(paths, ctx)
        return list(paths)

    job = Job(work, parent)
    window = ProgressWindow(i18n.tr("action.read_qr"), job, parent)
    window.show()
    job.finished.connect(lambda _results: ResultsWindow(holder.get("results", []), None).exec())
    job.start()
    return window


def run_share(file_paths, parent=None):
    import os
    paths = [Path(p) for p in file_paths if Path(p).exists()]
    if not paths:
        return None
    success = False
    try:
        import comtypes.client
        shell = comtypes.client.CreateObject("Shell.Application")
        for p in paths:
            abs_p = str(p.resolve())
            folder = shell.NameSpace(os.path.dirname(abs_p))
            if folder:
                item = folder.ParseName(os.path.basename(abs_p))
                if item:
                    for v in item.Verbs():
                        clean = v.Name.replace("&", "").strip().lower()
                        if clean == "share":
                            v.DoIt()
                            success = True
                            break
            if success:
                break
    except Exception as exc:
        log.warning("Windows Share verb invocation failed: %s", exc)

    if not success:
        run_copy_refs(file_paths, parent)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent,
            i18n.tr("app.name"),
            i18n.tr("action.share_fallback_copied"),
        )
    return None


def run_shelf(file_paths, parent=None):
    from . import shelf
    return shelf.open_shelf(file_paths, parent)


def run_copy_refs(file_paths, parent=None):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtWidgets import QApplication
    paths = [Path(p).resolve() for p in file_paths if Path(p).exists()]
    if not paths:
        return None
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    mime.setText("\n".join(str(p) for p in paths))
    cb = QApplication.clipboard()
    if cb is not None:
        cb.setMimeData(mime)
    return None


def run_move(file_paths, parent=None):
    import shutil
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from . import naming
    paths = [Path(p) for p in file_paths if Path(p).exists()]
    if not paths:
        return None
    start_dir = str(paths[0].parent)
    dest_dir = QFileDialog.getExistingDirectory(parent, i18n.tr("action.move_select_folder"), start_dir)
    if not dest_dir:
        return None
    dest_path = Path(dest_dir).resolve()
    reserved: set[Path] = set()
    errors = []
    for src in paths:
        src_resolved = src.resolve()
        if src_resolved.parent == dest_path:
            continue
        try:
            target = naming.unique_path(dest_path, src.stem, src.suffix, reserved)
            shutil.move(str(src_resolved), str(target))
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")
    if errors:
        QMessageBox.warning(
            parent,
            i18n.tr("app.name"),
            i18n.tr("action.move_error", error="\n".join(errors)),
        )
    return len(paths) - len(errors)


def run_copy_paths(file_paths, parent=None):
    from PySide6.QtWidgets import QApplication
    paths = [str(Path(p).resolve()) for p in file_paths]
    if not paths:
        return None
    text = "\n".join(paths)
    cb = QApplication.clipboard()
    if cb is not None:
        cb.setText(text)
    return None


def run_terminal(file_paths, parent=None):
    import shlex
    import shutil
    import subprocess
    paths = [Path(p).resolve() for p in file_paths]
    if not paths:
        return None
    target_dir = paths[0].parent if paths[0].is_file() else paths[0]
    folder_str = str(target_dir)
    if sys.platform == "darwin":
        command = f"cd {shlex.quote(folder_str)}"
        escaped = command.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{escaped}"'])
        return None
    if sys.platform.startswith("linux"):
        candidates = (
            ("x-terminal-emulator", "--working-directory", folder_str),
            ("gnome-terminal", f"--working-directory={folder_str}"),
            ("konsole", "--workdir", folder_str),
            ("xfce4-terminal", f"--working-directory={folder_str}"),
            ("kitty", "--directory", folder_str),
            ("alacritty", "--working-directory", folder_str),
        )
        for name, *arguments in candidates:
            executable = shutil.which(name)
            if executable:
                subprocess.Popen([executable, *arguments])
                return None
        raise RuntimeError("No supported terminal emulator was found.")
    wt = shutil.which("wt") or shutil.which("wt.exe")
    if wt:
        subprocess.Popen([wt, "-d", folder_str])
    else:
        powershell = shutil.which("powershell.exe") or "powershell.exe"
        subprocess.Popen([powershell, "-NoExit", "-Command", f"Set-Location -LiteralPath '{folder_str}'"])
    return None


def run_action(file_paths, key, parent=None, label=None, anchor=None):
    if key == "act.share":
        return run_share(file_paths, parent)
    if key == "act.shelf":
        return run_shelf(file_paths, parent)
    if key == "act.copy_ref":
        run_copy_refs(file_paths, parent)
        from .toast import show_toast
        show_toast(i18n.tr("action.refs_copied"), anchor=anchor)
        return None
    if key == "act.move":
        moved = run_move(file_paths, parent)
        if moved:
            from .toast import show_toast
            show_toast(i18n.tr("action.move_success", n=moved), anchor=anchor)
        return None
    if key == "act.copy_path":
        run_copy_paths(file_paths, parent)
        from .toast import show_toast
        show_toast(i18n.tr("action.paths_copied"), anchor=anchor)
        return None
    if key == "act.terminal":
        try:
            run_terminal(file_paths, parent)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(parent, i18n.tr("app.name"), str(exc))
            return None
        from .toast import show_toast
        paths = [Path(p).resolve() for p in file_paths]
        folder_name = paths[0].parent.name if paths[0].is_file() else paths[0].name
        show_toast(i18n.tr("action.terminal_opened", folder=folder_name), anchor=anchor)
        return None
    return None
