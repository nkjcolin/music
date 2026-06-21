"""Concurrent download queue built on ``QThreadPool``.

Adds, resolves and dispatches downloads, supports pausing/resuming the queue,
and persists pending items so they survive an app restart. Plain links and
playlists are expanded with yt-dlp; Spotify/Apple/Deezer links are resolved to
YouTube search queries via :mod:`app.core.resolvers`.
"""

from __future__ import annotations

import json
import os

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from . import resolvers
from .downloader import DownloadItem, DownloadOptions, DownloadWorker
from .naming import display_name_from_info
from .settings import queue_state_path

# Statuses that represent finished work (not re-dispatched, not persisted).
_TERMINAL = ("Done", "Skipped")


class _PrepareSignals(QObject):
    resolved = Signal(str, list)   # original_url, list[dict(url, name)]
    info = Signal(str)             # human-readable note
    error = Signal(str, str)       # original_url, message


class _PrepareWorker(QRunnable):
    """Turns one input URL into a list of ``{url, name}`` entries to download.

    Streaming links become ``ytsearch1:`` queries; plain links and playlists are
    flat-extracted with yt-dlp so this stays fast even for large playlists.
    """

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = _PrepareSignals()

    def run(self) -> None:
        # 1) Streaming services (Spotify / Apple Music / Deezer).
        try:
            streaming = resolvers.resolve(self.url)
        except Exception as exc:
            self.signals.error.emit(self.url, f"streaming lookup failed: {exc}")
            return
        if streaming is not None:
            if not streaming.tracks:
                self.signals.error.emit(self.url, "no tracks found at that link")
                return
            entries = [
                {"url": f"ytsearch1:{t.query}", "name": t.name}
                for t in streaming.tracks
            ]
            self.signals.info.emit(
                f"{streaming.source.title()} '{streaming.title}': {len(entries)} track(s) added."
            )
            self.signals.resolved.emit(self.url, entries)
            return

        # 2) Plain yt-dlp URL (single video, playlist, or other supported site).
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
            self.signals.info.emit(f"Playlist detected: {len(entries)} items added.")
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
    paused_changed = Signal(bool)

    def __init__(self, concurrency: int = 3) -> None:
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max(1, concurrency))
        self.items: dict[str, DownloadItem] = {}
        self._workers: list[QRunnable] = []
        self.paused = False

    def set_concurrency(self, n: int) -> None:
        self.pool.setMaxThreadCount(max(1, int(n)))

    # -- adding ------------------------------------------------------------
    def add_url(self, url: str, options: DownloadOptions) -> None:
        """Resolve a link (streaming/playlist/single) and queue its tracks."""
        url = url.strip()
        if not url:
            return
        self.log.emit(f"Resolving: {url}")
        worker = _PrepareWorker(url)
        worker.signals.resolved.connect(lambda u, entries: self._on_resolved(entries, options))
        worker.signals.info.connect(self.log)
        worker.signals.error.connect(lambda u, msg: self.log.emit(f"Could not resolve {u}: {msg}"))
        self._workers.append(worker)
        self.pool.start(worker)

    def add_resolved(self, url: str, name: str, options: DownloadOptions) -> None:
        """Queue a single already-known item (e.g. a chosen search result)."""
        item = DownloadItem(url=url, options=options, name=name)
        self.items[item.id] = item
        self.item_added.emit(item)
        self._dispatch(item)
        self._save()

    def _on_resolved(self, entries: list[dict], options: DownloadOptions) -> None:
        for entry in entries:
            item = DownloadItem(url=entry["url"], options=options, name=entry["name"])
            self.items[item.id] = item
            self.item_added.emit(item)
            self._dispatch(item)
        self._save()

    def _dispatch(self, item: DownloadItem) -> None:
        if self.paused:
            item.status = "Queued"
            self.item_status.emit(item.id, "Queued")
            return
        worker = DownloadWorker(item)
        worker.signals.progress.connect(self.item_progress)
        worker.signals.status.connect(self._on_status)
        worker.signals.finished.connect(self.item_finished)
        worker.signals.error.connect(self._on_error)
        worker.signals.log.connect(self.log)
        self.pool.start(worker)

    def _on_status(self, item_id: str, status: str) -> None:
        if item_id in self.items:
            self.items[item_id].status = status
        self.item_status.emit(item_id, status)
        if status in _TERMINAL:
            self._save()

    def _on_error(self, item_id: str, message: str) -> None:
        if item_id in self.items:
            self.items[item_id].status = "Error"
        self.item_error.emit(item_id, message)
        self._save()

    # -- pause / resume ----------------------------------------------------
    def pause(self) -> None:
        if self.paused:
            return
        self.paused = True
        self.paused_changed.emit(True)
        self.log.emit("Queue paused — running downloads finish; new ones wait.")

    def resume(self) -> None:
        if not self.paused:
            return
        self.paused = False
        self.paused_changed.emit(False)
        self.log.emit("Queue resumed.")
        for item in list(self.items.values()):
            if item.status == "Queued":
                item.cancel_event.clear()
                self._dispatch(item)

    def toggle_pause(self) -> None:
        self.resume() if self.paused else self.pause()

    # -- controls ----------------------------------------------------------
    def cancel(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if item:
            item.cancel_event.set()
            # A queued (not-yet-started) item won't see the event, so mark it now.
            if item.status == "Queued":
                item.status = "Cancelled"
                self.item_status.emit(item_id, "Cancelled")
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
            self._save()

    def remove(self, item_id: str) -> None:
        item = self.items.get(item_id)
        if item:
            item.cancel_event.set()   # stop it if it happens to be running
        self.items.pop(item_id, None)
        self._save()

    def clear_all(self) -> None:
        for item in self.items.values():
            item.cancel_event.set()
        self.items.clear()
        self._save()

    def move(self, item_id: str, delta: int) -> None:
        """Reorder a not-yet-started item; affects dispatch order on resume."""
        ids = list(self.items.keys())
        if item_id not in ids:
            return
        i = ids.index(item_id)
        j = i + delta
        if j < 0 or j >= len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        self.items = {k: self.items[k] for k in ids}
        self._save()

    # -- persistence -------------------------------------------------------
    def save(self) -> None:
        """Public entry point to persist the queue (e.g. on window close)."""
        self._save()

    def _save(self) -> None:
        """Write pending/unfinished items to disk so they survive a restart."""
        try:
            keep = [
                it.to_dict() for it in self.items.values()
                if it.status not in _TERMINAL
            ]
            path = queue_state_path()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"items": keep}, fh)
            os.replace(tmp, path)
        except Exception:
            pass  # persistence is best-effort and must never break a download

    def load_state(self) -> int:
        """Restore previously-saved items and resume them. Returns the count."""
        path = queue_state_path()
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return 0

        count = 0
        for raw in data.get("items", []):
            try:
                item = DownloadItem.from_dict(raw)
            except Exception:
                continue
            # Reset transient states so they actually run again on resume.
            if item.status not in ("Error", "Cancelled"):
                item.status = "Pending"
            self.items[item.id] = item
            self.item_added.emit(item)
            if item.status == "Pending":
                self._dispatch(item)
            else:
                self.item_status.emit(item.id, item.status)
            count += 1
        if count:
            self.log.emit(f"Restored {count} item(s) from your last session.")
        return count
