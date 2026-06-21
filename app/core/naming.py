"""Helpers for deriving a clean display name / filename from yt-dlp info."""

import re

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAILING = re.compile(r"[ .]+$")


def sanitize_filename(name: str, fallback: str = "download") -> str:
    """Strip characters that are illegal in Windows filenames."""
    name = _ILLEGAL.sub("_", name or "")
    name = _TRAILING.sub("", name).strip()
    # collapse runs of whitespace/underscores
    name = re.sub(r"\s+", " ", name)
    return name[:180] if name else fallback


def display_name_from_info(info: dict) -> str:
    """Resolve a human name from a yt-dlp info dict.

    Prefers ``"Artist - Track"`` when music metadata is available, otherwise the
    video title, falling back to any available identifier.
    """
    track = (info.get("track") or "").strip()
    artist = (info.get("artist") or info.get("creator") or info.get("uploader") or "").strip()

    if track and artist:
        return f"{artist} - {track}"
    if track:
        return track

    title = (info.get("title") or "").strip()
    if title:
        return title

    return info.get("id") or "download"
