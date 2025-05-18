# YouTube MP3 Downloader

A desktop application built with **PyQt5** that allows users to download audio from YouTube videos in **MP3 format** with embedded metadata and thumbnails. This app uses `yt-dlp` for downloading and `ffmpeg` for audio conversion.

---

## Features

- Download MP3 audio from YouTube links
- Choose output bitrate: 128, 192, 256, or 320 kbps
- Select a custom output directory
- Displays real-time download logs
- Cancel download option
- Automatic cleanup of partial downloads
- Embeds metadata and thumbnails in MP3 files

---

## Requirements

- Python 3.7 or newer

### Python packages:

```
pip install PyQt5 yt-dlp psutil
```

Or use the `requirements.txt` file:

```
pip install -r requirements.txt
```

---

## Setup

1. Clone or download this repository.
2. Make sure `ffmpeg.exe` is placed in the same directory as the script.
3. (Optional) Add `youtube_music.ico` in the same directory for a custom app icon.

---

## Running the App

```
python music.py
```

---

## Usage

1. Paste the YouTube URL into the text field.
2. Click **"Choose Folder"** to set the output directory.
3. Select a bitrate from the dropdown (128, 192, 256, or 320 kbps).
4. Click **"Download MP3"** to begin downloading.
5. To stop an in-progress download, click **"Cancel"**.

After a successful download, the log will show:

```
Successfully downloaded: <video title>
Download finished successfully.
```

---

## Optional: Build EXE for Windows

If you want to distribute the app as a `.exe`, use [PyInstaller](https://pyinstaller.org/):

```
pyinstaller --onefile --windowed --add-data "ffmpeg.exe;." --add-data "youtube_music.ico;." music.py
```

---
