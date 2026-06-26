import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


def _app():
    app = QApplication.instance()
    if app is not None:
        return app
    try:
        return QApplication([])
    except Exception as exc:  # headless runner without a usable Qt platform
        pytest.skip(f"QApplication unavailable: {exc}")


class _FakeSettings:
    """Minimal stand-in so the widget doesn't touch real QSettings."""

    def __init__(self, folder):
        self.folder = folder
        self.player_shuffle = False
        self.player_repeat = "off"


def test_library_widget_builds_and_lists(tmp_path):
    # Guards the regression where the UI wasn't built in __init__ and refresh()
    # crashed on a missing path_label.
    _app()
    from app.ui.library_widget import LibraryWidget
    (tmp_path / "a.mp3").write_text("x")
    (tmp_path / "b.flac").write_text("x")

    lw = LibraryWidget(_FakeSettings(str(tmp_path)))
    assert hasattr(lw, "path_label")
    lw.refresh()
    assert lw.path_label.text() == str(tmp_path)
    assert sorted(r.info["stem"] for r in lw._rows) == ["a", "b"]


def test_library_and_player_use_same_folder(tmp_path):
    _app()
    from app.ui.library_widget import LibraryWidget
    from app.ui.player_widget import PlayerWidget
    (tmp_path / "song.mp3").write_text("x")

    settings = _FakeSettings(str(tmp_path))
    lib = LibraryWidget(settings)
    lib.refresh()
    player = PlayerWidget(settings)
    if player.available:          # only when a Qt multimedia backend exists
        player.refresh_songs()
        import os
        assert os.path.dirname(player._song_paths[0]) == str(tmp_path)
    assert lib.path_label.text() == str(tmp_path)
