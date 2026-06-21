"""Lyrics fetching via ``syncedlyrics`` with synced-LRC and plain-text fallback."""

import os
import re

try:
    import syncedlyrics
except Exception:  # pragma: no cover - optional at runtime
    syncedlyrics = None

_LRC_TIMESTAMP = re.compile(r"^\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]", re.MULTILINE)


def _strip_lrc_timestamps(lrc: str) -> str:
    """Convert an LRC string into plain lyric lines (timestamps removed)."""
    lines = []
    for line in lrc.splitlines():
        text = _LRC_TIMESTAMP.sub("", line).strip()
        # drop metadata tags like [ar:...], [ti:...]
        if text.startswith("[") and text.endswith("]"):
            continue
        lines.append(text)
    return "\n".join(lines).strip()


def fetch_lyrics(artist: str, track: str) -> tuple[str | None, str | None]:
    """Return ``(synced_lrc, plain_text)``; either element may be ``None``.

    Tries to find time-synced lyrics first; if found, also derives plain text from
    them. If no synced lyrics exist, attempts a plain-text search.
    """
    if syncedlyrics is None:
        return None, None

    query = " ".join(p for p in (artist, track) if p).strip()
    if not query:
        return None, None

    synced = None
    plain = None
    try:
        synced = syncedlyrics.search(query)  # synced by default
    except Exception:
        synced = None

    if synced and _LRC_TIMESTAMP.search(synced):
        plain = _strip_lrc_timestamps(synced)
        return synced, plain

    # No synced result with timestamps — try a plain search.
    try:
        plain = syncedlyrics.search(query, plain_only=True)
    except TypeError:
        # older/newer signature differences — fall back to whatever we got
        plain = synced or None
    except Exception:
        plain = None

    if plain:
        plain = _strip_lrc_timestamps(plain) if _LRC_TIMESTAMP.search(plain) else plain.strip()

    return (synced if synced and _LRC_TIMESTAMP.search(synced) else None), (plain or None)


def write_lrc_sidecar(media_path: str, lrc: str) -> str | None:
    """Write an ``.lrc`` file next to ``media_path``. Returns the path or None."""
    if not lrc:
        return None
    base, _ = os.path.splitext(media_path)
    lrc_path = base + ".lrc"
    try:
        with open(lrc_path, "w", encoding="utf-8") as fh:
            fh.write(lrc)
        return lrc_path
    except Exception:
        return None
