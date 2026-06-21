"""Folder-aware duplicate tracking.

Unlike yt-dlp's plain download-archive (which records a track id forever and
blindly skips it), this index maps each track to the file it produced and only
counts it as a duplicate while that file still exists. If the user deletes the
file from the folder, the entry is pruned and the track downloads again.
"""

from __future__ import annotations

import json
import os
import threading

# A single process-wide lock keeps concurrent download workers from clobbering
# the index file during their read-modify-write updates.
_LOCK = threading.Lock()


def archive_key(info: dict) -> str:
    """Stable identity for a track from yt-dlp info (extractor + video id)."""
    extractor = (
        info.get("extractor_key")
        or info.get("extractor")
        or info.get("ie_key")
        or ""
    ).lower()
    vid = str(info.get("id") or "")
    if extractor and vid:
        return f"{extractor} {vid}"
    return info.get("webpage_url") or info.get("original_url") or vid


class Archive:
    """A JSON ``{key: filepath}`` index validated against the filesystem."""

    def __init__(self, path: str) -> None:
        self.path = path

    def _load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, self.path)
        except OSError:
            pass  # best-effort; never break a download over the index

    def valid_path(self, key: str) -> str | None:
        """Return the recorded file for ``key`` if it still exists, else ``None``.

        A recorded-but-missing file (manually deleted) is pruned so the track
        will be downloaded again.
        """
        if not key:
            return None
        with _LOCK:
            data = self._load()
            path = data.get(key)
            if path and os.path.exists(path):
                return path
            if key in data:
                del data[key]
                self._save(data)
            return None

    def record(self, key: str, path: str) -> None:
        """Remember that ``key`` produced ``path``."""
        if not key or not path:
            return
        with _LOCK:
            data = self._load()
            if data.get(key) == path:
                return
            data[key] = path
            self._save(data)
