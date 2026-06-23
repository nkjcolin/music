"""System-wide media-key support (Play/Pause, Next, Previous, Stop).

On Windows this registers the media virtual-keys as global hotkeys and listens
for ``WM_HOTKEY`` via a native event filter, so the keys control playback even
when Songtify isn't the focused window. On other platforms it's a no-op.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

_WM_HOTKEY = 0x0312

# Hotkey id -> media virtual-key code.
_HOTKEYS = {
    1: 0xB3,  # VK_MEDIA_PLAY_PAUSE
    2: 0xB0,  # VK_MEDIA_NEXT_TRACK
    3: 0xB1,  # VK_MEDIA_PREV_TRACK
    4: 0xB2,  # VK_MEDIA_STOP
}

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt_x", wintypes.LONG),
            ("pt_y", wintypes.LONG),
        ]


class MediaKeys(QObject, QAbstractNativeEventFilter):
    """Emits a signal when a global media key is pressed."""

    play_pause = Signal()
    next_track = Signal()
    prev_track = Signal()
    stop = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._hwnd = 0
        self._registered: list[int] = []

    def register(self, hwnd: int) -> bool:
        """Register the global media hotkeys against ``hwnd``. Returns True if any stuck."""
        if sys.platform != "win32" or not hwnd:
            return False
        self._hwnd = int(hwnd)
        user32 = ctypes.windll.user32
        for hotkey_id, vk in _HOTKEYS.items():
            # fsModifiers = 0; media virtual-keys register system-wide.
            if user32.RegisterHotKey(wintypes.HWND(self._hwnd), hotkey_id, 0, vk):
                self._registered.append(hotkey_id)
        return bool(self._registered)

    def unregister(self) -> None:
        if sys.platform != "win32" or not self._hwnd:
            return
        user32 = ctypes.windll.user32
        for hotkey_id in self._registered:
            user32.UnregisterHotKey(wintypes.HWND(self._hwnd), hotkey_id)
        self._registered = []

    def _dispatch(self, hotkey_id: int) -> None:
        if hotkey_id == 1:
            self.play_pause.emit()
        elif hotkey_id == 2:
            self.next_track.emit()
        elif hotkey_id == 3:
            self.prev_track.emit()
        elif hotkey_id == 4:
            self.stop.emit()

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt override)
        try:
            if sys.platform == "win32" and bytes(event_type) == b"windows_generic_MSG":
                msg = _MSG.from_address(int(message))
                if msg.message == _WM_HOTKEY:
                    self._dispatch(int(msg.wParam))
        except Exception:
            pass
        return False, 0
