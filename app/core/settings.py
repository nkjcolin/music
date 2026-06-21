"""Persistent application settings backed by ``QSettings``."""

import os

from PySide6.QtCore import QSettings, QStandardPaths

ORG = "songtify"
APP = "Songtify"

# Setting keys
KEY_FOLDER = "download/folder"
KEY_CONCURRENCY = "queue/concurrency"
KEY_FORMAT = "download/format"          # "audio" | "video"
KEY_BITRATE = "download/bitrate"        # str kbps
KEY_RESOLUTION = "download/resolution"  # "Best" | "1080" | "720" | "480"
KEY_FETCH_LYRICS = "features/lyrics"
KEY_EMBED_METADATA = "features/metadata"

DEFAULT_CONCURRENCY = 3
BITRATES = ["128", "192", "256", "320"]
RESOLUTIONS = ["Best", "1080", "720", "480"]


def _default_folder() -> str:
    music = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
    if music and os.path.isdir(music):
        return music
    return QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or os.getcwd()


class AppSettings:
    """Thin typed wrapper around ``QSettings`` for the values this app cares about."""

    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    # --- download folder ---
    @property
    def folder(self) -> str:
        return self._s.value(KEY_FOLDER, _default_folder(), type=str)

    @folder.setter
    def folder(self, value: str) -> None:
        self._s.setValue(KEY_FOLDER, value)

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
