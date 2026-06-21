"""The Library page: browse downloaded files and rename them in-app."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from . import theme


def _human_size(num: int) -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class LibraryRow(QFrame):
    """A single downloaded file with an editable name and rename/open controls."""

    def __init__(self, info: dict, on_renamed) -> None:
        super().__init__()
        self.setObjectName("queueRow")
        self.info = info
        self._on_renamed = on_renamed

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        is_audio = info["ext"].lower() in (".mp3", ".m4a")
        badge = QLabel()
        badge.setPixmap(theme.icon(
            "fa5s.music" if is_audio else "fa5s.film", theme.ACCENT
        ).pixmap(18, 18))
        lay.addWidget(badge)

        self.name_edit = QLineEdit(info["stem"])
        self.name_edit.returnPressed.connect(self._rename)
        lay.addWidget(self.name_edit, 1)

        ext = QLabel(info["ext"])
        ext.setStyleSheet(f"color: {theme.TEXT_DIM};")
        ext.setMinimumWidth(46)
        lay.addWidget(ext)

        size = QLabel(_human_size(info["size"]))
        size.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        size.setMinimumWidth(70)
        size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(size)

        save_btn = QPushButton("  Rename")
        save_btn.setIcon(theme.icon("fa5s.pen", theme.TEXT))
        save_btn.clicked.connect(self._rename)
        lay.addWidget(save_btn)

        open_btn = QPushButton()
        open_btn.setIcon(theme.icon("fa5s.folder-open", theme.TEXT_DIM))
        open_btn.setToolTip("Open file location")
        open_btn.setFixedSize(34, 34)
        open_btn.clicked.connect(self._open_location)
        lay.addWidget(open_btn)

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
                f"Could not rename the file (it may be open in another app).\n\n{exc}",
            )
            self.name_edit.setText(self.info["stem"])
            return

        self.info["path"] = new_path
        self.info["stem"] = os.path.splitext(os.path.basename(new_path))[0]
        self.name_edit.setText(self.info["stem"])
        if self._on_renamed:
            self._on_renamed(self.info["stem"])

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
    """Lists media files in the download folder and lets the user rename them."""

    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color: {theme.TEXT_DIM};")
        bar.addWidget(self.path_label, 1)
        refresh = QPushButton("  Refresh")
        refresh.setIcon(theme.icon("fa5s.sync", theme.TEXT))
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)

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

    def refresh(self) -> None:
        """Re-scan the download folder and rebuild the list."""
        folder = self.settings.folder
        self.path_label.setText(folder)

        # clear existing rows (keep empty label + trailing stretch)
        for i in reversed(range(self._vbox.count())):
            w = self._vbox.itemAt(i).widget()
            if isinstance(w, LibraryRow):
                self._vbox.takeAt(i)
                w.deleteLater()

        files = library_mod.list_media(folder)
        self.empty.setVisible(not files)
        for info in files:
            row = LibraryRow(info, on_renamed=lambda *_: None)
            self._vbox.insertWidget(self._vbox.count() - 1, row)
