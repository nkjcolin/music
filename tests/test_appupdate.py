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
