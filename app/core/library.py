"""List and rename downloaded media files (and their lyric sidecars)."""

from __future__ import annotations

import os

from .naming import sanitize_filename

MEDIA_EXTS = (".mp3", ".mp4", ".m4a", ".m4v")


def list_media(folder: str) -> list[dict]:
    """Return media files in ``folder`` sorted by most-recently-modified first."""
    if not folder or not os.path.isdir(folder):
        return []
    items = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(name)
        if ext.lower() not in MEDIA_EXTS:
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        items.append({
            "path": path,
            "stem": stem,
            "ext": ext,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
    items.sort(key=lambda d: d["mtime"], reverse=True)
    return items


def rename_media(old_path: str, new_stem: str) -> str:
    """Rename a media file to ``new_stem`` (keeping its extension).

    Also renames a matching ``.lrc`` sidecar when present. Returns the new path.
    Raises ``ValueError`` for an empty/invalid name and ``FileExistsError`` for a
    collision with a different file.
    """
    folder, old_name = os.path.split(old_path)
    old_stem, ext = os.path.splitext(old_name)

    clean = sanitize_filename(new_stem, fallback="")
    if not clean:
        raise ValueError("Please enter a valid file name.")
    if clean == old_stem:
        return old_path

    new_path = os.path.join(folder, clean + ext)
    if os.path.exists(new_path):
        raise FileExistsError(f"A file named '{clean}{ext}' already exists.")

    os.rename(old_path, new_path)

    old_lrc = os.path.join(folder, old_stem + ".lrc")
    if os.path.exists(old_lrc):
        new_lrc = os.path.join(folder, clean + ".lrc")
        if not os.path.exists(new_lrc):
            try:
                os.rename(old_lrc, new_lrc)
            except OSError:
                pass

    return new_path
