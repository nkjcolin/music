"""In-app audio player: song queue, now-playing card, time-synced lyrics."""

from __future__ import annotations

import os
import random

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core import library as library_mod
from ..core import lrc as lrc_mod
from ..core import lyrics as lyrics_mod
from ..core import metadata as metadata_mod
from . import theme

_AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg")
_REPEAT_NEXT = {"off": "all", "all": "one", "one": "off"}
_REPEAT_ICON = {"off": "mdi.repeat-off", "all": "mdi.repeat", "one": "mdi.repeat-once"}
_REPEAT_TIP = {"off": "Repeat: off", "all": "Repeat: all", "one": "Repeat: one"}


def _fmt_ms(ms: int) -> str:
    s = max(0, int(ms)) // 1000
    return f"{s // 60}:{s % 60:02d}"


class _LyricsSignals(QObject):
    done = Signal(str, object, object)   # path, synced_lrc, plain_text
    error = Signal(str, str)             # path, message


class _LyricsFetchWorker(QRunnable):
    """Searches for lyrics off the UI thread via :mod:`app.core.lyrics`."""

    def __init__(self, artist: str, title: str, path: str) -> None:
        super().__init__()
        self.artist = artist
        self.title = title
        self.path = path
        self.signals = _LyricsSignals()

    def run(self) -> None:
        try:
            synced, plain = lyrics_mod.fetch_lyrics(self.artist, self.title)
        except Exception as exc:
            self.signals.error.emit(self.path, str(exc))
            return
        self.signals.done.emit(self.path, synced, plain)


class PlayerWidget(QWidget):
    """Plays local audio with a real queue: next/prev, shuffle, repeat, auto-advance."""

    now_playing = Signal(str, str)   # title, artist
    state_changed = Signal(bool)     # True = playing

    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings
        self._current_path = ""
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.85)

        self._lyrics: list[tuple[int, str]] = []
        self._active = -1
        self._seeking = False
        self._song_paths: list[str] = []
        self._play_order: list[int] = []   # indices into _song_paths, playback order
        self._order_pos = -1               # position within _play_order
        self._shuffle = bool(settings.player_shuffle)
        self._repeat = settings.player_repeat

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._build_song_panel(), 1)
        main.addWidget(self._build_now_panel(), 2)
        root.addLayout(main, 1)
        root.addWidget(self._build_transport())

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

    # -- panels ------------------------------------------------------------
    def _build_song_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        header = QLabel("Songs in your folder")
        header.setObjectName("sectionLabel")
        lay.addWidget(header)
        self.song_list = QListWidget()
        self.song_list.setObjectName("songList")
        self.song_list.itemClicked.connect(self._on_song_clicked)
        lay.addWidget(self.song_list, 1)
        return panel

    def _build_now_panel(self) -> QWidget:
        self.now_panel = QWidget()
        lay = QVBoxLayout(self.now_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = QHBoxLayout()
        card.setSpacing(16)
        self.cover = QLabel()
        self.cover.setFixedSize(96, 96)
        self.cover.setObjectName("cover")
        self.cover.setAlignment(Qt.AlignCenter)
        self._set_placeholder_cover()
        card.addWidget(self.cover)

        meta = QVBoxLayout()
        meta.setSpacing(4)
        meta.addStretch(1)
        self.title_label = QLabel("Nothing playing")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.title_label.setWordWrap(True)
        self.artist_label = QLabel("")
        self.artist_label.setStyleSheet(f"color: {theme.TEXT_DIM};")
        meta.addWidget(self.title_label)
        meta.addWidget(self.artist_label)
        meta.addStretch(1)
        card.addLayout(meta, 1)

        open_btn = QPushButton("  Open file")
        open_btn.setIcon(theme.icon("fa5s.folder-open", theme.TEXT))
        open_btn.clicked.connect(self._open_file)
        card.addWidget(open_btn, 0, Qt.AlignTop)
        lay.addLayout(card)

        lyr_header = QHBoxLayout()
        lyr_label = QLabel("Lyrics")
        lyr_label.setObjectName("sectionLabel")
        lyr_header.addWidget(lyr_label)
        lyr_header.addStretch(1)
        self.find_lyrics_btn = QPushButton("  Find lyrics")
        self.find_lyrics_btn.setIcon(theme.icon("fa5s.search", theme.TEXT))
        self.find_lyrics_btn.setToolTip("Search online and save synced lyrics for this track")
        self.find_lyrics_btn.clicked.connect(self._find_lyrics)
        lyr_header.addWidget(self.find_lyrics_btn)
        self.lyrics_toggle = QPushButton("  Collapse")
        self.lyrics_toggle.setIcon(theme.icon("fa5s.chevron-up", theme.TEXT))
        self.lyrics_toggle.clicked.connect(self._toggle_lyrics)
        lyr_header.addWidget(self.lyrics_toggle)
        lay.addLayout(lyr_header)

        self.lyrics_list = QListWidget()
        self.lyrics_list.setObjectName("lyrics")
        self.lyrics_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.lyrics_list.setFocusPolicy(Qt.NoFocus)
        self.lyrics_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lyrics_list.itemClicked.connect(self._seek_to_line)
        self._reset_lyrics("Pick a song to see lyrics here.")
        lay.addWidget(self.lyrics_list, 1)
        return self.now_panel

    def _build_transport(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.shuffle_btn = self._mini("fa5s.random", "Shuffle", self._toggle_shuffle)
        lay.addWidget(self.shuffle_btn)
        self.prev_btn = self._mini("fa5s.step-backward", "Previous", lambda: self._advance(-1))
        lay.addWidget(self.prev_btn)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(theme.icon("fa5s.play", "white"))
        self.play_btn.setObjectName("primary")
        self.play_btn.setFixedSize(44, 44)
        self.play_btn.clicked.connect(self._toggle_play)
        lay.addWidget(self.play_btn)

        self.next_btn = self._mini("fa5s.step-forward", "Next", lambda: self._advance(1))
        lay.addWidget(self.next_btn)
        self.repeat_btn = self._mini(_REPEAT_ICON[self._repeat], _REPEAT_TIP[self._repeat],
                                     self._cycle_repeat)
        lay.addWidget(self.repeat_btn)

        self.elapsed = QLabel("0:00")
        self.elapsed.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(self.elapsed)

        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.seek.sliderReleased.connect(self._seek_released)
        lay.addWidget(self.seek, 1)

        self.total = QLabel("0:00")
        self.total.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(self.total)

        vol_icon = QLabel()
        vol_icon.setPixmap(theme.icon("fa5s.volume-up", theme.TEXT_DIM).pixmap(16, 16))
        lay.addWidget(vol_icon)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(85)
        self.volume.setFixedWidth(90)
        self.volume.valueChanged.connect(lambda v: self.audio.setVolume(v / 100.0))
        lay.addWidget(self.volume)

        self.minimise_btn = self._mini("fa5s.compress",
                                        "Minimise now playing to browse other songs",
                                        self._toggle_minimise)
        lay.addWidget(self.minimise_btn)
        self._sync_mode_buttons()
        return bar

    def _mini(self, icon_name: str, tip: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(theme.icon(icon_name, theme.TEXT))
        btn.setToolTip(tip)
        btn.setFixedSize(38, 38)
        btn.clicked.connect(slot)
        return btn

    # -- public ------------------------------------------------------------
    def refresh_songs(self) -> None:
        """Rescan the music folder and rebuild the song list + play order."""
        current = self.player.source().toLocalFile() if self.player.source().isValid() else ""
        self.song_list.clear()
        self._song_paths = []
        for info in library_mod.list_media(self.settings.folder):
            if info["ext"].lower() not in _AUDIO_EXTS:
                continue
            self._song_paths.append(info["path"])
            item = QListWidgetItem(info["stem"])
            self.song_list.addItem(item)
            if os.path.normcase(info["path"]) == os.path.normcase(current):
                self.song_list.setCurrentItem(item)
        if not self._song_paths:
            self.song_list.addItem(QListWidgetItem("No songs in your music folder yet."))
        # Re-anchor the play order on the current track (if still present).
        anchor = self._index_of(current) if current else None
        self._rebuild_play_order(anchor)

    def play_file(self, path: str) -> None:
        """Play a specific file, syncing the queue position to it."""
        if not path or not os.path.exists(path):
            return
        idx = self._index_of(path)
        if idx is None:
            # A file outside the folder list (Open file…): play standalone.
            self._order_pos = -1
        elif not self._play_order or idx not in self._play_order:
            self._rebuild_play_order(anchor=idx)
        else:
            self._order_pos = self._play_order.index(idx)
        self._load_and_play(path)

    def stop(self) -> None:
        self.player.stop()

    # -- queue order -------------------------------------------------------
    def _index_of(self, path: str) -> int | None:
        if not path:
            return None
        target = os.path.normcase(path)
        for i, p in enumerate(self._song_paths):
            if os.path.normcase(p) == target:
                return i
        return None

    def _rebuild_play_order(self, anchor: int | None = None) -> None:
        order = list(range(len(self._song_paths)))
        if self._shuffle:
            random.shuffle(order)
            if anchor is not None and anchor in order:
                order.remove(anchor)
                order.insert(0, anchor)
        self._play_order = order
        if anchor is not None and anchor in order:
            self._order_pos = order.index(anchor)
        else:
            self._order_pos = 0 if order else -1

    def _advance(self, delta: int) -> None:
        """Manual next/previous (delta +1 / -1)."""
        if not self._play_order:
            return
        n = len(self._play_order)
        pos = self._order_pos + delta
        if pos >= n:
            pos = 0 if self._repeat == "all" else n - 1
        elif pos < 0:
            pos = n - 1 if self._repeat == "all" else 0
        self._order_pos = pos
        self._load_and_play(self._song_paths[self._play_order[pos]])

    def _auto_advance(self) -> None:
        """Called when a track finishes — honours repeat one/all/off."""
        if self._repeat == "one":
            self.player.setPosition(0)
            self.player.play()
            return
        if not self._play_order:
            return
        if self._order_pos + 1 >= len(self._play_order) and self._repeat != "all":
            return  # end of queue, no repeat
        self._advance(1)

    def _on_song_clicked(self, item: QListWidgetItem) -> None:
        row = self.song_list.row(item)
        if 0 <= row < len(self._song_paths):
            self.play_file(self._song_paths[row])

    # -- shuffle / repeat / collapse / minimise ----------------------------
    def _toggle_shuffle(self) -> None:
        self._shuffle = not self._shuffle
        self.settings.player_shuffle = self._shuffle
        anchor = self._play_order[self._order_pos] if 0 <= self._order_pos < len(self._play_order) else None
        self._rebuild_play_order(anchor)
        self._sync_mode_buttons()

    def _cycle_repeat(self) -> None:
        self._repeat = _REPEAT_NEXT[self._repeat]
        self.settings.player_repeat = self._repeat
        self._sync_mode_buttons()

    def _sync_mode_buttons(self) -> None:
        self.shuffle_btn.setIcon(
            theme.icon("fa5s.random", theme.ACCENT if self._shuffle else theme.TEXT))
        self.shuffle_btn.setToolTip("Shuffle: on" if self._shuffle else "Shuffle: off")
        colour = theme.ACCENT if self._repeat != "off" else theme.TEXT
        self.repeat_btn.setIcon(theme.icon(_REPEAT_ICON[self._repeat], colour))
        self.repeat_btn.setToolTip(_REPEAT_TIP[self._repeat])

    def _toggle_lyrics(self) -> None:
        show = self.lyrics_list.isHidden()
        self.lyrics_list.setVisible(show)
        self.lyrics_toggle.setText("  Collapse" if show else "  Expand")
        self.lyrics_toggle.setIcon(
            theme.icon("fa5s.chevron-up" if show else "fa5s.chevron-down", theme.TEXT))

    def _toggle_minimise(self) -> None:
        minimised = not self.now_panel.isHidden()
        self.now_panel.setVisible(not minimised)
        self.minimise_btn.setIcon(
            theme.icon("fa5s.expand" if minimised else "fa5s.compress", theme.TEXT))
        self.minimise_btn.setToolTip(
            "Show now playing" if minimised else "Minimise now playing to browse other songs")

    # -- load / lyrics / cover --------------------------------------------
    def _load_and_play(self, path: str) -> None:
        if not path or not os.path.exists(path):
            return
        self._current_path = path
        if self.now_panel.isHidden():
            self._toggle_minimise()
        tags = metadata_mod.read_tags(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        title = tags.get("title") or stem
        artist = tags.get("artist") or ""
        self.title_label.setText(title)
        self.artist_label.setText(artist)
        self.now_playing.emit(title, artist)
        self._load_cover(path)

        self._lyrics = lrc_mod.load_synced(path)
        self._active = -1
        if self._lyrics:
            self.lyrics_list.clear()
            for _, text in self._lyrics:
                item = QListWidgetItem(text or "♪")
                item.setTextAlignment(Qt.AlignCenter)
                self.lyrics_list.addItem(item)
        else:
            self._reset_lyrics("No synced lyrics (.lrc) found for this track.")

        self._select_song_in_list(path)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _select_song_in_list(self, path: str) -> None:
        idx = self._index_of(path)
        if idx is not None:
            self.song_list.setCurrentRow(idx)

    def _reset_lyrics(self, message: str) -> None:
        self.lyrics_list.clear()
        item = QListWidgetItem(message)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(Qt.gray)
        self.lyrics_list.addItem(item)

    def _seek_to_line(self, item: QListWidgetItem) -> None:
        if not self._lyrics:
            return
        row = self.lyrics_list.row(item)
        if 0 <= row < len(self._lyrics):
            self.player.setPosition(self._lyrics[row][0])

    def _highlight(self, index: int) -> None:
        if index == self._active or not self._lyrics:
            return
        prev = self.lyrics_list.item(self._active) if self._active >= 0 else None
        if prev:
            prev.setForeground(Qt.gray)
            font = prev.font()
            font.setBold(False)
            prev.setFont(font)
        cur = self.lyrics_list.item(index) if index >= 0 else None
        if cur:
            cur.setForeground(Qt.white)
            font = cur.font()
            font.setBold(True)
            cur.setFont(font)
            self.lyrics_list.scrollToItem(cur, QAbstractItemView.PositionAtCenter)
        self._active = index

    def _set_placeholder_cover(self) -> None:
        self.cover.setPixmap(theme.icon("fa5s.compact-disc", theme.TEXT_DIM).pixmap(72, 72))

    def _load_cover(self, path: str) -> None:
        data = metadata_mod.read_cover(path)
        if not data:
            self._set_placeholder_cover()
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            self.cover.setPixmap(pix.scaled(
                96, 96, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self._set_placeholder_cover()

    # -- transport ---------------------------------------------------------
    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.player.source().isValid():
            self.player.play()

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open audio", self.settings.folder,
            "Audio (*.mp3 *.m4a *.flac *.wav *.opus *.ogg);;All files (*.*)",
        )
        if path:
            self.play_file(path)

    def _seek_released(self) -> None:
        self.player.setPosition(self.seek.value())
        self._seeking = False

    def _on_position(self, ms: int) -> None:
        if not self._seeking:
            self.seek.setValue(ms)
        self.elapsed.setText(_fmt_ms(ms))
        if self._lyrics:
            idx = -1
            for i, (t, _) in enumerate(self._lyrics):
                if t <= ms:
                    idx = i
                else:
                    break
            self._highlight(idx)

    def _on_duration(self, ms: int) -> None:
        self.seek.setRange(0, ms)
        self.total.setText(_fmt_ms(ms))

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlayingState
        self.play_btn.setIcon(theme.icon("fa5s.pause" if playing else "fa5s.play", "white"))
        self.state_changed.emit(playing)

    # -- public controls (for the mini-player bar) -------------------------
    def toggle_play(self) -> None:
        self._toggle_play()

    def play_next(self) -> None:
        self._advance(1)

    def play_prev(self) -> None:
        self._advance(-1)

    # -- fetch lyrics on demand -------------------------------------------
    def _find_lyrics(self) -> None:
        if not self._current_path:
            return
        tags = metadata_mod.read_tags(self._current_path)
        artist = tags.get("artist") or ""
        title = tags.get("title") or os.path.splitext(os.path.basename(self._current_path))[0]
        self.find_lyrics_btn.setEnabled(False)
        self._reset_lyrics("Searching for lyrics…")
        worker = _LyricsFetchWorker(artist, title, self._current_path)
        worker.signals.done.connect(self._on_lyrics_fetched)
        worker.signals.error.connect(self._on_lyrics_error)
        QThreadPool.globalInstance().start(worker)

    def _on_lyrics_fetched(self, path: str, synced, plain) -> None:
        self.find_lyrics_btn.setEnabled(True)
        if path != self._current_path:
            return   # user moved on to another track
        if synced:
            lyrics_mod.write_lrc_sidecar(path, synced)
            self._lyrics = lrc_mod.parse_lrc(synced)
            self._active = -1
            self.lyrics_list.clear()
            for _, text in self._lyrics:
                item = QListWidgetItem(text or "♪")
                item.setTextAlignment(Qt.AlignCenter)
                self.lyrics_list.addItem(item)
        elif plain:
            self._lyrics = []
            self.lyrics_list.clear()
            for line in plain.splitlines():
                item = QListWidgetItem(line.strip())
                item.setTextAlignment(Qt.AlignCenter)
                self.lyrics_list.addItem(item)
        else:
            self._reset_lyrics("No lyrics found for this track.")

    def _on_lyrics_error(self, path: str, message: str) -> None:
        self.find_lyrics_btn.setEnabled(True)
        if path == self._current_path:
            self._reset_lyrics(f"Lyrics search failed: {message}")

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self._auto_advance()

    def _on_error(self, error, message: str = "") -> None:
        if error != QMediaPlayer.NoError:
            self._reset_lyrics(
                f"Cannot play this file: {message or 'unsupported format/codec'}."
            )
