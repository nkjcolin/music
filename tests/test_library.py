import os

from app.core import library


def test_delete_media_removes_file_and_lyrics(tmp_path):
    media = tmp_path / "Song.mp3"
    media.write_text("x")
    lyr_dir = tmp_path / "Lyrics"
    lyr_dir.mkdir()
    (lyr_dir / "Song.lrc").write_text("[00:01.00]hi")

    library.delete_media(str(media))

    assert not media.exists()
    assert not (lyr_dir / "Song.lrc").exists()


def test_list_media_includes_all_audio_formats(tmp_path):
    for name in ("a.mp3", "b.flac", "c.opus", "d.wav", "e.ogg", "f.m4a",
                 "g.mp4", "skip.txt", "skip.lrc"):
        (tmp_path / name).write_text("x")
    exts = {i["ext"].lower() for i in library.list_media(str(tmp_path))}
    assert {".mp3", ".flac", ".opus", ".wav", ".ogg", ".m4a", ".mp4"} <= exts
    assert ".txt" not in exts and ".lrc" not in exts


def test_delete_media_without_lyrics(tmp_path):
    media = tmp_path / "Song.mp3"
    media.write_text("x")
    library.delete_media(str(media))
    assert not media.exists()


def test_remove_with_retry_eventually_raises(tmp_path, monkeypatch):
    # A persistently-locked file should still raise (after exhausting retries).
    target = tmp_path / "locked.mp3"
    target.write_text("x")

    def always_locked(_path):
        raise PermissionError("in use")

    monkeypatch.setattr(os, "remove", always_locked)
    monkeypatch.setattr(library.time, "sleep", lambda *_: None)  # don't actually wait
    try:
        library._remove_with_retry(str(target), attempts=3, delay=0)
        raised = False
    except PermissionError:
        raised = True
    assert raised
