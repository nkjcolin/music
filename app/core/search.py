"""Background YouTube search using yt-dlp's ``ytsearch`` provider."""

from __future__ import annotations

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal


def _fmt_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class SearchSignals(QObject):
    results = Signal(str, list)   # query, list[dict]
    error = Signal(str, str)      # query, message


class SearchWorker(QRunnable):
    """Runs ``ytsearchN:<query>`` off the UI thread and emits flat results."""

    def __init__(self, query: str, limit: int = 12) -> None:
        super().__init__()
        self.query = query
        self.limit = max(1, int(limit))
        self.signals = SearchSignals()

    def run(self) -> None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "default_search": "ytsearch",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{self.limit}:{self.query}", download=False)
        except Exception as exc:
            self.signals.error.emit(self.query, str(exc))
            return

        results = []
        for entry in (info or {}).get("entries", []) or []:
            if not entry:
                continue
            url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
            if url and not str(url).startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"
            results.append({
                "title": entry.get("title") or "Untitled",
                "uploader": entry.get("uploader") or entry.get("channel") or "",
                "duration": _fmt_duration(entry.get("duration")),
                "url": url,
                "id": entry.get("id") or "",
            })
        self.signals.results.emit(self.query, results)
