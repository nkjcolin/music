"""Main window: sidebar navigation with Download, Queue and Settings pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.downloader import DownloadOptions
from ..core.paths import icon_path
from ..core.queue_manager import QueueManager
from ..core.settings import BITRATES, RESOLUTIONS, AppSettings
from . import theme
from .library_widget import LibraryWidget
from .queue_widget import QueueWidget


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Songtify — Media Downloader")
        self.setWindowIcon(QIcon(icon_path()))
        self.resize(940, 660)
        self.setMinimumSize(820, 560)

        self.settings = AppSettings()
        self.queue = QueueManager(self.settings.concurrency)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.queue_page = QueueWidget()
        self.library_page = LibraryWidget(self.settings)
        self.stack.addWidget(self._build_download_page())   # 0
        self.stack.addWidget(self._build_queue_page())       # 1
        self.stack.addWidget(self._build_library_page())     # 2
        self.stack.addWidget(self._build_settings_page())    # 3
        root.addWidget(self.stack, 1)

        self._wire_queue()
        self._select_nav(0)

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

    # -- download page -----------------------------------------------------
    def _build_download_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)

        title = QLabel("Download")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Paste a video or playlist link, choose a format, and add it to the queue.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)

        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 22, 22, 22)
        c.setSpacing(16)

        # URL row
        c.addWidget(self._label("Video / Playlist URL"))
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_input.returnPressed.connect(self._add_to_queue)
        url_row.addWidget(self.url_input, 1)
        add_btn = QPushButton("  Add to Queue")
        add_btn.setObjectName("primary")
        add_btn.setIcon(theme.icon("fa5s.plus", "white"))
        add_btn.clicked.connect(self._add_to_queue)
        url_row.addWidget(add_btn)
        c.addLayout(url_row)

        # Format segmented toggle
        c.addWidget(self._label("Format"))
        seg_row = QHBoxLayout()
        seg_row.setSpacing(8)
        self.seg_group = QButtonGroup(self)
        self.audio_btn = QPushButton("  Audio (MP3)")
        self.audio_btn.setObjectName("segment")
        self.audio_btn.setIcon(theme.icon("fa5s.music", theme.TEXT))
        self.video_btn = QPushButton("  Video (MP4)")
        self.video_btn.setObjectName("segment")
        self.video_btn.setIcon(theme.icon("fa5s.film", theme.TEXT))
        for b in (self.audio_btn, self.video_btn):
            b.setCheckable(True)
            self.seg_group.addButton(b)
            seg_row.addWidget(b)
        seg_row.addStretch(1)
        self.audio_btn.toggled.connect(self._on_format_toggled)
        c.addLayout(seg_row)

        # Quality row (bitrate or resolution swap)
        self.quality_label = self._label("Audio quality (kbps)")
        c.addWidget(self.quality_label)
        q_row = QHBoxLayout()
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(BITRATES)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        self.resolution_combo.setVisible(False)
        q_row.addWidget(self.bitrate_combo)
        q_row.addWidget(self.resolution_combo)
        q_row.addStretch(1)
        c.addLayout(q_row)

        # Folder row
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

        # restore persisted format choice
        if self.settings.format == "video":
            self.video_btn.setChecked(True)
        else:
            self.audio_btn.setChecked(True)
        self._on_format_toggled(self.audio_btn.isChecked())
        self.bitrate_combo.setCurrentText(self.settings.bitrate)
        self.resolution_combo.setCurrentText(self.settings.resolution)
        return page

    def _on_format_toggled(self, audio_on: bool) -> None:
        self.bitrate_combo.setVisible(audio_on)
        self.resolution_combo.setVisible(not audio_on)
        self.quality_label.setText("Audio quality (kbps)" if audio_on else "Video resolution")

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
        clear_btn = QPushButton("  Clear finished")
        clear_btn.setIcon(theme.icon("fa5s.broom", theme.TEXT))
        clear_btn.clicked.connect(self._clear_finished)
        header.addWidget(clear_btn)
        lay.addLayout(header)

        lay.addWidget(self.queue_page, 1)

        lay.addWidget(self._label("Activity log"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(130)
        lay.addWidget(self.log_area)
        return page

    def _clear_finished(self) -> None:
        for item_id, row in list(self.queue_page.rows.items()):
            if row.status_label.text() in ("Done", "Cancelled", "Error"):
                row.setParent(None)
                row.deleteLater()
                self.queue_page.rows.pop(item_id, None)
                self.queue.items.pop(item_id, None)
        if not self.queue_page.rows:
            self.queue_page.empty.setVisible(True)

    # -- library page ------------------------------------------------------
    def _build_library_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        title = QLabel("Library")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("Downloaded files in your save folder. Edit a name and press Rename.")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(sub)

        lay.addWidget(self.library_page, 1)
        return page

    # -- settings page -----------------------------------------------------
    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 22, 22, 22)
        c.setSpacing(16)

        # Default folder
        c.addWidget(self._label("Default download folder"))
        f_row = QHBoxLayout()
        self.set_folder_input = QLineEdit(self.settings.folder)
        self.set_folder_input.setReadOnly(True)
        f_row.addWidget(self.set_folder_input, 1)
        b = QPushButton("  Browse")
        b.setIcon(theme.icon("fa5s.folder-open", theme.TEXT))
        b.clicked.connect(self._choose_default_folder)
        f_row.addWidget(b)
        c.addLayout(f_row)

        # Concurrency
        c.addWidget(self._label("Simultaneous downloads"))
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 10)
        self.concurrency_spin.setValue(self.settings.concurrency)
        self.concurrency_spin.setFixedWidth(90)
        self.concurrency_spin.valueChanged.connect(self._on_concurrency_changed)
        c.addWidget(self.concurrency_spin)

        # Toggles
        self.lyrics_check = QCheckBox("Fetch lyrics for audio downloads (synced .lrc + embedded)")
        self.lyrics_check.setChecked(self.settings.fetch_lyrics)
        self.lyrics_check.toggled.connect(lambda v: setattr(self.settings, "fetch_lyrics", v))
        c.addWidget(self.lyrics_check)

        self.metadata_check = QCheckBox("Embed metadata and cover art")
        self.metadata_check.setChecked(self.settings.embed_metadata)
        self.metadata_check.toggled.connect(lambda v: setattr(self.settings, "embed_metadata", v))
        c.addWidget(self.metadata_check)

        lay.addWidget(card)
        lay.addStretch(1)
        return page

    def _on_concurrency_changed(self, value: int) -> None:
        self.settings.concurrency = value
        self.queue.set_concurrency(value)

    # -- helpers -----------------------------------------------------------
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.settings.folder)
        if folder:
            self.settings.folder = folder
            self.folder_input.setText(folder)
            self.set_folder_input.setText(folder)

    def _choose_default_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.settings.folder)
        if folder:
            self.settings.folder = folder
            self.set_folder_input.setText(folder)
            self.folder_input.setText(folder)

    def _current_options(self) -> DownloadOptions:
        audio = self.audio_btn.isChecked()
        return DownloadOptions(
            folder=self.settings.folder,
            fmt="audio" if audio else "video",
            bitrate=self.bitrate_combo.currentText(),
            resolution=self.resolution_combo.currentText(),
            fetch_lyrics=self.settings.fetch_lyrics,
            embed_metadata=self.settings.embed_metadata,
        )

    def _add_to_queue(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._log("Please enter a URL.")
            return
        # persist format choices
        self.settings.format = "audio" if self.audio_btn.isChecked() else "video"
        self.settings.bitrate = self.bitrate_combo.currentText()
        self.settings.resolution = self.resolution_combo.currentText()

        self.queue.add_url(url, self._current_options())
        self.url_input.clear()
        self._select_nav(1)  # jump to queue

    # -- queue wiring ------------------------------------------------------
    def _wire_queue(self) -> None:
        self.queue.item_added.connect(self.queue_page.add_item)
        self.queue.item_progress.connect(self.queue_page.on_progress)
        self.queue.item_status.connect(self.queue_page.on_status)
        self.queue.item_finished.connect(self.queue_page.on_finished)
        self.queue.item_error.connect(self.queue_page.on_error)
        self.queue.log.connect(self._log)

        self.queue_page.cancel_requested.connect(self.queue.cancel)
        self.queue_page.retry_requested.connect(self.queue.retry)
        self.queue_page.rename_requested.connect(self.queue.rename)

    def _log(self, message: str) -> None:
        self.log_area.append(message)
