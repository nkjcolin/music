"""The download queue page: a scrollable list of per-item rows."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme


class QueueRow(QFrame):
    """A single download row with an editable name, progress and controls."""

    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    rename_requested = Signal(str, str)

    def __init__(self, item_id: str, name: str, fmt: str) -> None:
        super().__init__()
        self.item_id = item_id
        self.setObjectName("queueRow")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        badge = QLabel()
        badge.setPixmap(theme.icon(
            "fa5s.music" if fmt == "audio" else "fa5s.film", theme.ACCENT
        ).pixmap(18, 18))
        top.addWidget(badge)

        self.name_edit = QLineEdit(name)
        self.name_edit.setToolTip("Edit the file name before the download starts")
        self.name_edit.editingFinished.connect(
            lambda: self.rename_requested.emit(self.item_id, self.name_edit.text())
        )
        top.addWidget(self.name_edit, 1)

        self.status_label = QLabel("Pending")
        self.status_label.setMinimumWidth(110)
        self.status_label.setAlignment(Qt.AlignCenter)
        self._set_status_style("Pending")
        top.addWidget(self.status_label)

        self.open_btn = self._mini("fa5s.folder-open", "Open file location")
        self.open_btn.clicked.connect(self._open_location)
        self.open_btn.setVisible(False)
        top.addWidget(self.open_btn)

        self.retry_btn = self._mini("fa5s.redo", "Retry")
        self.retry_btn.clicked.connect(lambda: self.retry_requested.emit(self.item_id))
        self.retry_btn.setVisible(False)
        top.addWidget(self.retry_btn)

        self.cancel_btn = self._mini("fa5s.times", "Cancel")
        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.item_id))
        top.addWidget(self.cancel_btn)

        outer.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        bottom.addWidget(self.progress, 1)
        self.detail = QLabel("")
        self.detail.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        self.detail.setMinimumWidth(140)
        self.detail.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.detail)
        outer.addLayout(bottom)

        self.filepath: str | None = None

    def _mini(self, icon_name: str, tip: str) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(theme.icon(icon_name, theme.TEXT_DIM))
        btn.setToolTip(tip)
        btn.setFixedSize(34, 34)
        return btn

    def _set_status_style(self, status: str) -> None:
        color = theme.STATUS_COLORS.get(status, theme.TEXT_DIM)
        self.status_label.setStyleSheet(
            f"color: {color}; font-weight: 600; font-size: 12px;"
        )

    # -- updates from manager ---------------------------------------------
    def set_progress(self, pct: float, speed: str, eta: str) -> None:
        self.progress.setValue(int(pct))
        parts = [p for p in (speed, f"ETA {eta}" if eta else "") if p]
        self.detail.setText("  ".join(parts))

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        self._set_status_style(status)

        active = status in (
            "Downloading", "Processing", "Fetching lyrics", "Tagging", "Pending", "Queued", "Checking"
        )
        self.name_edit.setReadOnly(status not in ("Pending", "Queued"))
        self.cancel_btn.setVisible(active)
        self.retry_btn.setVisible(status in ("Error", "Cancelled", "Skipped"))
        if status == "Done":
            self.progress.setValue(100)
            self.detail.setText("")
            self.open_btn.setVisible(True)
        elif status == "Skipped":
            self.detail.setText("Already downloaded")
        elif status in ("Error", "Cancelled"):
            self.detail.setText(status)

    def set_finished(self, filepath: str) -> None:
        self.filepath = filepath
        self.open_btn.setVisible(True)

    def _open_location(self) -> None:
        if not self.filepath or not os.path.exists(self.filepath):
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self.filepath)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self.filepath])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(self.filepath)])


class QueueWidget(QWidget):
    """Scrollable container that holds and looks up ``QueueRow`` widgets."""

    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    rename_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[str, QueueRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.empty = QLabel("Your queue is empty.\nAdd a URL from the Download page to get started.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 14px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(2, 2, 2, 2)
        self._vbox.setSpacing(10)
        self._vbox.addWidget(self.empty)
        self._vbox.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def add_item(self, item) -> None:
        self.empty.setVisible(False)
        row = QueueRow(item.id, item.name, item.options.fmt)
        row.cancel_requested.connect(self.cancel_requested)
        row.retry_requested.connect(self.retry_requested)
        row.rename_requested.connect(self.rename_requested)
        self.rows[item.id] = row
        # insert before the trailing stretch
        self._vbox.insertWidget(self._vbox.count() - 1, row)

    def on_progress(self, item_id: str, pct: float, speed: str, eta: str) -> None:
        row = self.rows.get(item_id)
        if row:
            row.set_progress(pct, speed, eta)

    def on_status(self, item_id: str, status: str) -> None:
        row = self.rows.get(item_id)
        if row:
            row.set_status(status)

    def on_finished(self, item_id: str, filepath: str) -> None:
        row = self.rows.get(item_id)
        if row:
            row.set_finished(filepath)

    def on_error(self, item_id: str, message: str) -> None:
        row = self.rows.get(item_id)
        if row:
            row.set_status("Error")
            row.detail.setText(message[:60])
