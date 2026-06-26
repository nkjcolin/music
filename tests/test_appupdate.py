from app.core import appupdate


def test_parse_strips_v_prefix_and_handles_junk():
    assert appupdate._parse("v2.0.1") == (2, 0, 1)
    assert appupdate._parse("2.0") == (2, 0)
    assert appupdate._parse("v2.0.0-beta") == (2, 0, 0)


def test_is_newer():
    assert appupdate.is_newer("2.0.1", "2.0.0")
    assert appupdate.is_newer("v2.1.0", "2.0.9")
    assert not appupdate.is_newer("2.0.0", "2.0.0")
    assert not appupdate.is_newer("1.9.9", "2.0.0")


def test_is_newer_handles_differing_lengths():
    assert appupdate.is_newer("2.0.0.1", "2.0.0")
    assert not appupdate.is_newer("2.0", "2.0.1")


def test_apply_update_swaps_in_place_without_shell(tmp_path, monkeypatch):
    cur = tmp_path / "Songtify.exe"
    cur.write_text("OLD")
    new = tmp_path / "Songtify.update.exe"
    new.write_text("NEW")

    monkeypatch.setattr(appupdate, "is_frozen", lambda: True)
    monkeypatch.setattr(appupdate.sys, "executable", str(cur))
    monkeypatch.setattr(appupdate.subprocess, "Popen", lambda *a, **k: None)

    assert appupdate.apply_update(str(new)) is True
    assert cur.read_text() == "NEW"                 # new build is in place
    assert (tmp_path / "Songtify.exe.old").read_text() == "OLD"
    assert not new.exists()                          # update file consumed

    appupdate.cleanup_old()
    assert not (tmp_path / "Songtify.exe.old").exists()


def test_apply_update_noop_when_not_frozen(monkeypatch):
    monkeypatch.setattr(appupdate, "is_frozen", lambda: False)
    assert appupdate.apply_update("anything") is False
