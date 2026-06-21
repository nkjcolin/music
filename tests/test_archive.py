import json

from app.core.archive import Archive, archive_key


def test_archive_key_from_extractor_and_id():
    assert archive_key({"extractor_key": "Youtube", "id": "abc123"}) == "youtube abc123"


def test_record_and_valid_path(tmp_path):
    idx = tmp_path / "index.json"
    media = tmp_path / "song.mp3"
    media.write_text("x")
    arc = Archive(str(idx))
    arc.record("k", str(media))
    assert arc.valid_path("k") == str(media)


def test_deleted_file_is_not_a_duplicate_and_is_pruned(tmp_path):
    idx = tmp_path / "index.json"
    media = tmp_path / "song.mp3"
    media.write_text("x")
    arc = Archive(str(idx))
    arc.record("k", str(media))
    media.unlink()  # user deletes the file
    assert arc.valid_path("k") is None
    assert "k" not in json.loads(idx.read_text())


def test_missing_key_returns_none(tmp_path):
    arc = Archive(str(tmp_path / "index.json"))
    assert arc.valid_path("nope") is None
