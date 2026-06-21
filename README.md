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
- 🎤 **Lyrics** via `syncedlyrics` — synced `.lrc` (kept in a tidy `Lyrics/` sub-folder) plus on-demand fetch from the player
- 🎧 **Built-in player** — play your downloads with **time-synced lyrics** (karaoke highlight), a real queue (**auto-advance, next/prev, shuffle, repeat**), and a **persistent mini-player** across all pages
- 📚 **Library** — browse downloads with **search, sort, cover thumbnails, tag editing, rename, delete** and multi-select
- 🕘 **History** — every completed download, with open-location and one-click **re-download**
- 🎛️ **Advanced download** — quality **presets**, **SponsorBlock** segment removal, **cookies-from-browser** (age-restricted/private), embed **subtitles/chapters** for video
- 🔔 **Desktop notifications** + system tray when downloads finish
- 🚫 **Folder-aware duplicate detection** — skips a track only if its file is still on disk (re-downloads if you deleted it)
- 🐢 **Bandwidth limit** · 🗂️ **separate music & video folders** · 🔄 **one-click yt-dlp update**
- 🌙 Clean, dynamic dark UI with sidebar navigation
- 🔁 Per-item **cancel / retry / reorder / remove**, with partial-file cleanup

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
    archive.py           # folder-aware duplicate index
    history.py           # persistent download history
    lrc.py               # .lrc parsing + Lyrics/ sub-folder paths
    logsetup.py          # rotating file log + uncaught-exception hook
  ui/
    main_window.py       # sidebar nav: Download/Queue/Library/Player/History/Settings
    search_widget.py     # search results list (click to queue)
    queue_widget.py      # queue rows (progress, rename, reorder, remove, retry)
    library_widget.py    # library rows (play, rename, tags, delete; search/sort)
    player_widget.py     # audio player with synced lyrics + playback queue
    history_widget.py    # download history rows (re-download / open)
    metadata_dialog.py   # tag editor + MusicBrainz auto-fill
    theme.py             # dark QSS + icon helpers
assets/youtube_music.ico
ffmpeg.exe               # bundled FFmpeg (required for audio/merge)
music.spec               # PyInstaller build spec (one-file)
music_onedir.spec        # PyInstaller build spec (one-folder, fast startup)
tests/                   # pytest suite for the core logic
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

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # app deps + pytest + ruff
pytest                                 # run the test suite
ruff check .                           # lint
```

CI (GitHub Actions) runs ruff + pytest on every push and pull request.

## Build a Windows .exe

```bash
pip install pyinstaller
pyinstaller music.spec          # one file  -> dist/Songtify.exe
# or, for instant startup:
pyinstaller music_onedir.spec   # one folder -> dist/Songtify/ (ship the folder)
```

The **one-file** build is a single `dist/Songtify.exe` with `ffmpeg.exe` and the
icon bundled inside — convenient, but it extracts ffmpeg to a temp dir on each
launch, so startup is a little slow. The **one-folder** build starts instantly;
distribute the whole `dist/Songtify/` folder.

## Updating yt-dlp

yt-dlp changes often as sites update. If downloads start failing, refresh it:

```bash
pip install -U yt-dlp
```

## Notes

This tool is for **personal use** with content you are authorized to download.
Downloading copyrighted material may violate the source site's Terms of Service —
respect content licenses and local law.
