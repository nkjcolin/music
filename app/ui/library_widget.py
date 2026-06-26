"""The Library page: browse downloads — search, sort, play, tag, rename, delete."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import library as library_mod
from ..core import metadata as metadata_mod
from . import theme
from .metadata_dialog import MetadataDialog

_AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg")

# Cache decoded cover thumbnails by (path, mtime) so re-opening Library is fast.
_THUMB_CACHE: dict[tuple, QPixmap] = {}

SORT_MODES = ["Recent", "Name (A–Z)", "Largest"]


def _human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _fmt_duration(seconds) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _thumbnail(info: dict) -> QPixmap:
    key = (info["path"], info["mtime"])
    cached = _THUMB_CACHE.get(key)
    if cached is not None:
        return cached
    pix = QPixmap()
    data = metadata_mod.read_cover(info["path"])
    if data and pix.loadFromData(data):
        pix = pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    else:
        pix = QPixmap()  # empty -> caller shows an icon
    _THUMB_CACHE[key] = pix
    return pix


class LibraryRow(QFrame):
    """A single downloaded file: thumbnail, name, tags, and per-row actions."""

    play_requested = Signal(str)   # file path
    deleted = Signal(str)          # file path

    def __init__(self, info: dict, tags: dict, duration, release_cb=None) -> None:
        super().__init__()
        self.setObjectName("queueRow")
        self.info = info
        self._release_cb = release_cb   # called with the path before deletion
        self.haystack = " ".join([
            info["stem"], tags.get("artist", ""), tags.get("album", ""),
        ]).lower()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        self.check = QCheckBox()
        self.check.setToolTip("Select for bulk actions")
        lay.addWidget(self.check)

        is_audio = info["ext"].lower() in _AUDIO_EXTS
        thumb = QLabel()
        thumb.setFixedSize(40, 40)
        thumb.setAlignment(Qt.AlignCenter)
        pix = _thumbnail(info) if is_audio else QPixmap()
        if pix.isNull():
            thumb.setPixmap(theme.icon(
                "fa5s.music" if is_audio else "fa5s.film", theme.ACCENT).pixmap(20, 20))
        else:
            thumb.setPixmap(pix)
        lay.addWidget(thumb)

        if is_audio:
            play_btn = QPushButton()
            play_btn.setIcon(theme.icon("fa5s.play", theme.ACCENT))
            play_btn.setToolTip("Play in app")
            play_btn.setFixedSize(34, 34)
            play_btn.clicked.connect(lambda: self.play_requested.emit(self.info["path"]))
            lay.addWidget(play_btn)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.name_edit = QLineEdit(info["stem"])
        self.name_edit.returnPressed.connect(self._rename)
        text.addWidget(self.name_edit)
        subtitle_bits = [b for b in (
            tags.get("artist", ""), tags.get("album", ""), _fmt_duration(duration)) if b]
        self.subtitle = QLabel("  •  ".join(subtitle_bits))
        self.subtitle.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        text.addWidget(self.subtitle)
        lay.addLayout(text, 1)

        ext = QLabel(info["ext"])
        ext.setStyleSheet(f"color: {theme.TEXT_DIM};")
        ext.setMinimumWidth(44)
        lay.addWidget(ext)

        size = QLabel(_human_size(info["size"]))
        size.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        size.setMinimumWidth(66)
        size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(size)

        rename_btn = self._mini("fa5s.pen", "Rename", self._rename)
        lay.addWidget(rename_btn)
        tags_btn = self._mini("fa5s.tag", "Edit metadata", self._edit_tags)
        lay.addWidget(tags_btn)
        del_btn = self._mini("fa5s.trash", "Delete file", self._delete)
        lay.addWidget(del_btn)
        open_btn = self._mini("fa5s.folder-open", "Open file location", self._open_location)
        lay.addWidget(open_btn)

    def _mini(self, icon_name: str, tip: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(theme.icon(icon_name, theme.TEXT_DIM))
        btn.setToolTip(tip)
        btn.setFixedSize(34, 34)
        btn.clicked.connect(slot)
        return btn

    # -- actions -----------------------------------------------------------
    def _rename(self) -> None:
        new_stem = self.name_edit.text().strip()
        if new_stem == self.info["stem"]:
            return
        try:
            new_path = library_mod.rename_media(self.info["path"], new_stem)
        except (ValueError, FileExistsError) as exc:
            QMessageBox.warning(self, "Rename failed", str(exc))
            self.name_edit.setText(self.info["stem"])
            return
        except OSError as exc:
            QMessageBox.warning(
                self, "Rename failed",
                f"Could not rename the file (it may be open in another app).\n\n{exc}")
            self.name_edit.setText(self.info["stem"])
            return
        self.info["path"] = new_path
        self.info["stem"] = os.path.splitext(os.path.basename(new_path))[0]
        self.name_edit.setText(self.info["stem"])

    def _edit_tags(self) -> None:
        MetadataDialog(self.info["path"], parent=self).exec()

    def _delete(self) -> None:
        name = os.path.basename(self.info["path"])
        if QMessageBox.question(
            self, "Delete file",
            f"Delete “{name}” from disk?\nThis also removes its lyrics file.",
        ) != QMessageBox.Yes:
            return
        if self._release_cb:               # let the player release it if playing
            self._release_cb(self.info["path"])
        try:
            library_mod.delete_media(self.info["path"])
        except OSError as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))
            return
        self.deleted.emit(self.info["path"])

    def _open_location(self) -> None:
        path = self.info["path"]
        if not os.path.exists(path):
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])


class LibraryWidget(QWidget):
    """Lists media files in the music folder with search, sort and bulk delete."""

    play_requested = Signal(str)   # file path

    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings
        self._rows: list[LibraryRow] = []
        # Set by MainWindow: callable(path) to release a file from the player
        # before deleting it (so a currently-playing track can be deleted).
        self.release_file = None

    def _release(self, path: str) -> None:
        if self.release_file:
            try:
                self.release_file(path)
            except Exception:
                pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Toolbar: filter, sort, bulk delete, refresh.
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by name, artist or album…")
        self.filter_input.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter_input, 1)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_MODES)
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.sort_combo)
        del_sel = QPushButton("  Delete selected")
        del_sel.setIcon(theme.icon("fa5s.trash", theme.TEXT))
        del_sel.clicked.connect(self._delete_selected)
        bar.addWidget(del_sel)
        refresh = QPushButton("  Refresh")
        refresh.setIcon(theme.icon("fa5s.sync", theme.TEXT))
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self.path_label)

        self.empty = QLabel("No downloaded files found in this folder yet.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 14px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(2, 2, 2, 2)
        self._vbox.setSpacing(8)
        self._vbox.addWidget(self.empty)
        self._vbox.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def _sorted(self, files: list[dict]) -> list[dict]:
        mode = self.sort_combo.currentText()
        if mode == "Name (A–Z)":
            return sorted(files, key=lambda d: d["stem"].lower())
        if mode == "Largest":
            return sorted(files, key=lambda d: d["size"], reverse=True)
        return sorted(files, key=lambda d: d["mtime"], reverse=True)  # Recent

    def refresh(self) -> None:
        """Re-scan the music folder and rebuild the list."""
        folder = self.settings.folder
        self.path_label.setText(folder)

        for row in self._rows:
            self._vbox.removeWidget(row)
            row.deleteLater()
        self._rows = []

        files = self._sorted(library_mod.list_media(folder))
        self.empty.setVisible(not files)
        for info in files:
            is_audio = info["ext"].lower() in _AUDIO_EXTS
            tags = metadata_mod.read_tags(info["path"]) if is_audio else {}
            duration = metadata_mod.read_duration(info["path"]) if is_audio else None
            row = LibraryRow(info, tags, duration, release_cb=self._release)
            row.play_requested.connect(self.play_requested)
            row.deleted.connect(self._on_row_deleted)
            self._rows.append(row)
            self._vbox.insertWidget(self._vbox.count() - 1, row)
        self._apply_filter(self.filter_input.text())

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for row in self._rows:
            row.setVisible(needle in row.haystack)

    def _on_row_deleted(self, path: str) -> None:
        for row in list(self._rows):
            if row.info["path"] == path:
                self._vbox.removeWidget(row)
                row.deleteLater()
                self._rows.remove(row)
        self.empty.setVisible(not self._rows)

    def _delete_selected(self) -> None:
        selected = [r for r in self._rows if r.check.isChecked()]
        if not selected:
            QMessageBox.information(self, "Delete selected", "No files are selected.")
            return
        if QMessageBox.question(
            self, "Delete selected",
            f"Delete {len(selected)} file(s) from disk? This also removes their lyrics.",
        ) != QMessageBox.Yes:
            return
        errors = 0
        for row in selected:
            self._release(row.info["path"])   # free it from the player if playing
            try:
                library_mod.delete_media(row.info["path"])
                self._on_row_deleted(row.info["path"])
            except OSError:
                errors += 1
        if errors:
            QMessageBox.warning(self, "Delete selected", f"{errors} file(s) could not be deleted.")
