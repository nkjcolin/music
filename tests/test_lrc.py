import os

from app.core import lrc


def test_parse_lrc_basic_and_sorted():
    parsed = lrc.parse_lrc("[ti:Song]\n[00:03.50]World\n[00:01.00]Hello")
    assert parsed == [(1000, "Hello"), (3500, "World")]


def test_parse_lrc_multiple_timestamps_per_line():
    parsed = lrc.parse_lrc("[00:03.50][00:07.00]Repeat")
    assert (3500, "Repeat") in parsed and (7000, "Repeat") in parsed


def test_centiseconds_and_milliseconds():
    assert lrc.parse_lrc("[00:01.5]a") == [(1500, "a")]
    assert lrc.parse_lrc("[00:01.123]a") == [(1123, "a")]
    assert lrc.parse_lrc("[00:01]a") == [(1000, "a")]


def test_sidecar_path_is_in_lyrics_subfolder():
    p = lrc.sidecar_path(os.path.join("C:", "Music", "Song.mp3"))
    assert p.replace("\\", "/").endswith("Music/Lyrics/Song.lrc")


def test_load_synced_finds_subfolder_then_sibling(tmp_path):
    media = tmp_path / "Track.mp3"
    media.write_text("x")
    # sibling (legacy) location
    (tmp_path / "Track.lrc").write_text("[00:02.00]legacy")
    assert lrc.load_synced(str(media)) == [(2000, "legacy")]
    # subfolder takes precedence
    lyr = tmp_path / "Lyrics"
    lyr.mkdir()
    (lyr / "Track.lrc").write_text("[00:01.00]new")
    assert lrc.load_synced(str(media)) == [(1000, "new")]
