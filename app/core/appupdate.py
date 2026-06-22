"""Self-update: check GitHub Releases and install a newer Songtify.exe.

Pure logic only (no PySide6) so it stays unit-testable headless. The Qt worker
wrappers live in the UI layer (``main_window``).

A running ``.exe`` can't overwrite itself on Windows, so installing works by
writing the new build next to the current one and launching a tiny batch script
that waits for the app to exit, swaps the file, and relaunches it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import requests

REPO = "nkjcolin/music"
_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
_TIMEOUT = 15


def current_version() -> str:
    from .. import __version__
    return __version__


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _parse(version: str) -> tuple:
    digits = []
    for part in str(version).lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        digits.append(int(num) if num else 0)
    return tuple(digits)


def is_newer(latest: str, current: str) -> bool:
    return _parse(latest) > _parse(current)


def check_latest() -> dict | None:
    """Return ``{version, asset, html_url}`` for the latest release, or None."""
    resp = requests.get(_LATEST, headers={"Accept": "application/vnd.github+json"}, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    tag = data.get("tag_name", "") or data.get("name", "")
    asset_url = None
    for asset in data.get("assets", []):
        if asset.get("name", "").lower().endswith(".exe"):
            asset_url = asset.get("browser_download_url")
            break
    if not tag:
        return None
    return {"version": tag, "asset": asset_url, "html_url": data.get("html_url", "")}


def _download_target() -> str:
    """Where to save the freshly downloaded exe (next to the current one)."""
    folder = os.path.dirname(sys.executable) if is_frozen() else tempfile.gettempdir()
    return os.path.join(folder, "Songtify.update.exe")


def download(url: str, progress=None) -> str:
    """Stream the new executable to a temp file. ``progress`` gets 0-100 ints."""
    dest = _download_target()
    with requests.get(url, stream=True, timeout=_TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=262144):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if total and progress:
                    progress(int(done / total * 100))
    return dest


def apply_update(new_exe_path: str) -> bool:
    """Swap in the downloaded exe and relaunch via a detached batch script.

    Returns True if the swap was launched (the caller should then quit the app).
    Only works for a frozen build.
    """
    if not is_frozen():
        return False
    current = sys.executable
    bat = os.path.join(tempfile.gettempdir(), "songtify_update.bat")
    script = (
        "@echo off\r\n"
        "ping 127.0.0.1 -n 3 >nul\r\n"
        ":retry\r\n"
        f'move /y "{new_exe_path}" "{current}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto retry\r\n"
        ")\r\n"
        f'start "" "{current}"\r\n'
        'del "%~f0"\r\n'
    )
    try:
        with open(bat, "w", encoding="ascii") as fh:
            fh.write(script)
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        subprocess.Popen(["cmd", "/c", bat], creationflags=creationflags, close_fds=True)
        return True
    except Exception:
        return False
