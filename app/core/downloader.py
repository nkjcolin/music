"""yt-dlp download worker and the per-item data model."""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass, field

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal

from . import lyrics as lyrics_mod
from . import metadata as metadata_mod
from .naming import sanitize_filename
from .paths import ffmpeg_path


@dataclass
class DownloadOptions:
    """User-chosen options that apply to a download."""

    folder: str
    fmt: str = "audio"          # "audio" | "video"
    bitrate: str = "192"        # kbps, audio only
    resolution: str = "Best"    # "Best" | "1080" | "720" | "480", video only
    fetch_lyrics: bool = True
    embed_metadata: bool = True


@dataclass
class DownloadItem:
    """A single queued download. ``name`` is editable from the UI before it starts."""

    url: str
    options: DownloadOptions
    name: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "Pending"
    filepath: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started: bool = False


class WorkerSignals(QObject):
    progress = Signal(str, float, str, str)   # id, percent, speed, eta
    status = Signal(str, str)                  # id, status text
    log = Signal(str)                          # message
    finished = Signal(str, str)                # id, filepath
    error = Signal(str, str)                   # id, message


class _Cancelled(Exception):
    pass


class DownloadWorker(QRunnable):
    """Downloads one ``DownloadItem`` on a thread-pool thread."""

    def __init__(self, item: DownloadItem) -> None:
        super().__init__()
        self.item = item
        self.signals = WorkerSignals()

    # -- helpers -----------------------------------------------------------
    def _progress_hook(self, d: dict) -> None:
        if self.item.cancel_event.is_set():
            raise _Cancelled()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = (downloaded / total * 100.0) if total else 0.0
            speed = d.get("_speed_str") or ""
            eta = d.get("_eta_str") or ""
            self.signals.progress.emit(self.item.id, pct, speed.strip(), eta.strip())
        elif d.get("status") == "finished":
            self.signals.status.emit(self.item.id, "Processing")

    def _build_opts(self, outtmpl: str) -> dict:
        opts: dict = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
        }
        ff = ffmpeg_path()
        if ff:
            opts["ffmpeg_location"] = ff

        if self.item.options.fmt == "audio":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": self.item.options.bitrate,
            }]
        else:
            res = self.item.options.resolution
            if res and res != "Best":
                opts["format"] = (
                    f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={res}]+bestaudio/best[height<={res}]/best"
                )
            else:
                opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            opts["merge_output_format"] = "mp4"
        return opts

    def _final_path(self, info: dict, ydl: yt_dlp.YoutubeDL) -> str:
        """Resolve the path of the produced file after post-processing."""
        # Prefer the post-processed file path recorded by yt-dlp.
        rds = info.get("requested_downloads") or []
        if rds:
            fp = rds[0].get("filepath")
            if fp and os.path.exists(fp):
                return fp
        base = ydl.prepare_filename(info)
        if self.item.options.fmt == "audio":
            cand = os.path.splitext(base)[0] + ".mp3"
            if os.path.exists(cand):
                return cand
        else:
            cand = os.path.splitext(base)[0] + ".mp4"
            if os.path.exists(cand):
                return cand
        return base

    def _cleanup_partials(self, stem: str) -> None:
        folder = self.item.options.folder
        if not os.path.isdir(folder):
            return
        prefix = os.path.basename(stem)
        for name in os.listdir(folder):
            if name.startswith(prefix) and name.endswith((".part", ".ytdl", ".webm", ".m4a", ".temp")):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass

    # -- entry point -------------------------------------------------------
    def run(self) -> None:
        item = self.item
        if item.cancel_event.is_set():
            self.signals.status.emit(item.id, "Cancelled")
            return

        item.started = True
        name = sanitize_filename(item.name) if item.name else "download"
        outtmpl = os.path.join(item.options.folder, name + ".%(ext)s")

        try:
            self.signals.status.emit(item.id, "Downloading")
            opts = self._build_opts(outtmpl)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(item.url, download=True)
                final = self._final_path(info, ydl)

            if item.cancel_event.is_set():
                raise _Cancelled()

            plain_lyrics = None
            if item.options.fmt == "audio" and item.options.fetch_lyrics:
                self.signals.status.emit(item.id, "Fetching lyrics")
                try:
                    artist = info.get("artist") or info.get("uploader") or ""
                    track = info.get("track") or info.get("title") or ""
                    synced, plain_lyrics = lyrics_mod.fetch_lyrics(artist, track)
                    if synced:
                        lyrics_mod.write_lrc_sidecar(final, synced)
                except Exception as exc:  # non-fatal
                    self.signals.log.emit(f"[{name}] lyrics skipped: {exc}")

            if item.options.embed_metadata:
                self.signals.status.emit(item.id, "Tagging")
                try:
                    metadata_mod.embed(final, info, plain_lyrics)
                except Exception as exc:  # non-fatal
                    self.signals.log.emit(f"[{name}] metadata skipped: {exc}")

            item.filepath = final
            item.status = "Done"
            self.signals.status.emit(item.id, "Done")
            self.signals.finished.emit(item.id, final)
            self.signals.log.emit(f"Completed: {os.path.basename(final)}")

        except _Cancelled:
            self._cleanup_partials(os.path.join(item.options.folder, name))
            item.status = "Cancelled"
            self.signals.status.emit(item.id, "Cancelled")
            self.signals.log.emit(f"Cancelled: {name}")
        except Exception as exc:
            msg = str(exc)
            if "Cancelled" in msg or isinstance(exc, _Cancelled):
                item.status = "Cancelled"
                self.signals.status.emit(item.id, "Cancelled")
            else:
                item.status = "Error"
                self.signals.error.emit(item.id, msg)
                self.signals.log.emit(f"Error [{name}]: {msg}")
