"""Main window: sidebar navigation with Download, Queue and Settings pages."""

from __future__ import annotations

import os

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import history as history_mod
from ..core import resolvers, updater
from ..core.downloader import DownloadOptions
from ..core.naming import TEMPLATE_HELP
from ..core.paths import icon_path
from ..core.queue_manager import QueueManager
from ..core.search import SearchWorker
from ..core.settings import (
    BITRATES,
    CODECS,
    COOKIE_BROWSERS,
    RESOLUTIONS,
    AppSettings,
    archive_path,
)
from . import theme
from .history_widget import HistoryWidget
from .library_widget import LibraryWidget
from .player_widget import PlayerWidget
from .queue_widget import QueueWidget
from .search_widget import SearchWidget


class MainWindow(QWidget):
    # Download presets: label -> (fmt, codec, bitrate, resolution); None = Custom.
    _PRESETS = [
        ("Custom", None),
        ("MP3 · 320 kbps", ("audio", "mp3", "320", None)),
        ("MP3 · 192 kbps", ("audio", "mp3", "192", None)),
        ("M4A · 256 kbps", ("audio", "m4a", "256", None)),
        ("FLAC (lossless)", ("audio", "flac", None, None)),
        ("Video · 1080p", ("video", None, None, "1080")),
        ("Video · 720p", ("video", None, None, "720")),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._applying_preset = False
        self.setObjectName("root")
        self.setWindowTitle("Songtify — Media Downloader")
        self.setWindowIcon(QIcon(icon_path()))
        self.resize(940, 720)
        self.setMinimumSize(820, 580)
        self.setAcceptDrops(True)

        self.settings = AppSettings()
        self.queue = QueueManager(self.settings.concurrency)
        self._last_clip = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.queue_page = QueueWidget()
        self.library_page = LibraryWidget(self.settings)
        self.player_page = PlayerWidget(self.settings)
        self.history_page = HistoryWidget()
        self.stack.addWidget(self._build_download_page())   # 0
        self.stack.addWidget(self._build_queue_page())       # 1
        self.stack.addWidget(self._build_library_page())     # 2
        self.stack.addWidget(self._build_player_page())      # 3
        self.stack.addWidget(self._build_history_page())     # 4
        self.stack.addWidget(self._build_settings_page())    # 5
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)
        outer.addWidget(self._build_mini_bar())

        self.library_page.play_requested.connect(self._play_in_app)
        self.history_page.redownload_requested.connect(self._redownload)
        self._wire_player_bar()
        self._wire_queue()
        self._setup_clipboard()
        self._setup_tray()
        self._select_nav(0)
        self.queue.load_state()

    # -- sidebar -----------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        logo = QLabel("🎵  Songtify")
        logo.setObjectName("logo")
        lay.addWidget(logo)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, (label, icon_name) in enumerate([
            ("Download", "fa5s.download"),
            ("Queue", "fa5s.list"),
            ("Library", "fa5s.compact-disc"),
            ("Player", "fa5s.headphones"),
            ("History", "fa5s.history"),
            ("Settings", "fa5s.cog"),
        ]):
            btn = QPushButton(f"  {label}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setIcon(theme.icon(icon_name, theme.TEXT_DIM))
            btn.clicked.connect(lambda _=False, i=idx: self._select_nav(i))
            self.nav_group.addButton(btn, idx)
            lay.addWidget(btn)

        lay.addStretch(1)
        hint = QLabel("Personal use only.\nRespect content licenses.")
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px; padding: 14px;")
        lay.addWidget(hint)
        return side

    def _select_nav(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        btn = self.nav_group.button(idx)
        if btn:
            btn.setChecked(True)
        if idx == 2:  # Library — rescan the folder each time it's opened
            self.library_page.refresh()
        elif idx == 3:  # Player — rescan the music folder for the song list
            self.player_page.refresh_songs()
        elif idx == 4:  # History — reload from disk
            self.history_page.refresh()

    # -- download page -----------------------------------------------------
    def _build_download_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        title = QLabel("Download")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Search for a song, or paste a video / playlist / Spotify / Deezer link.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)

        # -- Format / quality / codec card (top, single row) --
        fmt_card = QFrame()
        fmt_card.setObjectName("card")
        fc = QHBoxLayout(fmt_card)
        fc.setContentsMargins(22, 16, 22, 16)
        fc.setSpacing(8)

        fc.addWidget(self._label("Preset"))
        self.preset_combo = QComboBox()
        for label, _ in self._PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        fc.addWidget(self.preset_combo)
        fc.addSpacing(14)

        fc.addWidget(self._label("Format"))
        self.seg_group = QButtonGroup(self)
        self.audio_btn = QPushButton("  Audio")
        self.audio_btn.setObjectName("segment")
        self.audio_btn.setIcon(theme.icon("fa5s.music", theme.TEXT))
        self.video_btn = QPushButton("  Video (MP4)")
        self.video_btn.setObjectName("segment")
        self.video_btn.setIcon(theme.icon("fa5s.film", theme.TEXT))
        for b in (self.audio_btn, self.video_btn):
            b.setCheckable(True)
            self.seg_group.addButton(b)
            fc.addWidget(b)
        self.audio_btn.toggled.connect(self._on_format_toggled)

        fc.addSpacing(14)
        self.bitrate_label = self._label("Bitrate")
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(BITRATES)
        self.codec_label = self._label("Codec")
        self.codec_combo = QComboBox()
        for codec in CODECS:
            self.codec_combo.addItem(codec.upper(), codec)
        self.resolution_label = self._label("Resolution")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        for w_ in (self.bitrate_label, self.bitrate_combo, self.codec_label,
                   self.codec_combo, self.resolution_label, self.resolution_combo):
            fc.addWidget(w_)
        self.resolution_label.setVisible(False)
        self.resolution_combo.setVisible(False)
        fc.addStretch(1)
        lay.addWidget(fmt_card)

        # Manual control changes drop the preset back to "Custom".
        self.bitrate_combo.currentIndexChanged.connect(self._mark_custom_preset)
        self.codec_combo.currentIndexChanged.connect(self._mark_custom_preset)
        self.resolution_combo.currentIndexChanged.connect(self._mark_custom_preset)
        self.audio_btn.toggled.connect(self._mark_custom_preset)

        # -- Search card --
        search_card = QFrame()
        search_card.setObjectName("card")
        sc = QVBoxLayout(search_card)
        sc.setContentsMargins(22, 22, 22, 22)
        sc.setSpacing(12)
        sc.addWidget(self._label("Search"))
        s_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by song or artist…")
        self.search_input.returnPressed.connect(self._do_search)
        s_row.addWidget(self.search_input, 1)
        search_btn = QPushButton("  Search")
        search_btn.setObjectName("primary")
        search_btn.setIcon(theme.icon("fa5s.search", "white"))
        search_btn.clicked.connect(self._do_search)
        s_row.addWidget(search_btn)
        sc.addLayout(s_row)

        self.search_panel = SearchWidget()
        self.search_panel.setMinimumHeight(200)
        self.search_panel.add_requested.connect(self._add_search_result)
        sc.addWidget(self.search_panel)
        lay.addWidget(search_card)

        # -- Link + destination card --
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 22, 22, 22)
        c.setSpacing(16)

        c.addWidget(self._label("Or paste a link"))
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…  ·  open.spotify.com/…")
        self.url_input.returnPressed.connect(self._add_to_queue)
        url_row.addWidget(self.url_input, 1)
        add_btn = QPushButton("  Add to Queue")
        add_btn.setObjectName("primary")
        add_btn.setIcon(theme.icon("fa5s.plus", "white"))
        add_btn.clicked.connect(self._add_to_queue)
        url_row.addWidget(add_btn)
        c.addLayout(url_row)

        c.addWidget(self._label("Save to"))
        f_row = QHBoxLayout()
        self.folder_input = QLineEdit(self.settings.folder)
        self.folder_input.setReadOnly(True)
        f_row.addWidget(self.folder_input, 1)
        folder_btn = QPushButton("  Browse")
        folder_btn.setIcon(theme.icon("fa5s.folder-open", theme.TEXT))
        folder_btn.clicked.connect(self._choose_folder)
        f_row.addWidget(folder_btn)
        c.addLayout(f_row)

        lay.addWidget(card)
        lay.addStretch(1)

        # restore persisted choices
        if self.settings.format == "video":
            self.video_btn.setChecked(True)
        else:
            self.audio_btn.setChecked(True)
        self._on_format_toggled(self.audio_btn.isChecked())
        self.bitrate_combo.setCurrentText(self.settings.bitrate)
        self.resolution_combo.setCurrentText(self.settings.resolution)
        idx = self.codec_combo.findData(self.settings.codec)
        if idx >= 0:
            self.codec_combo.setCurrentIndex(idx)
        return page

    def _apply_preset(self, idx: int) -> None:
        if not (0 <= idx < len(self._PRESETS)):
            return
        spec = self._PRESETS[idx][1]
        if spec is None:   # "Custom" — leave the controls as they are
            return
        fmt, codec, bitrate, res = spec
        self._applying_preset = True
        (self.audio_btn if fmt == "audio" else self.video_btn).setChecked(True)
        if codec:
            ci = self.codec_combo.findData(codec)
            if ci >= 0:
                self.codec_combo.setCurrentIndex(ci)
        if bitrate:
            self.bitrate_combo.setCurrentText(bitrate)
        if res:
            self.resolution_combo.setCurrentText(res)
        self._applying_preset = False

    def _mark_custom_preset(self, *_args) -> None:
        # A manual tweak means the selection no longer matches a named preset.
        if self._applying_preset:
            return
        if self.preset_combo.currentIndex() != 0:
            self.preset_combo.setCurrentIndex(0)

    def _on_format_toggled(self, audio_on: bool) -> None:
        for w_ in (self.bitrate_label, self.bitrate_combo, self.codec_label, self.codec_combo):
            w_.setVisible(audio_on)
        self.resolution_label.setVisible(not audio_on)
        self.resolution_combo.setVisible(not audio_on)
        # Reflect the destination for the chosen format.
        self.folder_input.setText(self.settings.folder_for("audio" if audio_on else "video"))

    # -- queue page --------------------------------------------------------
    def _build_queue_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Queue")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.pause_btn = QPushButton("  Pause")
        self.pause_btn.setIcon(theme.icon("fa5s.pause", theme.TEXT))
        self.pause_btn.clicked.connect(self.queue.toggle_pause)
        header.addWidget(self.pause_btn)
        retry_btn = QPushButton("  Retry failed")
        retry_btn.setIcon(theme.icon("fa5s.redo", theme.TEXT))
        retry_btn.clicked.connect(self.queue.retry_all_failed)
        header.addWidget(retry_btn)
        clear_btn = QPushButton("  Clear finished")
        clear_btn.setIcon(theme.icon("fa5s.broom", theme.TEXT))
        clear_btn.clicked.connect(self._clear_finished)
        header.addWidget(clear_btn)
        clear_all_btn = QPushButton("  Clear all")
        clear_all_btn.setIcon(theme.icon("fa5s.trash", theme.TEXT))
        clear_all_btn.clicked.connect(self._clear_all)
        header.addWidget(clear_all_btn)
        lay.addLayout(header)

        lay.addWidget(self.queue_page, 1)

        lay.addWidget(self._label("Activity log"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(130)
        lay.addWidget(self.log_area)
        return page

    def _on_paused_changed(self, paused: bool) -> None:
        self.pause_btn.setText("  Resume" if paused else "  Pause")
        self.pause_btn.setIcon(theme.icon("fa5s.play" if paused else "fa5s.pause", theme.TEXT))

    def _clear_finished(self) -> None:
        for item_id, row in list(self.queue_page.rows.items()):
            if row.status_label.text() in ("Done", "Cancelled", "Error", "Skipped"):
                row.setParent(None)
                row.deleteLater()
                self.queue_page.rows.pop(item_id, None)
                self.queue.remove(item_id)
        if not self.queue_page.rows:
            self.queue_page.empty.setVisible(True)

    def _clear_all(self) -> None:
        self.queue.clear_all()
        self.queue_page.clear_all_rows()

    def _remove_item(self, item_id: str) -> None:
        self.queue.remove(item_id)
        self.queue_page.remove_row(item_id)

    def _move_item(self, item_id: str, delta: int) -> None:
        self.queue.move(item_id, delta)
        self.queue_page.move_row(item_id, delta)

    # -- library page ------------------------------------------------------
    def _build_library_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        title = QLabel("Library")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Downloaded files in your save folder. Rename or edit tags in place.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)

        lay.addWidget(self.library_page, 1)
        return page

    # -- player page -------------------------------------------------------
    def _build_player_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        title = QLabel("Player")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Play a track and follow along with time-synced lyrics.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)

        lay.addWidget(self.player_page, 1)
        return page

    def _play_in_app(self, path: str) -> None:
        self.player_page.play_file(path)
        self._select_nav(3)  # Player page

    # -- history page ------------------------------------------------------
    def _build_history_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        title = QLabel("History")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Everything you've downloaded. Re-download or open the file.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)
        lay.addWidget(self.history_page, 1)
        return page

    def _redownload(self, url: str, name: str) -> None:
        if not url:
            return
        self.queue.add_resolved(url, name, self._current_options())
        self._log(f"Re-downloading: {name}")
        self._select_nav(1)

    # -- system tray / notifications --------------------------------------
    def _setup_tray(self) -> None:
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(QIcon(icon_path()), self)
        self._tray.setToolTip("Songtify")
        menu = QMenu()
        show_act = QAction("Show Songtify", self)
        show_act.triggered.connect(self._show_from_tray)
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(show_act)
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_download_finished(self, item_id: str, filepath: str) -> None:
        """Record history and (optionally) notify when an item finishes."""
        item = self.queue.items.get(item_id)
        if item:
            history_mod.add_entry(
                item.name or os.path.basename(filepath), filepath, item.url, item.options.fmt)
        if self.settings.notifications and self._tray:
            self._tray.showMessage(
                "Songtify", f"Saved: {os.path.basename(filepath)}",
                QSystemTrayIcon.Information, 4000)

    # -- mini-player bar (persistent across pages) -------------------------
    def _build_mini_bar(self) -> QWidget:
        self.mini_bar = QFrame()
        self.mini_bar.setObjectName("miniBar")
        lay = QHBoxLayout(self.mini_bar)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(10)

        self.mini_prev = self._mini_btn("fa5s.step-backward", "Previous",
                                        lambda: self.player_page.play_prev())
        lay.addWidget(self.mini_prev)
        self.mini_play = self._mini_btn("fa5s.play", "Play / pause",
                                        lambda: self.player_page.toggle_play())
        lay.addWidget(self.mini_play)
        self.mini_next = self._mini_btn("fa5s.step-forward", "Next",
                                        lambda: self.player_page.play_next())
        lay.addWidget(self.mini_next)

        self.mini_title = QLabel("Nothing playing")
        self.mini_title.setStyleSheet("font-weight: 600;")
        lay.addWidget(self.mini_title)
        self.mini_artist = QLabel("")
        self.mini_artist.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(self.mini_artist)
        lay.addStretch(1)

        open_player = QPushButton("  Open player")
        open_player.setIcon(theme.icon("fa5s.headphones", theme.TEXT))
        open_player.clicked.connect(lambda: self._select_nav(3))
        lay.addWidget(open_player)

        self.mini_bar.setVisible(False)   # appears once something plays
        return self.mini_bar

    def _mini_btn(self, icon_name: str, tip: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(theme.icon(icon_name, theme.TEXT))
        btn.setToolTip(tip)
        btn.setFixedSize(34, 34)
        btn.clicked.connect(slot)
        return btn

    def _wire_player_bar(self) -> None:
        self.player_page.now_playing.connect(self._on_now_playing)
        self.player_page.state_changed.connect(self._on_player_state)

    def _on_now_playing(self, title: str, artist: str) -> None:
        self.mini_bar.setVisible(True)
        self.mini_title.setText(title)
        self.mini_artist.setText(f"— {artist}" if artist else "")

    def _on_player_state(self, playing: bool) -> None:
        self.mini_play.setIcon(theme.icon("fa5s.pause" if playing else "fa5s.play", theme.TEXT))

    # -- settings page -----------------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 22, 22, 22)
        c.setSpacing(16)

        # Default music (audio) folder
        c.addWidget(self._label("Default music folder"))
        m_row = QHBoxLayout()
        self.set_music_input = QLineEdit(self.settings.folder)
        self.set_music_input.setReadOnly(True)
        m_row.addWidget(self.set_music_input, 1)
        mb = QPushButton("  Browse")
        mb.setIcon(theme.icon("fa5s.folder-open", theme.TEXT))
        mb.clicked.connect(self._choose_music_folder)
        m_row.addWidget(mb)
        c.addLayout(m_row)

        # Default video folder
        c.addWidget(self._label("Default video folder"))
        v_row = QHBoxLayout()
        self.set_video_input = QLineEdit(self.settings.video_folder)
        self.set_video_input.setReadOnly(True)
        v_row.addWidget(self.set_video_input, 1)
        vb = QPushButton("  Browse")
        vb.setIcon(theme.icon("fa5s.folder-open", theme.TEXT))
        vb.clicked.connect(self._choose_video_folder)
        v_row.addWidget(vb)
        c.addLayout(v_row)

        # Output template
        c.addWidget(self._label("Filename template"))
        self.template_input = QLineEdit(self.settings.template)
        self.template_input.setPlaceholderText("{name}")
        self.template_input.editingFinished.connect(self._on_template_changed)
        c.addWidget(self.template_input)
        tpl_hint = QLabel(f"Use / for sub-folders. Tokens: {TEMPLATE_HELP}")
        tpl_hint.setWordWrap(True)
        tpl_hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        c.addWidget(tpl_hint)

        # Concurrency + bandwidth limit
        row = QHBoxLayout()
        row.setSpacing(24)
        col1 = QVBoxLayout()
        col1.addWidget(self._label("Simultaneous downloads"))
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 10)
        self.concurrency_spin.setValue(self.settings.concurrency)
        self.concurrency_spin.setFixedWidth(90)
        self.concurrency_spin.valueChanged.connect(self._on_concurrency_changed)
        col1.addWidget(self.concurrency_spin)
        row.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(self._label("Speed limit (KB/s, 0 = unlimited)"))
        self.ratelimit_spin = QSpinBox()
        self.ratelimit_spin.setRange(0, 1_000_000)
        self.ratelimit_spin.setSingleStep(100)
        self.ratelimit_spin.setValue(self.settings.ratelimit)
        self.ratelimit_spin.setSpecialValueText("Unlimited")
        self.ratelimit_spin.setFixedWidth(140)
        self.ratelimit_spin.valueChanged.connect(lambda v: setattr(self.settings, "ratelimit", v))
        col2.addWidget(self.ratelimit_spin)
        row.addLayout(col2)
        row.addStretch(1)
        c.addLayout(row)

        # Toggles
        self.lyrics_check = QCheckBox("Fetch lyrics for audio downloads (synced .lrc + embedded)")
        self.lyrics_check.setChecked(self.settings.fetch_lyrics)
        self.lyrics_check.toggled.connect(lambda v: setattr(self.settings, "fetch_lyrics", v))
        c.addWidget(self.lyrics_check)

        self.metadata_check = QCheckBox("Embed metadata and cover art")
        self.metadata_check.setChecked(self.settings.embed_metadata)
        self.metadata_check.toggled.connect(lambda v: setattr(self.settings, "embed_metadata", v))
        c.addWidget(self.metadata_check)

        self.archive_check = QCheckBox("Skip tracks already downloaded (duplicate detection)")
        self.archive_check.setChecked(self.settings.skip_existing)
        self.archive_check.toggled.connect(lambda v: setattr(self.settings, "skip_existing", v))
        c.addWidget(self.archive_check)

        self.clipboard_check = QCheckBox("Auto-detect links copied to the clipboard")
        self.clipboard_check.setChecked(self.settings.clipboard_watch)
        self.clipboard_check.toggled.connect(lambda v: setattr(self.settings, "clipboard_watch", v))
        c.addWidget(self.clipboard_check)

        self.notify_check = QCheckBox("Show a desktop notification when a download finishes")
        self.notify_check.setChecked(self.settings.notifications)
        self.notify_check.toggled.connect(lambda v: setattr(self.settings, "notifications", v))
        c.addWidget(self.notify_check)

        # Advanced download options
        c.addWidget(self._label("Advanced download"))

        ck_row = QHBoxLayout()
        ck_row.addWidget(QLabel("Use cookies from browser"))
        self.cookies_combo = QComboBox()
        for b in COOKIE_BROWSERS:
            self.cookies_combo.addItem("None" if b == "" else b.capitalize(), b)
        idx = self.cookies_combo.findData(self.settings.cookies_browser)
        if idx >= 0:
            self.cookies_combo.setCurrentIndex(idx)
        self.cookies_combo.currentIndexChanged.connect(
            lambda: setattr(self.settings, "cookies_browser", self.cookies_combo.currentData() or ""))
        self.cookies_combo.setToolTip("Lets you download age-restricted or private items you can access in that browser")
        ck_row.addWidget(self.cookies_combo)
        ck_row.addStretch(1)
        c.addLayout(ck_row)

        self.thumbnail_check = QCheckBox("Embed thumbnail as cover art")
        self.thumbnail_check.setChecked(self.settings.embed_thumbnail)
        self.thumbnail_check.toggled.connect(lambda v: setattr(self.settings, "embed_thumbnail", v))
        c.addWidget(self.thumbnail_check)

        self.sponsorblock_check = QCheckBox("Remove SponsorBlock segments (sponsor / intro / outro, YouTube)")
        self.sponsorblock_check.setChecked(self.settings.sponsorblock)
        self.sponsorblock_check.toggled.connect(lambda v: setattr(self.settings, "sponsorblock", v))
        c.addWidget(self.sponsorblock_check)

        self.subs_check = QCheckBox("Embed subtitles in videos (English, incl. auto-generated)")
        self.subs_check.setChecked(self.settings.embed_subs)
        self.subs_check.toggled.connect(lambda v: setattr(self.settings, "embed_subs", v))
        c.addWidget(self.subs_check)

        self.chapters_check = QCheckBox("Embed chapters in videos")
        self.chapters_check.setChecked(self.settings.embed_chapters)
        self.chapters_check.toggled.connect(lambda v: setattr(self.settings, "embed_chapters", v))
        c.addWidget(self.chapters_check)

        # yt-dlp updater
        c.addWidget(self._label("Downloader engine"))
        u_row = QHBoxLayout()
        self.update_btn = QPushButton("  Update yt-dlp")
        self.update_btn.setIcon(theme.icon("fa5s.sync", theme.TEXT))
        self.update_btn.clicked.connect(self._update_ytdlp)
        u_row.addWidget(self.update_btn)
        self.update_status = QLabel(f"yt-dlp {updater.current_version()}")
        self.update_status.setStyleSheet(f"color: {theme.TEXT_DIM};")
        u_row.addWidget(self.update_status, 1)
        c.addLayout(u_row)

        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _on_concurrency_changed(self, value: int) -> None:
        self.settings.concurrency = value
        self.queue.set_concurrency(value)

    def _on_template_changed(self) -> None:
        self.settings.template = self.template_input.text()
        self.template_input.setText(self.settings.template)

    def _update_ytdlp(self) -> None:
        self.update_btn.setEnabled(False)
        self.update_status.setText("Updating yt-dlp…")
        worker = updater.UpdateWorker()
        worker.signals.finished.connect(self._on_update_done)
        QThreadPool.globalInstance().start(worker)

    def _on_update_done(self, ok: bool, message: str) -> None:
        self.update_btn.setEnabled(True)
        self.update_status.setText(message)
        self._log(message)

    # -- helpers -----------------------------------------------------------
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _choose_folder(self) -> None:
        """Browse on the Download page — sets the folder for the active format."""
        is_video = self.video_btn.isChecked()
        fmt = "video" if is_video else "audio"
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.settings.folder_for(fmt))
        if not folder:
            return
        if is_video:
            self.settings.video_folder = folder
            self.set_video_input.setText(folder)
        else:
            self.settings.folder = folder
            self.set_music_input.setText(folder)
        self.folder_input.setText(folder)

    def _choose_music_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Music Folder", self.settings.folder)
        if folder:
            self.settings.folder = folder
            self.set_music_input.setText(folder)
            if not self.video_btn.isChecked():
                self.folder_input.setText(folder)

    def _choose_video_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Video Folder", self.settings.video_folder)
        if folder:
            self.settings.video_folder = folder
            self.set_video_input.setText(folder)
            if self.video_btn.isChecked():
                self.folder_input.setText(folder)

    def _persist_format_choices(self) -> None:
        self.settings.format = "audio" if self.audio_btn.isChecked() else "video"
        self.settings.bitrate = self.bitrate_combo.currentText()
        self.settings.resolution = self.resolution_combo.currentText()
        self.settings.codec = self.codec_combo.currentData() or "mp3"

    def _current_options(self) -> DownloadOptions:
        audio = self.audio_btn.isChecked()
        fmt = "audio" if audio else "video"
        return DownloadOptions(
            folder=self.settings.folder_for(fmt),
            fmt=fmt,
            bitrate=self.bitrate_combo.currentText(),
            resolution=self.resolution_combo.currentText(),
            codec=self.codec_combo.currentData() or "mp3",
            template=self.settings.template,
            ratelimit_kbps=self.settings.ratelimit,
            use_archive=self.settings.skip_existing,
            archive_path=archive_path(),
            fetch_lyrics=self.settings.fetch_lyrics,
            embed_metadata=self.settings.embed_metadata,
            embed_thumbnail=self.settings.embed_thumbnail,
            cookies_browser=self.settings.cookies_browser,
            sponsorblock=self.settings.sponsorblock,
            embed_subs=self.settings.embed_subs,
            embed_chapters=self.settings.embed_chapters,
        )

    # -- search ------------------------------------------------------------
    def _do_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        self.search_panel.set_loading(query)
        worker = SearchWorker(query)
        worker.signals.results.connect(self.search_panel.set_results)
        worker.signals.error.connect(
            lambda q, msg: self.search_panel.set_message(f"Search failed: {msg}")
        )
        QThreadPool.globalInstance().start(worker)

    def _add_search_result(self, url: str, name: str) -> None:
        # Stay on the Download page so the user can keep adding tracks; just
        # confirm in place rather than jumping to the Queue.
        self._persist_format_choices()
        self.queue.add_resolved(url, name, self._current_options())
        self._log(f"Queued: {name}")
        self.search_panel.notify(f"Added “{name}” to the queue. Click another result to add more.")

    # -- add from URL ------------------------------------------------------
    def _add_to_queue(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._log("Please enter a URL.")
            return
        self._persist_format_choices()
        self.queue.add_url(url, self._current_options())
        self.url_input.clear()
        self._select_nav(1)  # jump to queue

    # -- clipboard & drag/drop --------------------------------------------
    def _setup_clipboard(self) -> None:
        clip = QGuiApplication.clipboard()
        if clip:
            clip.dataChanged.connect(self._on_clipboard)

    def _on_clipboard(self) -> None:
        if not self.settings.clipboard_watch:
            return
        clip = QGuiApplication.clipboard()
        url = resolvers.find_first_url(clip.text() if clip else "")
        if not url or url == self._last_clip:
            return
        self._last_clip = url
        if not self.url_input.text().strip():
            self.url_input.setText(url)
        self._log(f"Clipboard link detected — ready on the Download page: {url}")
        self._select_nav(0)

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasUrls() or md.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        text = ""
        if md.hasUrls() and md.urls():
            text = md.urls()[0].toString()
        elif md.hasText():
            text = md.text()
        url = resolvers.find_first_url(text) or text.strip()
        if not url:
            return
        self._persist_format_choices()
        self.queue.add_url(url, self._current_options())
        self._log(f"Added dropped link: {url}")
        self._select_nav(1)

    # -- queue wiring ------------------------------------------------------
    def _wire_queue(self) -> None:
        self.queue.item_added.connect(self.queue_page.add_item)
        self.queue.item_progress.connect(self.queue_page.on_progress)
        self.queue.item_status.connect(self.queue_page.on_status)
        self.queue.item_finished.connect(self.queue_page.on_finished)
        self.queue.item_finished.connect(self._on_download_finished)
        self.queue.item_error.connect(self.queue_page.on_error)
        self.queue.log.connect(self._log)
        self.queue.paused_changed.connect(self._on_paused_changed)

        self.queue_page.cancel_requested.connect(self.queue.cancel)
        self.queue_page.retry_requested.connect(self.queue.retry)
        self.queue_page.rename_requested.connect(self.queue.rename)
        self.queue_page.move_requested.connect(self._move_item)
        self.queue_page.remove_requested.connect(self._remove_item)

    def _log(self, message: str) -> None:
        self.log_area.append(message)

    def closeEvent(self, event) -> None:
        # Persist the queue so unfinished items return on next launch.
        self.queue.save()
        super().closeEvent(event)
