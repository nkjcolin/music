from app.core import history


def _isolate(tmp_path, monkeypatch):
    target = tmp_path / "history.json"
    monkeypatch.setattr(history, "history_path", lambda: str(target))
    return target


def test_add_and_load_most_recent_first(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    history.add_entry("A", str(tmp_path / "a.mp3"), "u/a", "audio")
    history.add_entry("B", str(tmp_path / "b.mp3"), "u/b", "video")
    names = [e["name"] for e in history.load()]
    assert names == ["B", "A"]


def test_dedup_by_path_moves_to_front(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    path_a = str(tmp_path / "a.mp3")
    history.add_entry("A", path_a, "u/a", "audio")
    history.add_entry("B", str(tmp_path / "b.mp3"), "u/b", "video")
    history.add_entry("A again", path_a, "u/a", "audio")
    entries = history.load()
    assert len(entries) == 2
    assert entries[0]["path"] == path_a and entries[0]["name"] == "A again"


def test_cap_at_max(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    for i in range(history._MAX + 25):
        history.add_entry(f"S{i}", str(tmp_path / f"{i}.mp3"), f"u/{i}", "audio")
    assert len(history.load()) == history._MAX


def test_clear(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    history.add_entry("A", str(tmp_path / "a.mp3"), "u/a", "audio")
    history.clear()
    assert history.load() == []
