# Songtify

A modern desktop downloader built on **PySide6** and **yt-dlp**. Grab audio or video
from YouTube (and the many other sites yt-dlp supports), embed metadata and lyrics, and
keep a concurrent download queue running while you add more.

![format: mp3 / mp4](https://img.shields.io/badge/output-MP3%20%7C%20MP4-7c5cff)

## Features

- 🎵 **Audio (MP3)** with selectable bitrate (128–320 kbps)
- 🎬 **Video (MP4)** with a resolution picker (Best / 1080p / 720p / 480p)
- ⚡ **Concurrent queue** — download several items at once (configurable), keep adding while they run
- 📃 **Playlists** are expanded automatically into individual queue items
- ✏️ **Editable filename per item** — defaults to *Artist - Track*, falls back to the video title
- 🏷️ **Full metadata + cover art** embedded (title, artist, album, year, genre, square thumbnail)
- 🎤 **Lyrics** via `syncedlyrics` — synced `.lrc` sidecar when available, plus embedded plain text
- 🌙 Clean, dynamic dark UI with sidebar navigation
- 🔁 Per-item **cancel** and **retry**, with partial-file cleanup

## Project layout

```
main.py                 # entry point
app/
  core/
    downloader.py        # yt-dlp worker (QRunnable)
    queue_manager.py     # QThreadPool queue + playlist expansion
    metadata.py          # mutagen tags + cover art
    lyrics.py            # syncedlyrics fetch -> .lrc / embedded
    naming.py            # name resolution + sanitization
    settings.py          # QSettings persistence
    paths.py             # resource/ffmpeg/icon path resolution
  ui/
    main_window.py       # sidebar nav + Download/Queue/Settings pages
    queue_widget.py      # queue rows (progress, rename, cancel/retry)
    theme.py             # dark QSS + icon helpers
assets/youtube_music.ico
ffmpeg.exe               # bundled FFmpeg (required for audio/merge)
music.spec               # PyInstaller build spec
```

## Run from source

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

> `ffmpeg.exe` ships in the repo root and is used automatically. If you remove it,
> install FFmpeg and make sure it is on your `PATH`.

## Build a Windows .exe

```bash
pip install pyinstaller
pyinstaller music.spec
```

The single-file executable is written to `dist/Songtify.exe`. `ffmpeg.exe` and the
icon are bundled inside it.

## Updating yt-dlp

yt-dlp changes often as sites update. If downloads start failing, refresh it:

```bash
pip install -U yt-dlp
```

## Notes

This tool is for **personal use** with content you are authorized to download.
Downloading copyrighted material may violate the source site's Terms of Service —
respect content licenses and local law.
