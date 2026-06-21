"""Parse ``.lrc`` lyric files into timed lines for the in-app player."""

from __future__ import annotations

import os
import re

# Matches one timestamp like [01:23.45] or [1:23] or [01:23.456].
_STAMP = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")

# Lyrics are kept in a sub-folder to keep the download folder tidy.
LYRICS_DIRNAME = "Lyrics"


def sidecar_path(media_path: str) -> str:
    """Canonical ``.lrc`` location for a media file: a ``Lyrics`` sub-folder."""
    folder, name = os.path.split(media_path)
    stem, _ = os.path.splitext(name)
    return os.path.join(folder, LYRICS_DIRNAME, stem + ".lrc")


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """Return ``[(time_ms, line_text), …]`` sorted by time.

    Handles multiple timestamps per line and ignores metadata tags such as
    ``[ar:…]`` / ``[ti:…]`` that carry no timestamp.
    """
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stamps = list(_STAMP.finditer(raw))
        if not stamps:
            continue
        content = raw[stamps[-1].end():].strip()
        for m in stamps:
            minutes = int(m.group(1))
            seconds = int(m.group(2))
            frac = m.group(3) or "0"
            millis = int(frac.ljust(3, "0")[:3])  # 5 -> 500ms, 45 -> 450ms
            lines.append((minutes * 60000 + seconds * 1000 + millis, content))
    lines.sort(key=lambda pair: pair[0])
    return lines


def lrc_path_for(media_path: str) -> str | None:
    """Return an existing ``.lrc`` for a media file, or ``None``.

    Checks the ``Lyrics`` sub-folder first, then falls back to a sibling file
    next to the media (for tracks downloaded before lyrics were foldered).
    """
    candidates = [
        sidecar_path(media_path),
        os.path.splitext(media_path)[0] + ".lrc",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def load_synced(media_path: str) -> list[tuple[int, str]]:
    """Load timed lyrics from a media file's ``.lrc`` sidecar (may be empty)."""
    path = lrc_path_for(media_path)
    if not path:
        return []
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as fh:
                return parse_lrc(fh.read())
        except (UnicodeDecodeError, OSError):
            continue
    return []
