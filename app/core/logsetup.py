"""Diagnostics logging to a rotating file in the app-data directory.

Keeps a small on-disk log so problems users hit in the wild (failed downloads,
crashes) can be diagnosed after the fact. UI activity still goes to the
in-app log; this is the persistent, technical record.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .settings import log_path

_LOG = logging.getLogger("songtify")


def setup_logging() -> None:
    """Attach a rotating file handler and route uncaught exceptions to it."""
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return  # already configured
    root.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(
            log_path(), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    except OSError:
        pass  # logging must never stop the app from running

    def _excepthook(exc_type, exc, tb):
        _LOG.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        # In a frozen build, writing to stderr triggers a pop-up error dialog;
        # the log file already has the details, so stay quiet there.
        if not getattr(sys, "frozen", False):
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook
    import os
    mei_in_path = any("_MEI" in p for p in os.environ.get("PATH", "").split(os.pathsep))
    _LOG.info(
        "Songtify started (frozen=%s, _MEI in PATH=%s, QT_QPA_PLATFORM_PLUGIN_PATH set=%s)",
        getattr(sys, "frozen", False), mei_in_path,
        bool(os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH")),
    )
