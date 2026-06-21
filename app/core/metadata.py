"""Embed tags, cover art and lyrics into downloaded media using mutagen."""

import io
import os

import requests

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TRCK,
    USLT,
    ID3NoHeaderError,
)
from mutagen.mp4 import MP4, MP4Cover


def _fetch_square_cover(thumbnail_url: str) -> bytes | None:
    """Download a thumbnail and center-crop it to a square JPEG."""
    if not thumbnail_url:
        return None
    try:
        resp = requests.get(thumbnail_url, timeout=15)
        resp.raise_for_status()
        data = resp.content
    except Exception:
        return None

    if Image is None:
        return data  # embed as-is if Pillow unavailable

    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return data


def _year(info: dict) -> str | None:
    date = info.get("release_year") or info.get("upload_date")
    if not date:
        return None
    date = str(date)
    return date[:4] if len(date) >= 4 else date


def embed_mp3(path: str, info: dict, plain_lyrics: str | None = None) -> None:
    """Write ID3 tags, cover art and lyrics to an MP3 file."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    title = info.get("track") or info.get("title")
    artist = info.get("artist") or info.get("creator") or info.get("uploader")
    album = info.get("album")
    genre = info.get("genre")
    track_no = info.get("track_number")
    year = _year(info)

    if title:
        tags.setall("TIT2", [TIT2(encoding=3, text=str(title))])
    if artist:
        tags.setall("TPE1", [TPE1(encoding=3, text=str(artist))])
    if album:
        tags.setall("TALB", [TALB(encoding=3, text=str(album))])
    if genre:
        tags.setall("TCON", [TCON(encoding=3, text=str(genre))])
    if track_no:
        tags.setall("TRCK", [TRCK(encoding=3, text=str(track_no))])
    if year:
        tags.setall("TDRC", [TDRC(encoding=3, text=str(year))])

    cover = _fetch_square_cover(info.get("thumbnail"))
    if cover:
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))

    if plain_lyrics:
        tags.delall("USLT")
        tags.add(USLT(encoding=3, lang="eng", desc="", text=plain_lyrics))
        tags.add(COMM(encoding=3, lang="eng", desc="", text=plain_lyrics))

    tags.save(path, v2_version=3)


def embed_mp4(path: str, info: dict, plain_lyrics: str | None = None) -> None:
    """Write metadata atoms and cover art to an MP4/M4A file."""
    mp4 = MP4(path)

    title = info.get("track") or info.get("title")
    artist = info.get("artist") or info.get("creator") or info.get("uploader")
    album = info.get("album")
    genre = info.get("genre")
    year = _year(info)

    if title:
        mp4["\xa9nam"] = [str(title)]
    if artist:
        mp4["\xa9ART"] = [str(artist)]
    if album:
        mp4["\xa9alb"] = [str(album)]
    if genre:
        mp4["\xa9gen"] = [str(genre)]
    if year:
        mp4["\xa9day"] = [str(year)]
    if plain_lyrics:
        mp4["\xa9lyr"] = [plain_lyrics]

    cover = _fetch_square_cover(info.get("thumbnail"))
    if cover:
        mp4["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]

    mp4.save()


def embed(path: str, info: dict, plain_lyrics: str | None = None) -> None:
    """Dispatch to the right embedder based on file extension. Non-fatal."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".mp3":
        embed_mp3(path, info, plain_lyrics)
    elif ext in (".mp4", ".m4a", ".m4v"):
        embed_mp4(path, info, plain_lyrics)
