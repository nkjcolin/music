"""Concurrent download queue built on ``QThreadPool``."""

from __future__ import annotations

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .downloader import DownloadItem, DownloadOptions, DownloadWorker
from .naming import display_name_from_info


class _ExtractSignals(QObject):
    resolved = Signal(str, list)   # original_url, list[dict(url, name)]
    error = Signal(str, str)       # original_url, message


class _ExtractWorker(QRunnable):
    """Resolves a URL (single video or playlist) into one or more entries.

    Uses a flat extraction so this stays fast even for large playlists; full
    metadata is fetched later by each ``DownloadWorker``.
    """

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = _ExtractSignals()

    def run(self) -> None:
        opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
        except Exception as exc:
            self.signals.error.emit(self.url, str(exc))
            return

        entries = []
        if info.get("entries"):
            for entry in info["entries"]:
                if not entry:
                    continue
                url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
                if url and not str(url).startswith("http"):
                    url = f"https://www.youtube.com/watch?v={url}"
                entries.append({"url": url, "name": display_name_from_info(entry)})
        else:
            entries.append({
                "url": info.get("webpage_url") or self.url,
                "name": display_name_from_info(info),
            })
        self.signals.resolved.emit(self.url, entries)


class QueueManager(QObject):
    """Owns the download items and dispatches them to a bounded thread pool."""

    item_added = Signal(object)               # DownloadItem
    item_progress = Signal(str, float, str, str)
    item_status = Signal(str, str)
    item_finished = Signal(str, str)
    item_error = Signal(str, str)
    log = Signal(str)

    def __init__(self, concurrency: int = 3) -> None:
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max(1, concurrency))
        self.items: dict[str, DownloadItem] = {}
        self._extractors: list[_ExtractWorker] = []

    def set_concurrency(self, n: int) -> None:
        self.pool.setMaxThreadCount(max(1, int(n)))

    # -- adding ------------------------------------------------------------
    def add_url(self, url: str, options: DownloadOptions) -> None:
        url = url.strip()
        if not url:
            return
        self.log.emit(f"Resolving: {url}")
        worker = _ExtractWorker(url)
        worker.signals.resolved.connect(lambda u, entries: self._on_resolved(entries, options))
        worker.signals.error.connect(lambda u, msg: self.log.emit(f"Could not resolve {u}: {msg}"))
        self._extractors.append(worker)
        self.pool.start(worker)

    def _on_resolved(self, entries: list[dict], options: DownloadOptions) -> None:
        if len(entries) > 1:
            self.log.emit(f"Playlist detected: {len(entries)} items added.")
        for entry in entries:
            item = DownloadItem(url=entry["url"], options=options, name=entry["name"])
            self.items[item.id] = item
            self.item_added.emit(item)
            self._dispatch(item)

    def _dispatch(self, item: DownloadItem) -> None:
        worker = DownloadWorker(item)
        worker.signals.progress.connect(self.item_progress)
        worker.signals.status.connect(self._on_status)
        worker.signals.finished.connect(self.item_finished)
        worker.signals.error.connect(self.item_error)
        worker.signals.log.connect(self.log)
        self.pool.start(worker)

    def _on_status(self, item_id: str, status: str) -> None:
        if item_id in self.items:
            self.items[item_id].status = status
        self.item_status.emit(item_id, status)

    # -- controls ----------------------------------------------------------
    def cancel(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if item:
            item.cancel_event.set()
            self.log.emit(f"Cancelling: {item.name}")

    def retry(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if not item or item.status in ("Downloading", "Pending", "Processing"):
            return
        item.cancel_event.clear()
        item.status = "Pending"
        item.started = False
        item.filepath = None
        self.item_status.emit(item_id, "Pending")
        self._dispatch(item)

    def rename(self, item_id: str, new_name: str) -> None:
        item = self.items.get(item_id)
        if item and not item.started:
            item.name = new_name
