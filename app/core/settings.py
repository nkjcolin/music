"""Persistent application settings backed by ``QSettings``."""

import os

from PySide6.QtCore import QSettings, QStandardPaths

ORG = "songtify"
APP = "Songtify"

# Setting keys
KEY_FOLDER = "download/folder"              # music / audio downloads
KEY_VIDEO_FOLDER = "download/video_folder"  # video downloads
KEY_CONCURRENCY = "queue/concurrency"
KEY_FORMAT = "download/format"          # "audio" | "video"
KEY_BITRATE = "download/bitrate"        # str kbps
KEY_RESOLUTION = "download/resolution"  # "Best" | "1080" | "720" | "480"
KEY_CODEC = "download/codec"            # "mp3" | "m4a" | "opus" | "flac" | "wav"
KEY_TEMPLATE = "download/template"      # output filename template
KEY_RATELIMIT = "download/ratelimit"    # KB/s, 0 = unlimited
KEY_FETCH_LYRICS = "features/lyrics"
KEY_EMBED_METADATA = "features/metadata"
KEY_CLIPBOARD = "features/clipboard"    # auto-detect links on the clipboard
KEY_ARCHIVE = "features/archive"        # skip already-downloaded tracks
KEY_PLAYER_SHUFFLE = "player/shuffle"   # player shuffle on/off
KEY_PLAYER_REPEAT = "player/repeat"     # "off" | "all" | "one"
KEY_COOKIES = "download/cookies_browser"    # "" = none, else browser name
KEY_SPONSORBLOCK = "download/sponsorblock"  # remove sponsor/intro/outro segments
KEY_EMBED_SUBS = "download/embed_subs"      # embed subtitles into video
KEY_EMBED_CHAPTERS = "download/embed_chapters"  # embed chapters into video
KEY_EMBED_THUMBNAIL = "download/embed_thumbnail"  # use thumbnail as cover art

REPEAT_MODES = ("off", "all", "one")
# Browsers yt-dlp can read cookies from (for age-restricted / private media).
COOKIE_BROWSERS = ["", "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium"]

DEFAULT_CONCURRENCY = 3
BITRATES = ["128", "192", "256", "320"]
RESOLUTIONS = ["Best", "1080", "720", "480"]
CODECS = ["mp3", "m4a", "opus", "flac", "wav"]
DEFAULT_TEMPLATE = "{name}"

# Audio container extension for each selectable codec.
CODEC_EXT = {
    "mp3": ".mp3",
    "m4a": ".m4a",
    "opus": ".opus",
    "flac": ".flac",
    "wav": ".wav",
}


def _default_folder() -> str:
    music = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
    if music and os.path.isdir(music):
        return music
    return QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or os.getcwd()


def _default_video_folder() -> str:
    movies = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
    if movies and os.path.isdir(movies):
        return movies
    return QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or os.getcwd()


def _app_data_dir() -> str:
    """A writable per-user directory for app state (archive, queue cache)."""
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.getcwd()
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return base


def archive_path() -> str:
    """Path to the folder-aware duplicate index (track id -> downloaded file)."""
    return os.path.join(_app_data_dir(), "download-index.json")


def queue_state_path() -> str:
    """Path to the persisted queue (restored on next launch)."""
    return os.path.join(_app_data_dir(), "queue.json")


class AppSettings:
    """Thin typed wrapper around ``QSettings`` for the values this app cares about."""

    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    # --- music (audio) download folder ---
    @property
    def folder(self) -> str:
        return self._s.value(KEY_FOLDER, _default_folder(), type=str)

    @folder.setter
    def folder(self, value: str) -> None:
        self._s.setValue(KEY_FOLDER, value)

    # --- video download folder ---
    @property
    def video_folder(self) -> str:
        return self._s.value(KEY_VIDEO_FOLDER, _default_video_folder(), type=str)

    @video_folder.setter
    def video_folder(self, value: str) -> None:
        self._s.setValue(KEY_VIDEO_FOLDER, value)

    def folder_for(self, fmt: str) -> str:
        """Return the configured destination for an ``audio``/``video`` download."""
        return self.video_folder if fmt == "video" else self.folder

    # --- concurrency ---
    @property
    def concurrency(self) -> int:
        return self._s.value(KEY_CONCURRENCY, DEFAULT_CONCURRENCY, type=int)

    @concurrency.setter
    def concurrency(self, value: int) -> None:
        self._s.setValue(KEY_CONCURRENCY, int(value))

    # --- format ---
    @property
    def format(self) -> str:
        return self._s.value(KEY_FORMAT, "audio", type=str)

    @format.setter
    def format(self, value: str) -> None:
        self._s.setValue(KEY_FORMAT, value)

    # --- bitrate ---
    @property
    def bitrate(self) -> str:
        return self._s.value(KEY_BITRATE, "192", type=str)

    @bitrate.setter
    def bitrate(self, value: str) -> None:
        self._s.setValue(KEY_BITRATE, value)

    # --- resolution ---
    @property
    def resolution(self) -> str:
        return self._s.value(KEY_RESOLUTION, "Best", type=str)

    @resolution.setter
    def resolution(self, value: str) -> None:
        self._s.setValue(KEY_RESOLUTION, value)

    # --- audio codec ---
    @property
    def codec(self) -> str:
        value = self._s.value(KEY_CODEC, "mp3", type=str)
        return value if value in CODECS else "mp3"

    @codec.setter
    def codec(self, value: str) -> None:
        self._s.setValue(KEY_CODEC, value)

    # --- output template ---
    @property
    def template(self) -> str:
        value = self._s.value(KEY_TEMPLATE, DEFAULT_TEMPLATE, type=str)
        return value.strip() or DEFAULT_TEMPLATE

    @template.setter
    def template(self, value: str) -> None:
        self._s.setValue(KEY_TEMPLATE, (value or "").strip() or DEFAULT_TEMPLATE)

    # --- bandwidth limit (KB/s, 0 = unlimited) ---
    @property
    def ratelimit(self) -> int:
        return self._s.value(KEY_RATELIMIT, 0, type=int)

    @ratelimit.setter
    def ratelimit(self, value: int) -> None:
        self._s.setValue(KEY_RATELIMIT, max(0, int(value)))

    # --- feature toggles ---
    @property
    def fetch_lyrics(self) -> bool:
        return self._s.value(KEY_FETCH_LYRICS, True, type=bool)

    @fetch_lyrics.setter
    def fetch_lyrics(self, value: bool) -> None:
        self._s.setValue(KEY_FETCH_LYRICS, bool(value))

    @property
    def embed_metadata(self) -> bool:
        return self._s.value(KEY_EMBED_METADATA, True, type=bool)

    @embed_metadata.setter
    def embed_metadata(self, value: bool) -> None:
        self._s.setValue(KEY_EMBED_METADATA, bool(value))

    @property
    def clipboard_watch(self) -> bool:
        return self._s.value(KEY_CLIPBOARD, False, type=bool)

    @clipboard_watch.setter
    def clipboard_watch(self, value: bool) -> None:
        self._s.setValue(KEY_CLIPBOARD, bool(value))

    @property
    def skip_existing(self) -> bool:
        return self._s.value(KEY_ARCHIVE, True, type=bool)

    @skip_existing.setter
    def skip_existing(self, value: bool) -> None:
        self._s.setValue(KEY_ARCHIVE, bool(value))

    # --- player preferences ---
    @property
    def player_shuffle(self) -> bool:
        return self._s.value(KEY_PLAYER_SHUFFLE, False, type=bool)

    @player_shuffle.setter
    def player_shuffle(self, value: bool) -> None:
        self._s.setValue(KEY_PLAYER_SHUFFLE, bool(value))

    @property
    def player_repeat(self) -> str:
        value = self._s.value(KEY_PLAYER_REPEAT, "off", type=str)
        return value if value in REPEAT_MODES else "off"

    @player_repeat.setter
    def player_repeat(self, value: str) -> None:
        self._s.setValue(KEY_PLAYER_REPEAT, value if value in REPEAT_MODES else "off")

    # --- advanced download options ---
    @property
    def cookies_browser(self) -> str:
        value = self._s.value(KEY_COOKIES, "", type=str)
        return value if value in COOKIE_BROWSERS else ""

    @cookies_browser.setter
    def cookies_browser(self, value: str) -> None:
        self._s.setValue(KEY_COOKIES, value if value in COOKIE_BROWSERS else "")

    @property
    def sponsorblock(self) -> bool:
        return self._s.value(KEY_SPONSORBLOCK, False, type=bool)

    @sponsorblock.setter
    def sponsorblock(self, value: bool) -> None:
        self._s.setValue(KEY_SPONSORBLOCK, bool(value))

    @property
    def embed_subs(self) -> bool:
        return self._s.value(KEY_EMBED_SUBS, False, type=bool)

    @embed_subs.setter
    def embed_subs(self, value: bool) -> None:
        self._s.setValue(KEY_EMBED_SUBS, bool(value))

    @property
    def embed_chapters(self) -> bool:
        return self._s.value(KEY_EMBED_CHAPTERS, False, type=bool)

    @embed_chapters.setter
    def embed_chapters(self, value: bool) -> None:
        self._s.setValue(KEY_EMBED_CHAPTERS, bool(value))

    @property
    def embed_thumbnail(self) -> bool:
        return self._s.value(KEY_EMBED_THUMBNAIL, True, type=bool)

    @embed_thumbnail.setter
    def embed_thumbnail(self, value: bool) -> None:
        self._s.setValue(KEY_EMBED_THUMBNAIL, bool(value))
