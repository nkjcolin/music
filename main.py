"""Songtify — entry point.

A modern PySide6 front-end for yt-dlp that downloads audio (MP3) and video (MP4),
fetches lyrics, embeds metadata, supports playlists, and runs a concurrent queue.
"""

import logging
import os
import sys

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.core import appupdate
from app.core.logsetup import setup_logging
from app.core.paths import icon_path
from app.core.settings import APP, ORG
from app.ui.main_window import MainWindow
from app.ui.theme import STYLESHEET


def _silence_native_stderr() -> None:
    """Send the process's stderr to nowhere in a frozen build.

    A windowed PyInstaller app pops up a dialog ("Traceback is disabled…") if
    *anything* reaches stderr before exit — e.g. Qt teardown warnings during the
    post-update shutdown. Redirecting fd 2 keeps that dialog from ever showing.
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
    except OSError:
        pass


def _route_qt_messages_to_log() -> None:
    """Send Qt's own warnings/messages to the log file instead of stderr."""
    qt_log = logging.getLogger("songtify.qt")

    def handler(_mode, _context, message):
        qt_log.warning("%s", message)

    qInstallMessageHandler(handler)


def main() -> int:
    _silence_native_stderr()
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP)
    # After org/app names are set so logs land in the proper app-data folder.
    setup_logging()
    _route_qt_messages_to_log()
    appupdate.cleanup_old()   # remove the previous exe after a self-update
    app.setWindowIcon(QIcon(icon_path()))
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
