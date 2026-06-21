"""Search results list for the Download page (YouTube search)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme


class SearchResultRow(QFrame):
    """One search hit. Clicking anywhere on the row queues it."""

    add_requested = Signal(str, str)   # url, name

    def __init__(self, result: dict) -> None:
        super().__init__()
        self.setObjectName("clickableRow")
        self._url = result.get("url") or ""
        self._name = result.get("title") or "Untitled"
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to add to the download queue")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        badge = QLabel()
        badge.setPixmap(theme.icon("fa5s.music", theme.ACCENT).pixmap(18, 18))
        lay.addWidget(badge)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(self._name)
        title.setStyleSheet("font-weight: 600;")
        title.setWordWrap(False)
        meta_bits = [b for b in (result.get("uploader"), result.get("duration")) if b]
        meta = QLabel("  •  ".join(meta_bits))
        meta.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        text.addWidget(title)
        text.addWidget(meta)
        lay.addLayout(text, 1)

        hint = QLabel()
        hint.setPixmap(theme.icon("fa5s.plus-circle", theme.ACCENT).pixmap(18, 18))
        lay.addWidget(hint)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._url:
            self.add_requested.emit(self._url, self._name)
        super().mousePressEvent(event)


class SearchWidget(QWidget):
    """Scrollable list of search results with a status line."""

    add_requested = Signal(str, str)   # url, name

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status = QLabel("Search for a song to see results here.")
        self.status.setStyleSheet(f"color: {theme.TEXT_DIM};")
        layout.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(2, 2, 2, 2)
        self._vbox.setSpacing(8)
        self._vbox.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def _clear(self) -> None:
        for i in reversed(range(self._vbox.count())):
            w = self._vbox.itemAt(i).widget()
            if isinstance(w, SearchResultRow):
                self._vbox.takeAt(i)
                w.deleteLater()

    def set_loading(self, query: str) -> None:
        self._clear()
        self.status.setText(f"Searching for “{query}”…")

    def set_message(self, message: str) -> None:
        self._clear()
        self.status.setText(message)

    def notify(self, message: str) -> None:
        """Update the status line without clearing the results (e.g. after adding)."""
        self.status.setText(message)

    def set_results(self, query: str, results: list[dict]) -> None:
        self._clear()
        if not results:
            self.status.setText(f"No results for “{query}”.")
            return
        self.status.setText(f"{len(results)} result(s) for “{query}” — pick one to queue.")
        for result in results:
            row = SearchResultRow(result)
            row.add_requested.connect(self.add_requested)
            self._vbox.insertWidget(self._vbox.count() - 1, row)
