"""Resolve streaming-service links (Spotify / Apple Music / Deezer) into tracks.

These services can't be downloaded from directly, but we can read their public
metadata and turn each track into a YouTube search query that yt-dlp *can*
download. ``resolve(url)`` returns a :class:`ResolveResult` for a recognised
streaming link, or ``None`` when the URL should be handled as a normal yt-dlp
link (YouTube, SoundCloud, a direct file, …).

No API keys are required: Deezer and Apple expose key-free JSON endpoints, and
Spotify links are read from their public embed page.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests

_TIMEOUT = 15
_UA = "Mozilla/5.0 (Songtify; +https://github.com) AppleWebKit/537.36"

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_SPOTIFY_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?(track|album|playlist)/([A-Za-z0-9]+)")
_DEEZER_RE = re.compile(r"deezer\.com/(?:[a-z]{2}/)?(track|album|playlist)/(\d+)")
_APPLE_RE = re.compile(r"music\.apple\.com/[a-z]{2}/(album|playlist|song)/[^/]+/([A-Za-z0-9.]+)")


@dataclass
class Track:
    """A resolved streaming track and the YouTube search query it maps to."""

    name: str           # "Artist - Title" for display / queue rows
    query: str          # plain "Artist Title" search text


@dataclass
class ResolveResult:
    source: str                 # "spotify" | "deezer" | "apple"
    title: str                  # playlist/album/track name (for logging)
    tracks: list[Track] = field(default_factory=list)


def find_first_url(text: str) -> str | None:
    """Return the first http(s) URL contained in ``text`` (clipboard/drop helper)."""
    if not text:
        return None
    m = _URL_RE.search(text.strip())
    return m.group(0) if m else None


def looks_like_url(text: str) -> bool:
    """True if ``text`` is (or contains) something we'd treat as a link."""
    return find_first_url(text) is not None


def collapse_duplicate_url(text: str) -> str:
    """Collapse an accidentally doubled URL (e.g. clipboard fill + manual paste).

    ``https://x/abchttps://x/abc`` -> ``https://x/abc``. Only trims when the two
    halves are identical, so distinct concatenations are left untouched.
    """
    text = (text or "").strip()
    m = re.match(r"(https?://.+?)(https?://.+)$", text)
    if m and m.group(2) == m.group(1):
        return m.group(1)
    return text


def is_streaming_url(url: str) -> bool:
    return bool(_SPOTIFY_RE.search(url) or _DEEZER_RE.search(url) or _APPLE_RE.search(url))


def _track(artist: str, title: str) -> Track:
    artist = (artist or "").strip()
    title = (title or "").strip()
    name = f"{artist} - {title}" if artist and title else (title or artist or "Unknown")
    query = " ".join(p for p in (artist, title) if p) or name
    return Track(name=name, query=query)


# --------------------------------------------------------------------------- #
# Deezer — public JSON API (no key required)
# --------------------------------------------------------------------------- #
def _resolve_deezer(kind: str, id_: str) -> ResolveResult:
    base = f"https://api.deezer.com/{kind}/{id_}"
    data = requests.get(base, headers={"User-Agent": _UA}, timeout=_TIMEOUT).json()
    if data.get("error"):
        raise ValueError(data["error"].get("message", "Deezer lookup failed"))

    tracks: list[Track] = []
    if kind == "track":
        tracks.append(_track(data.get("artist", {}).get("name", ""), data.get("title", "")))
        title = data.get("title", "track")
    else:
        for t in (data.get("tracks") or {}).get("data", []):
            tracks.append(_track(t.get("artist", {}).get("name", ""), t.get("title", "")))
        title = data.get("title", kind)
    return ResolveResult("deezer", title, tracks)


# --------------------------------------------------------------------------- #
# Apple Music — iTunes lookup API (no key required)
# --------------------------------------------------------------------------- #
def _resolve_apple(url: str, kind: str, id_: str) -> ResolveResult:
    # A specific song inside an album appears as ``?i=<trackId>``.
    m = re.search(r"[?&]i=(\d+)", url)
    if m:
        params = {"id": m.group(1), "entity": "song"}
    elif kind == "song":
        params = {"id": id_, "entity": "song"}
    else:  # album
        params = {"id": id_, "entity": "song"}

    resp = requests.get(
        "https://itunes.apple.com/lookup", params=params,
        headers={"User-Agent": _UA}, timeout=_TIMEOUT,
    ).json()
    results = resp.get("results", [])
    if not results:
        raise ValueError("Apple Music lookup returned no tracks")

    tracks: list[Track] = []
    title = kind
    for r in results:
        if r.get("wrapperType") == "collection" or r.get("kind") not in ("song", None):
            title = r.get("collectionName", title)
            if r.get("wrapperType") == "collection":
                continue
        if r.get("kind") == "song" or r.get("trackName"):
            tracks.append(_track(r.get("artistName", ""), r.get("trackName", "")))
    return ResolveResult("apple", title, tracks)


# --------------------------------------------------------------------------- #
# Spotify — read the public embed page (no key required)
# --------------------------------------------------------------------------- #
def _spotify_tracks_from_entity(entity: dict) -> tuple[str, list[Track]]:
    title = entity.get("name") or entity.get("title") or "Spotify"
    track_list = entity.get("trackList") or []
    if track_list:
        tracks = [_track(t.get("subtitle", ""), t.get("title", "")) for t in track_list]
        return title, tracks
    # Single track entity.
    artists = entity.get("artists") or []
    artist = ", ".join(a.get("name", "") for a in artists if a.get("name"))
    if not artist:
        artist = entity.get("subtitle", "")
    return title, [_track(artist, entity.get("name", ""))]


def _resolve_spotify(kind: str, id_: str) -> ResolveResult:
    embed = f"https://open.spotify.com/embed/{kind}/{id_}"
    html = requests.get(embed, headers={"User-Agent": _UA}, timeout=_TIMEOUT).text
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        raise ValueError("Could not read Spotify page (format may have changed)")
    data = json.loads(m.group(1))

    # Walk down to the entity; the exact path has shifted over time, so search.
    entity = _find_entity(data)
    if not entity:
        raise ValueError("No track data found on the Spotify page")
    title, tracks = _spotify_tracks_from_entity(entity)
    return ResolveResult("spotify", title, tracks)


def _find_entity(obj) -> dict | None:
    """Depth-first search for the Spotify entity dict in the embed JSON."""
    if isinstance(obj, dict):
        if obj.get("name") and ("trackList" in obj or "artists" in obj or obj.get("type") == "track"):
            return obj
        for value in obj.values():
            found = _find_entity(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_entity(value)
            if found:
                return found
    return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def resolve(url: str) -> ResolveResult | None:
    """Resolve a streaming URL to tracks, or ``None`` if it isn't one.

    Raises on a recognised-but-failed lookup so the caller can surface the error.
    """
    url = (url or "").strip()

    m = _DEEZER_RE.search(url)
    if m:
        return _resolve_deezer(m.group(1), m.group(2))

    m = _SPOTIFY_RE.search(url)
    if m:
        return _resolve_spotify(m.group(1), m.group(2))

    m = _APPLE_RE.search(url)
    if m:
        return _resolve_apple(url, m.group(1), m.group(2))

    return None
