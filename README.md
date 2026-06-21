# Songtify

A modern desktop downloader built on **PySide6** and **yt-dlp**. Grab audio or video
from YouTube (and the many other sites yt-dlp supports), embed metadata and lyrics, and
keep a concurrent download queue running while you add more.

![format: mp3 / mp4](https://img.shields.io/badge/output-MP3%20%7C%20MP4-7c5cff)

## Features

- 🔎 **Search & download** — find a song by name right in the app; no link needed. Pasting a URL still works as a fallback.
- 🔗 **Streaming links** — paste a **Spotify / Apple Music / Deezer** track, album or playlist link and Songtify resolves each track and grabs it from YouTube (no API keys required).
- 🎵 **Audio** in **MP3 / M4A / Opus / FLAC / WAV** with selectable bitrate (128–320 kbps for lossy)
- 🎬 **Video (MP4)** with a resolution picker (Best / 1080p / 720p / 480p)
- ⚡ **Concurrent queue** — download several items at once (configurable), **pause/resume** the whole queue, keep adding while they run
- 💾 **Persistent queue** — unfinished items return after you restart the app
- 🗂️ **Filename templates** — organise output with tokens and sub-folders, e.g. `{artist}/{album}/{track}`
- 🚫 **Duplicate detection** — skip tracks you've already downloaded (yt-dlp download archive)
- 🐢 **Bandwidth limit** — cap download speed for metered connections
- 📋 **Clipboard auto-detect** & **drag-and-drop** — drop a link on the window or copy one to queue it fast
- 📃 **Playlists** are expanded automatically into individual queue items
- ✏️ **Editable filename per item** — defaults to *Artist - Track*, falls back to the video title
- 🏷️ **Full metadata + cover art** embedded (title, artist, album, year, genre, square thumbnail)
- 🎚️ **In-app tag editor** with **MusicBrainz** auto-fill for clean, canonical tags
- 🎤 **Lyrics** via `syncedlyrics` — synced `.lrc` sidecar when available, plus embedded plain text
- 🔄 **One-click yt-dlp update** so downloads keep working as sites change
- 🌙 Clean, dynamic dark UI with sidebar navigation
- 🔁 Per-item **cancel** and **retry**, with partial-file cleanup

## Project layout

```
main.py                 # entry point
app/
  core/
    downloader.py        # yt-dlp worker (QRunnable): codecs, rate limit, archive
    queue_manager.py     # QThreadPool queue: resolve, pause/resume, persistence
    resolvers.py         # Spotify / Apple Music / Deezer link -> YouTube searches
    search.py            # ytsearch worker (search & download)
    enrich.py            # MusicBrainz tag lookup
    updater.py           # one-click yt-dlp update worker
    metadata.py          # mutagen tags + cover art (mp3/m4a/flac/opus) + tag I/O
    lyrics.py            # syncedlyrics fetch -> .lrc / embedded
    naming.py            # name resolution, sanitization, filename templates
    settings.py          # QSettings persistence + app-data paths
    library.py           # list/rename downloaded files
    paths.py             # resource/ffmpeg/icon path resolution
  ui/
    main_window.py       # sidebar nav + Download/Queue/Library/Settings pages
    search_widget.py     # search results list
    queue_widget.py      # queue rows (progress, rename, cancel/retry)
    library_widget.py    # library rows (rename, edit tags)
    metadata_dialog.py   # tag editor + MusicBrainz auto-fill
    theme.py             # dark QSS + icon helpers
assets/youtube_music.ico
ffmpeg.exe               # bundled FFmpeg (required for audio/merge)
music.spec               # PyInstaller build spec
```

## Filename templates

The **Settings → Filename template** field controls how files are named and
foldered. The default is `{name}` (the editable *Artist - Track* name). Use `/`
to create sub-folders. Available tokens:

`{name}` `{title}` `{track}` `{artist}` `{album}` `{year}` `{playlist}` `{index}`

Example: `{artist}/{album}/{index} - {track}` →
`Daft Punk/Discovery/01 - One More Time.mp3`

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
