"""Update the bundled yt-dlp so downloads keep working as sites change."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QObject, QRunnable, Signal

import yt_dlp


def current_version() -> str:
    try:
        return yt_dlp.version.__version__
    except Exception:
        return "unknown"


class UpdateSignals(QObject):
    finished = Signal(bool, str)   # success, message


class UpdateWorker(QRunnable):
    """Runs ``pip install -U yt-dlp`` off the UI thread.

    Using pip (rather than yt-dlp's binary self-update) is what works for a
    pip-installed copy; a frozen build should ship a fresh yt-dlp instead.
    """

    def __init__(self) -> None:
        super().__init__()
        self.signals = UpdateSignals()

    def run(self) -> None:
        before = current_version()
        if getattr(sys, "frozen", False):
            self.signals.finished.emit(
                False,
                "This is a packaged build — reinstall the latest Songtify to update yt-dlp.",
            )
            return
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "--no-input", "yt-dlp"],
                capture_output=True, text=True, timeout=300,
            )
        except Exception as exc:
            self.signals.finished.emit(False, f"Update failed: {exc}")
            return

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            msg = tail[-1] if tail else "pip returned an error."
            self.signals.finished.emit(False, f"Update failed: {msg}")
            return

        out = (proc.stdout or "").lower()
        if "already satisfied" in out and "collecting yt-dlp" not in out:
            self.signals.finished.emit(True, f"Already up to date (yt-dlp {before}).")
        else:
            self.signals.finished.emit(
                True,
                f"Updated yt-dlp. Restart Songtify to load the new version (was {before}).",
            )
