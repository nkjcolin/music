import sys
import os
import psutil
import time
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import yt_dlp

def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

def is_file_locked(file_path):
    """Check if a file is being used by another process."""
    for proc in psutil.process_iter(attrs=['pid', 'name', 'open_files']):
        for file in proc.info['open_files'] or []:
            if file_path == file.path:
                return True
    return False

class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    cancel_signal = pyqtSignal()

    def __init__(self, url, output_path, bitrate):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.bitrate = bitrate
        self._is_running = True
        self._yt_dlp = None

    def run(self):
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'ffmpeg_location': resource_path("ffmpeg.exe"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': str(self.bitrate)
                }],
                'outtmpl': self.output_path,
                'embedmetadata': True,
                'embedthumbnail': True,
                'addmetadata': True,
                'progress_hooks': [self.progress_hook]
            }

            self.log_signal.emit(f"Starting download for: {self.url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._yt_dlp = ydl
                ydl.download([self.url])

            self.log_signal.emit("Download finished successfully.")
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
        finally:
            self.finished_signal.emit()

    def progress_hook(self, progress):
        if not self._is_running:
            raise yt_dlp.utils.DownloadError("Download was canceled, preparing to clean up files")

    def cancel(self):
        self._is_running = False
        self.cancel_signal.emit()

        try:
            if self._yt_dlp:
                self._yt_dlp.process.terminate()
        except Exception as e:
            self.log_signal.emit(f"Error during cancellation: {str(e)}")

        if os.path.exists(self.output_path):
            os.remove(self.output_path)

        if self.output_path:
            download_dir = os.path.dirname(self.output_path)
            for file_name in os.listdir(download_dir):
                if 'webm' in file_name:
                    file_path = os.path.join(download_dir, file_name)
                    os.remove(file_path)

class YouTubeDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube MP3 Downloader")
        self.setGeometry(300, 300, 600, 450)
        self.download_directory = None
        self.download_thread = None

        # UI Elements
        self.url_label = QLabel("YouTube URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL here...")

        self.folder_button = QPushButton("Choose Folder")
        self.folder_label = QLabel("No folder selected")

        self.bitrate_label = QLabel("Select Bitrate (kbps):")
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128", "192", "256", "320"])

        self.download_button = QPushButton("Download MP3")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)

        # Layouts
        main_layout = QVBoxLayout()
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_button)
        folder_layout.addWidget(self.folder_label)

        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(self.bitrate_label)
        bitrate_layout.addWidget(self.bitrate_combo)

        main_layout.addLayout(url_layout)
        main_layout.addLayout(folder_layout)
        main_layout.addLayout(bitrate_layout)
        main_layout.addWidget(self.download_button)
        main_layout.addWidget(self.cancel_button)
        main_layout.addWidget(QLabel("Download Log:"))
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

        # Event Bindings
        self.folder_button.clicked.connect(self.choose_folder)
        self.download_button.clicked.connect(self.download_audio)
        self.cancel_button.clicked.connect(self.cancel_download)

        # Timer for delaying file deletion
        self.cancel_timer = QTimer(self)
        self.cancel_timer.setSingleShot(True)
        self.cancel_timer.timeout.connect(self.delete_partial_files)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.download_directory = folder
            self.folder_label.setText(f"Selected: {folder}")

    def log(self, message):
        self.log_area.append(message)

    def download_audio(self):
        url = self.url_input.text().strip()
        if not url:
            self.log("Please enter a valid YouTube URL.")
            return
        if not self.download_directory:
            self.log("Please select a download folder.")
            return

        bitrate = self.bitrate_combo.currentText()
        output_path = os.path.join(self.download_directory, "%(title)s.%(ext)s")

        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.download_thread = DownloadThread(url, output_path, bitrate)
        self.download_thread.log_signal.connect(self.log)
        self.download_thread.finished_signal.connect(self.download_complete)
        self.download_thread.cancel_signal.connect(self.cancel_complete)
        self.download_thread.start()

    def cancel_download(self):
        if self.download_thread:
            self.download_thread.cancel()

    def cancel_complete(self):
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.log("Download was canceled.")
        self.cancel_timer.start(3000)

    def delete_partial_files(self):
        if self.download_thread and self.download_thread.output_path:
            download_dir = os.path.dirname(self.download_thread.output_path)
            for file_name in os.listdir(download_dir):
                if 'webm' in file_name:
                    file_path = os.path.join(download_dir, file_name)
                    while is_file_locked(file_path):
                        time.sleep(0.5)
                    os.remove(file_path)
                    self.log(f"Deleted partial file: {file_name}")

    def download_complete(self):
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.information(self, "Download", "Download completed.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    icon_path = resource_path("youtube_music.ico")
    app.setWindowIcon(QIcon(icon_path))
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec_())
