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
    """Stream the new executable to a temp file, then verify it.

    A truncated/corrupt download could brick the install if swapped in, so the
    file is validated (full length + valid ``MZ`` executable header) before it
    is returned. Raises on a bad download.
    """
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

    size = os.path.getsize(dest)
    if total and size != total:
        os.remove(dest)
        raise OSError(f"incomplete download ({size} of {total} bytes)")
    if size < 1_000_000:
        os.remove(dest)
        raise OSError("downloaded file is too small to be valid")
    with open(dest, "rb") as fh:
        header = fh.read(2)
    if header != b"MZ":
        os.remove(dest)   # file is closed now — safe to delete on Windows
        raise OSError("downloaded file is not a valid Windows executable")
    return dest


_DETACHED_PROCESS = 0x00000008


def apply_update(new_exe_path: str) -> bool:
    """Swap in the downloaded exe and relaunch — no shell, no console windows.

    Windows lets you *rename* a running executable (just not overwrite/delete
    it), so we move the current exe aside, drop the new build into its place,
    and relaunch it. The leftover ``.old`` file is removed on the next start by
    :func:`cleanup_old`. Returns True if the swap succeeded (caller then quits).
    Only applies to a frozen build.
    """
    if not is_frozen():
        return False
    current = sys.executable
    backup = current + ".old"

    if os.path.exists(backup):
        try:
            os.remove(backup)
        except OSError:
            pass  # still locked from a previous run; harmless

    try:
        os.replace(current, backup)        # rename the running exe out of the way
        os.replace(new_exe_path, current)  # put the new build at the original path
    except OSError:
        # Roll back if we moved the original but couldn't place the new one.
        if not os.path.exists(current) and os.path.exists(backup):
            try:
                os.replace(backup, current)
            except OSError:
                pass
        return False

    try:
        subprocess.Popen([current], creationflags=_DETACHED_PROCESS, close_fds=True)
    except Exception:
        pass  # already swapped; the user can relaunch manually if needed
    return True


def cleanup_old() -> None:
    """Delete the previous executable left behind by a completed update."""
    if not is_frozen():
        return
    backup = sys.executable + ".old"
    if os.path.exists(backup):
        try:
            os.remove(backup)
        except OSError:
            pass  # may still be locked right after relaunch; next start clears it
