"""Persistent download history (separate from the live queue)."""

from __future__ import annotations

import json
import os
import time

_MAX = 500


def history_path() -> str:
    """Path to the history file.

    Imported lazily from :mod:`settings` so this module (and its tests) don't
    pull in PySide6 just to resolve a path.
    """
    from .settings import history_path as _resolve
    return _resolve()


def _load_raw(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def load() -> list[dict]:
    """Return history entries, most recent first."""
    return _load_raw(history_path())


def add_entry(name: str, path: str, url: str, fmt: str) -> None:
    """Record a completed download. De-duplicates by output path."""
    entries = _load_raw(history_path())
    entries = [e for e in entries if e.get("path") != path]
    entries.insert(0, {
        "name": name,
        "path": path,
        "url": url,
        "fmt": fmt,
        "time": time.time(),
    })
    del entries[_MAX:]
    _save(entries)


def clear() -> None:
    _save([])


def _save(entries: list) -> None:
    path = history_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entries, fh)
        os.replace(tmp, path)
    except OSError:
        pass
