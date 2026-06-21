"""Helpers for deriving a clean display name / filename from yt-dlp info."""

import os
import re

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAILING = re.compile(r"[ .]+$")

# Map our friendly ``{token}`` placeholders to yt-dlp output-template fields.
# yt-dlp expands these from the real metadata at download time, so they stay
# correct even though we only know the editable display name up front.
_TEMPLATE_TOKENS = {
    "title": "%(title)s",
    "track": "%(track,title)s",
    "artist": "%(artist,creator,uploader)s",
    "album": "%(album,playlist_title|Unknown Album)s",
    "uploader": "%(uploader)s",
    "playlist": "%(playlist,playlist_title|Singles)s",
    "index": "%(playlist_index)02d",
    "year": "%(release_year,upload_date>%Y|)s",
}

# Placeholders the user may put in a template (shown in the Settings hint).
TEMPLATE_HELP = "{name} {title} {track} {artist} {album} {year} {playlist} {index}"

_TOKEN_RE = re.compile(r"\{([a-z_]+)\}")


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


def _to_ytdlp_template(template: str, name: str) -> str:
    """Translate a ``{token}`` template into a yt-dlp output template.

    ``{name}`` is replaced with the (sanitized) editable display name; every
    other recognised token maps to a yt-dlp field that yt-dlp fills in later.
    Unknown tokens and literal text are passed through (with ``%`` escaped so
    yt-dlp does not treat it as a field).
    """
    safe_name = sanitize_filename(name) if name else "download"

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key == "name":
            return safe_name.replace("%", "%%")
        return _TEMPLATE_TOKENS.get(key, match.group(0).replace("%", "%%"))

    # Escape stray percent signs in the literal portions, then substitute tokens.
    parts = []
    last = 0
    for m in _TOKEN_RE.finditer(template):
        parts.append(template[last:m.start()].replace("%", "%%"))
        parts.append(repl(m))
        last = m.end()
    parts.append(template[last:].replace("%", "%%"))
    return "".join(parts)


def build_outtmpl(folder: str, template: str, name: str) -> str:
    """Return a yt-dlp ``outtmpl`` path under ``folder`` for this item.

    The default template ``{name}`` reproduces the original behaviour (a single
    file named after the editable display name). Templates may contain ``/`` to
    create sub-folders (e.g. ``{artist}/{album}/{track}``).
    """
    rendered = _to_ytdlp_template(template or "{name}", name)
    rendered = rendered.replace("\\", "/").strip("/") or "download"
    return os.path.join(folder, rendered + ".%(ext)s")
