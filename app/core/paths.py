"""Resource path resolution that works both from source and a PyInstaller bundle."""

import os
import sys


def resource_path(filename: str) -> str:
    """Return an absolute path to a bundled resource.

    When frozen by PyInstaller the data files live in ``sys._MEIPASS``; otherwise
    they live next to the project root.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    # project root is two levels up from this file (app/core/paths.py)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, filename)


def ffmpeg_path() -> str | None:
    """Return the path to the bundled ffmpeg binary, or ``None`` to use PATH."""
    candidate = resource_path("ffmpeg.exe")
    return candidate if os.path.exists(candidate) else None


def ffprobe_path() -> str | None:
    """Return the path to the bundled ffprobe binary, or ``None`` to use PATH."""
    candidate = resource_path("ffprobe.exe")
    return candidate if os.path.exists(candidate) else None


def ffmpeg_dir() -> str | None:
    """Directory holding ffmpeg/ffprobe — what yt-dlp's ``ffmpeg_location`` wants.

    Passing the directory lets yt-dlp find **both** ffmpeg and ffprobe (the
    latter is needed for subtitle/chapter post-processing).
    """
    ff = ffmpeg_path()
    return os.path.dirname(ff) if ff else None


def icon_path() -> str:
    """Return the path to the application icon, checking bundle and assets dir."""
    for name in ("youtube_music.ico", os.path.join("assets", "youtube_music.ico")):
        candidate = resource_path(name)
        if os.path.exists(candidate):
            return candidate
    return resource_path("youtube_music.ico")
