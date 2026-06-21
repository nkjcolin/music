"""Songtify — entry point.

A modern PySide6 front-end for yt-dlp that downloads audio (MP3) and video (MP4),
fetches lyrics, embeds metadata, supports playlists, and runs a concurrent queue.
"""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core.logsetup import setup_logging
from app.core.paths import icon_path
from app.core.settings import APP, ORG
from app.ui.main_window import MainWindow
from app.ui.theme import STYLESHEET


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP)
    app.setWindowIcon(QIcon(icon_path()))
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
