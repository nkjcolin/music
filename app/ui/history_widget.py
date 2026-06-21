"""The History page: past downloads with open-location and re-download."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import history as history_mod
from . import theme


def _when(ts) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError):
        return ""


class HistoryRow(QFrame):
    """One past download with open-location and re-download actions."""

    redownload_requested = Signal(str, str)   # url, name

    def __init__(self, entry: dict) -> None:
        super().__init__()
        self.setObjectName("queueRow")
        self.entry = entry

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        badge = QLabel()
        badge.setPixmap(theme.icon(
            "fa5s.film" if entry.get("fmt") == "video" else "fa5s.music", theme.ACCENT
        ).pixmap(18, 18))
        lay.addWidget(badge)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel(entry.get("name") or os.path.basename(entry.get("path", "")))
        title.setStyleSheet("font-weight: 600;")
        meta = QLabel("  •  ".join(b for b in (entry.get("fmt", ""), _when(entry.get("time"))) if b))
        meta.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        text.addWidget(title)
        text.addWidget(meta)
        lay.addLayout(text, 1)

        redl = QPushButton("  Re-download")
        redl.setIcon(theme.icon("fa5s.redo", theme.TEXT))
        redl.setToolTip("Add this back to the queue with your current options")
        redl.clicked.connect(lambda: self.redownload_requested.emit(
            entry.get("url", ""), entry.get("name", "")))
        redl.setEnabled(bool(entry.get("url")))
        lay.addWidget(redl)

        open_btn = QPushButton()
        open_btn.setIcon(theme.icon("fa5s.folder-open", theme.TEXT_DIM))
        open_btn.setToolTip("Open file location")
        open_btn.setFixedSize(34, 34)
        open_btn.setEnabled(bool(entry.get("path")) and os.path.exists(entry.get("path", "")))
        open_btn.clicked.connect(self._open_location)
        lay.addWidget(open_btn)

    def _open_location(self) -> None:
        path = self.entry.get("path", "")
        if not path or not os.path.exists(path):
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])


class HistoryWidget(QWidget):
    """Lists previously-downloaded items with re-download and clear."""

    redownload_requested = Signal(str, str)   # url, name

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[HistoryRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        bar.addStretch(1)
        clear_btn = QPushButton("  Clear history")
        clear_btn.setIcon(theme.icon("fa5s.trash", theme.TEXT))
        clear_btn.clicked.connect(self._clear)
        bar.addWidget(clear_btn)
        refresh = QPushButton("  Refresh")
        refresh.setIcon(theme.icon("fa5s.sync", theme.TEXT))
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        self.empty = QLabel("No downloads yet. Completed downloads will appear here.")
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
        for row in self._rows:
            self._vbox.removeWidget(row)
            row.deleteLater()
        self._rows = []
        entries = history_mod.load()
        self.empty.setVisible(not entries)
        for entry in entries:
            row = HistoryRow(entry)
            row.redownload_requested.connect(self.redownload_requested)
            self._rows.append(row)
            self._vbox.insertWidget(self._vbox.count() - 1, row)

    def _clear(self) -> None:
        if QMessageBox.question(self, "Clear history", "Clear the download history?") != QMessageBox.Yes:
            return
        history_mod.clear()
        self.refresh()
