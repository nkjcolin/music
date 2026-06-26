"""yt-dlp download worker and the per-item data model."""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal

from . import lyrics as lyrics_mod
from . import metadata as metadata_mod
from .archive import Archive, archive_key
from .naming import build_outtmpl
from .paths import ffmpeg_dir, ffmpeg_path
from .settings import CODEC_EXT

# SponsorBlock categories removed when the user enables it (YouTube only).
_SPONSOR_CATS = ["sponsor", "intro", "outro", "selfpromo", "preview", "music_offtopic"]


@dataclass
class DownloadOptions:
    """User-chosen options that apply to a download."""

    folder: str
    fmt: str = "audio"          # "audio" | "video"
    bitrate: str = "192"        # kbps, audio only
    resolution: str = "Best"    # "Best" | "1080" | "720" | "480", video only
    codec: str = "mp3"          # "mp3" | "m4a" | "opus" | "flac" | "wav", audio only
    template: str = "{name}"    # output filename/sub-folder template
    ratelimit_kbps: int = 0     # download speed cap in KB/s, 0 = unlimited
    use_archive: bool = True    # skip tracks already recorded in the archive
    archive_path: str | None = None
    fetch_lyrics: bool = True
    embed_metadata: bool = True
    embed_thumbnail: bool = True   # embed the thumbnail as cover art
    cookies_browser: str = ""      # read cookies from this browser ("" = none)
    sponsorblock: bool = False     # remove sponsor/intro/outro segments
    embed_subs: bool = False       # embed subtitles (video)
    embed_chapters: bool = False   # embed chapters (video)

    @property
    def audio_ext(self) -> str:
        return CODEC_EXT.get(self.codec, ".mp3")


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

    def to_dict(self) -> dict:
        """Serialise for the persisted queue (omits the runtime cancel event)."""
        return {
            "url": self.url,
            "name": self.name,
            "id": self.id,
            "status": self.status,
            "filepath": self.filepath,
            "options": asdict(self.options),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DownloadItem:
        opts_data = dict(data.get("options") or {})
        # Drop unknown keys so older/newer saved queues still load.
        valid = {f.name for f in fields(DownloadOptions)}
        opts = DownloadOptions(**{k: v for k, v in opts_data.items() if k in valid})
        return cls(
            url=data["url"],
            options=opts,
            name=data.get("name", ""),
            id=data.get("id") or uuid.uuid4().hex,
            status=data.get("status", "Pending"),
            filepath=data.get("filepath"),
        )


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

    def _build_opts(self, outtmpl: str, use_cookies: bool = True, subs_mode: str = "all") -> dict:
        o = self.item.options
        opts: dict = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
        }
        # Point at the directory so yt-dlp finds BOTH ffmpeg and ffprobe
        # (ffprobe is required for subtitle/chapter post-processing).
        ff = ffmpeg_dir() or ffmpeg_path()
        if ff:
            opts["ffmpeg_location"] = ff
        if o.ratelimit_kbps and o.ratelimit_kbps > 0:
            opts["ratelimit"] = o.ratelimit_kbps * 1024
        if use_cookies and o.cookies_browser:
            # yt-dlp reads cookies directly from the browser's profile.
            opts["cookiesfrombrowser"] = (o.cookies_browser,)

        pps: list[dict] = []
        if o.fmt == "audio":
            opts["format"] = "bestaudio/best"
            extract = {"key": "FFmpegExtractAudio", "preferredcodec": o.codec}
            # Lossless/uncompressed codecs ignore a bitrate target.
            if o.codec not in ("flac", "wav"):
                extract["preferredquality"] = o.bitrate
            pps.append(extract)
        else:
            res = self.item.options.resolution
            hf = f"[height<={res}]" if res and res != "Best" else ""
            # Prefer H.264 (avc1) video + AAC (mp4a) audio: the codecs every
            # editor/player supports. Avoids AV1 (av01) / VP9 / Opus, which apps
            # like Premiere can't open. Falls back to mp4, then anything.
            opts["format"] = (
                f"bestvideo[vcodec^=avc1]{hf}+bestaudio[acodec^=mp4a]/"
                f"bestvideo[vcodec^=avc1]{hf}+bestaudio/"
                f"best[vcodec^=avc1]{hf}/"
                f"bestvideo[ext=mp4]{hf}+bestaudio[ext=m4a]/"
                f"best[ext=mp4]{hf}/best{hf}/best"
            )
            # Safety net: bias selection toward h264/aac if the string falls through.
            opts["format_sort"] = ["vcodec:h264", "acodec:aac"]
            opts["merge_output_format"] = "mp4"
            if o.embed_subs and subs_mode != "none":
                # Grab every available subtitle / closed-caption track.
                opts["writesubtitles"] = True
                opts["subtitleslangs"] = ["all"]
                # Auto-generated (and auto-translated) captions are what trip
                # HTTP 429 — include them in "all" mode, drop them in "manual".
                opts["writeautomaticsub"] = subs_mode == "all"
                pps.append({"key": "FFmpegEmbedSubtitle"})
            if o.embed_chapters:
                pps.append({"key": "FFmpegMetadata", "add_chapters": True})

        if o.sponsorblock:
            # Fetch segments (early) then cut them out of the media (YouTube only).
            pps.insert(0, {"key": "SponsorBlock", "categories": _SPONSOR_CATS,
                           "when": "after_filter"})
            pps.append({"key": "ModifyChapters", "remove_sponsor_segments": list(_SPONSOR_CATS)})

        if pps:
            opts["postprocessors"] = pps
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
            cand = os.path.splitext(base)[0] + self.item.options.audio_ext
            if os.path.exists(cand):
                return cand
        else:
            cand = os.path.splitext(base)[0] + ".mp4"
            if os.path.exists(cand):
                return cand
        return base

    def _download(self, ydl: yt_dlp.YoutubeDL, probe: dict | None) -> dict | None:
        """Download the media, reusing probe metadata to avoid re-extraction.

        When the duplicate check already extracted the metadata, hand it
        straight to yt-dlp's downloader. Falls back to a fresh extraction if
        that path produces nothing.
        """
        if probe is not None:
            try:
                info = self._unwrap(ydl.process_ie_result(probe, download=True))
                if info is not None:
                    return info
            except Exception:
                pass  # fall through to a clean extraction
        return self._unwrap(ydl.extract_info(self.item.url, download=True))

    @staticmethod
    def _unwrap(info: dict | None) -> dict | None:
        """Unwrap a ``ytsearchN:`` / playlist results wrapper to a single entry."""
        if info and info.get("entries"):
            entries = [e for e in info["entries"] if e]
            return entries[0] if entries else info
        return info

    def _expected_path(self, ydl: yt_dlp.YoutubeDL, info: dict) -> str | None:
        """Predict the output file path for ``info`` under the current template."""
        try:
            base = ydl.prepare_filename(info)
        except Exception:
            return None
        stem = os.path.splitext(base)[0]
        ext = self.item.options.audio_ext if self.item.options.fmt == "audio" else ".mp4"
        return stem + ext

    def _already_present(self, ydl: yt_dlp.YoutubeDL, info: dict, archive: Archive) -> str | None:
        """Return the existing file for this track, or ``None`` if absent.

        Checks the duplicate index first (pruning stale entries), then falls back
        to a direct existence check of the predicted output path so files added
        outside the index are still recognised.
        """
        key = archive_key(info)
        existing = archive.valid_path(key)
        if not existing:
            predicted = self._expected_path(ydl, info)
            if predicted and os.path.exists(predicted):
                existing = predicted
        if existing:
            archive.record(key, existing)
        return existing

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

    @staticmethod
    def _is_cookie_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "cookie" in msg or "could not copy" in msg or "unable to open" in msg

    @staticmethod
    def _is_subtitle_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        # Subtitle download (429) or its ffprobe-based post-processing.
        return "subtitle" in msg or "ffprobe" in msg or "video duration" in msg

    def _extract(self, outtmpl: str, archive, name: str, use_cookies: bool, subs_mode: str):
        """Probe (for dedup) and download. Returns ('skip', path) or ('ok', info, final)."""
        opts = self._build_opts(outtmpl, use_cookies=use_cookies, subs_mode=subs_mode)
        with yt_dlp.YoutubeDL(opts) as ydl:
            probe = None
            if archive is not None:
                self.signals.status.emit(self.item.id, "Checking")
                probe = self._unwrap(ydl.extract_info(self.item.url, download=False))
                if self.item.cancel_event.is_set():
                    raise _Cancelled()
                if probe:
                    existing = self._already_present(ydl, probe, archive)
                    if existing:
                        return ("skip", existing)

            self.signals.status.emit(self.item.id, "Downloading")
            info = self._download(ydl, probe)
            if info is None:
                raise RuntimeError("no media returned")
            final = self._final_path(info, ydl)
        return ("ok", info, final)

    # -- entry point -------------------------------------------------------
    def run(self) -> None:
        item = self.item
        if item.cancel_event.is_set():
            self.signals.status.emit(item.id, "Cancelled")
            return

        item.started = True
        name = item.name or "download"
        outtmpl = build_outtmpl(item.options.folder, item.options.template, item.name)

        o = item.options
        archive = Archive(o.archive_path) if (o.use_archive and o.archive_path) else None

        try:
            # Try the full download, then degrade gracefully: a bad cookie
            # source or a rate-limited (HTTP 429) subtitle fetch must never block
            # the actual media — drop that feature and retry.
            use_cookies = True
            # Subtitles degrade: all (manual + auto) -> manual only -> none.
            subs_mode = "all" if o.embed_subs else "none"
            while True:
                try:
                    result = self._extract(outtmpl, archive, name, use_cookies, subs_mode)
                    break
                except _Cancelled:
                    raise
                except Exception as exc:
                    if use_cookies and o.cookies_browser and self._is_cookie_error(exc):
                        use_cookies = False
                        self.signals.log.emit(f"[{name}] cookies unavailable, retrying without them…")
                        continue
                    if subs_mode != "none" and self._is_subtitle_error(exc):
                        if subs_mode == "all":
                            subs_mode = "manual"
                            self.signals.log.emit(
                                f"[{name}] auto captions rate-limited, retrying with manual subtitles only…")
                        else:
                            subs_mode = "none"
                            self.signals.log.emit(
                                f"[{name}] subtitles unavailable, retrying without them…")
                        continue
                    raise

            if result[0] == "skip":
                existing = result[1]
                item.filepath = existing
                item.status = "Skipped"
                self.signals.status.emit(item.id, "Skipped")
                self.signals.finished.emit(item.id, existing)
                self.signals.log.emit(f"Already in folder, skipped: {name}")
                return

            _, info, final = result

            if item.cancel_event.is_set():
                raise _Cancelled()

            if not final or not os.path.exists(final):
                item.status = "Error"
                self.signals.error.emit(item.id, "Download produced no output file.")
                return

            if archive is not None:
                archive.record(archive_key(info), final)

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
                    # Dropping the thumbnail makes the embedder skip cover art.
                    tag_info = info if o.embed_thumbnail else {**info, "thumbnail": None}
                    metadata_mod.embed(final, tag_info, plain_lyrics)
                except Exception as exc:  # non-fatal
                    self.signals.log.emit(f"[{name}] metadata skipped: {exc}")

            item.filepath = final
            item.status = "Done"
            self.signals.status.emit(item.id, "Done")
            self.signals.finished.emit(item.id, final)
            self.signals.log.emit(f"Completed: {os.path.basename(final)}")

        except _Cancelled:
            self._cleanup_partials(outtmpl.replace(".%(ext)s", ""))
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
