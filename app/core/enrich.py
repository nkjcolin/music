"""Look up canonical track tags from the MusicBrainz public API.

Used by the metadata editor's "Fetch from MusicBrainz" button. No API key is
needed, but MusicBrainz requires a descriptive User-Agent and rate-limits to
roughly one request per second, which is fine for interactive use.
"""

from __future__ import annotations

import requests

_ENDPOINT = "https://musicbrainz.org/ws/2/recording"
_UA = "Songtify/1.0 (https://github.com; personal music tagger)"
_TIMEOUT = 15


def _artist_credit(recording: dict) -> str:
    parts = []
    for credit in recording.get("artist-credit", []) or []:
        if isinstance(credit, dict):
            name = credit.get("name") or (credit.get("artist") or {}).get("name")
            if name:
                parts.append(name)
            if credit.get("joinphrase"):
                parts.append(credit["joinphrase"])
    return "".join(parts).strip()


def _best_release(recording: dict) -> dict:
    releases = recording.get("releases") or []
    if not releases:
        return {}
    # Prefer official albums over singles/compilations when we can tell.
    for rel in releases:
        group = rel.get("release-group") or {}
        if group.get("primary-type") == "Album":
            return rel
    return releases[0]


def search_recordings(artist: str, title: str, limit: int = 8) -> list[dict]:
    """Return tag candidates for ``artist``/``title`` ordered by match score.

    Each candidate is a dict with ``title``, ``artist``, ``album``, ``year`` and
    ``track`` keys (any may be an empty string). Raises on a network error.
    """
    title = (title or "").strip()
    if not title:
        return []

    query_parts = [f'recording:"{title}"']
    if artist and artist.strip():
        query_parts.append(f'artist:"{artist.strip()}"')
    params = {"query": " AND ".join(query_parts), "fmt": "json", "limit": int(limit)}

    resp = requests.get(_ENDPOINT, params=params, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    candidates: list[dict] = []
    for rec in data.get("recordings", []) or []:
        release = _best_release(rec)
        date = release.get("date", "") or ""
        track_no = ""
        for medium in release.get("media", []) or []:
            for track in medium.get("track", []) or []:
                track_no = str(track.get("number", "")) or track_no
                break
            if track_no:
                break
        candidates.append({
            "title": rec.get("title", "") or "",
            "artist": _artist_credit(rec),
            "album": release.get("title", "") or "",
            "year": date[:4] if date else "",
            "track": track_no,
        })
    return candidates
