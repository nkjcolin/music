import pytest

# MediaKeys is a QObject; skip cleanly if a QApplication can't be created.
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.media_keys import MediaKeys  # noqa: E402


def _app():
    app = QApplication.instance()
    if app is not None:
        return app
    try:
        return QApplication([])
    except Exception as exc:  # headless runner without a usable Qt platform
        pytest.skip(f"QApplication unavailable: {exc}")


def test_dispatch_maps_hotkey_ids_to_signals():
    _app()
    mk = MediaKeys()
    fired = []
    mk.play_pause.connect(lambda: fired.append("play"))
    mk.next_track.connect(lambda: fired.append("next"))
    mk.prev_track.connect(lambda: fired.append("prev"))
    mk.stop.connect(lambda: fired.append("stop"))

    mk._dispatch(1)
    mk._dispatch(2)
    mk._dispatch(3)
    mk._dispatch(4)
    mk._dispatch(99)  # unknown id -> ignored

    assert fired == ["play", "next", "prev", "stop"]


def test_register_is_safe_without_window():
    _app()
    mk = MediaKeys()
    # No HWND -> no registration, no crash.
    assert mk.register(0) is False
    mk.unregister()  # should be a no-op
