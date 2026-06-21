"""Manual metadata editor with optional MusicBrainz auto-fill."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..core import enrich
from ..core import metadata as metadata_mod
from . import theme

_FIELDS = [
    ("title", "Title"),
    ("artist", "Artist"),
    ("album", "Album"),
    ("genre", "Genre"),
    ("year", "Year"),
    ("track", "Track #"),
]


class _MBSignals(QObject):
    done = Signal(list)
    error = Signal(str)


class _MBWorker(QRunnable):
    """Looks up tag candidates on MusicBrainz off the UI thread."""

    def __init__(self, artist: str, title: str) -> None:
        super().__init__()
        self.artist = artist
        self.title = title
        self.signals = _MBSignals()

    def run(self) -> None:
        try:
            results = enrich.search_recordings(self.artist, self.title)
        except Exception as exc:
            self.signals.error.emit(str(exc))
            return
        self.signals.done.emit(results)


class MetadataDialog(QDialog):
    """Edit the embedded tags of one downloaded file."""

    saved = Signal(str)   # new/unchanged path (tags only, name unchanged)

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self._candidates: list[dict] = []
        self.setWindowTitle("Edit metadata")
        self.setModal(True)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QLabel(os.path.basename(path))
        header.setObjectName("pageTitle")
        header.setStyleSheet("font-size: 16px; font-weight: 700;")
        header.setWordWrap(True)
        root.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        self.edits: dict[str, QLineEdit] = {}
        existing = metadata_mod.read_tags(path)
        for key, label in _FIELDS:
            edit = QLineEdit(existing.get(key, ""))
            self.edits[key] = edit
            form.addRow(QLabel(label), edit)
        root.addLayout(form)

        # MusicBrainz auto-fill row.
        mb_row = QHBoxLayout()
        self.mb_btn = QPushButton("  Fetch from MusicBrainz")
        self.mb_btn.setIcon(theme.icon("fa5s.cloud-download-alt", theme.TEXT))
        self.mb_btn.clicked.connect(self._fetch_musicbrainz)
        mb_row.addWidget(self.mb_btn)
        self.mb_combo = QComboBox()
        self.mb_combo.setVisible(False)
        self.mb_combo.activated.connect(self._apply_candidate)
        mb_row.addWidget(self.mb_combo, 1)
        root.addLayout(mb_row)

        self.mb_status = QLabel("")
        self.mb_status.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        self.mb_status.setWordWrap(True)
        root.addWidget(self.mb_status)

        # Save / Cancel.
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("  Save tags")
        save.setObjectName("primary")
        save.setIcon(theme.icon("fa5s.save", "white"))
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)

    # -- MusicBrainz -------------------------------------------------------
    def _fetch_musicbrainz(self) -> None:
        title = self.edits["title"].text().strip()
        artist = self.edits["artist"].text().strip()
        if not title:
            self.mb_status.setText("Enter at least a title to search MusicBrainz.")
            return
        self.mb_btn.setEnabled(False)
        self.mb_status.setText("Searching MusicBrainz…")
        worker = _MBWorker(artist, title)
        worker.signals.done.connect(self._on_mb_results)
        worker.signals.error.connect(self._on_mb_error)
        QThreadPool.globalInstance().start(worker)

    def _on_mb_results(self, results: list) -> None:
        self.mb_btn.setEnabled(True)
        self._candidates = results
        self.mb_combo.clear()
        if not results:
            self.mb_combo.setVisible(False)
            self.mb_status.setText("No MusicBrainz matches found.")
            return
        for c in results:
            bits = [c.get("artist", ""), c.get("title", ""), c.get("album", ""), c.get("year", "")]
            label = " — ".join(b for b in bits if b)
            self.mb_combo.addItem(label or "(untitled)")
        self.mb_combo.setVisible(True)
        self.mb_status.setText("Pick a match to fill the fields above.")
        self._apply_candidate(0)

    def _on_mb_error(self, message: str) -> None:
        self.mb_btn.setEnabled(True)
        self.mb_combo.setVisible(False)
        self.mb_status.setText(f"MusicBrainz lookup failed: {message}")

    def _apply_candidate(self, index: int) -> None:
        if 0 <= index < len(self._candidates):
            c = self._candidates[index]
            for key in ("title", "artist", "album", "year", "track"):
                value = c.get(key, "")
                if value:
                    self.edits[key].setText(str(value))

    # -- save --------------------------------------------------------------
    def _save(self) -> None:
        fields = {key: edit.text() for key, edit in self.edits.items()}
        try:
            metadata_mod.write_tags(self.path, fields)
        except Exception as exc:
            QMessageBox.warning(self, "Could not save tags", str(exc))
            return
        self.saved.emit(self.path)
        self.accept()
