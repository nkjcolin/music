import os

from app.core import naming


def test_default_template_uses_editable_name():
    out = naming.build_outtmpl("D", "{name}", "Daft Punk - One More Time")
    assert out.endswith("Daft Punk - One More Time.%(ext)s")


def test_name_is_sanitized():
    out = naming.build_outtmpl("D", "{name}", "A/B:C")
    assert out.endswith("A_B_C.%(ext)s")


def test_metadata_tokens_map_to_ytdlp_fields():
    out = naming.build_outtmpl("D", "{artist}/{album}/{track}", "x")
    assert "%(artist" in out and "%(album" in out and "%(track" in out
    assert out.endswith(".%(ext)s")


def test_literal_percent_is_escaped():
    out = naming.build_outtmpl("D", "{name}", "50% off")
    assert "%%" in out


def test_subfolders_use_forward_slash():
    out = naming.build_outtmpl("D", "{artist}/{name}", "Song")
    assert "/" in out.replace(os.sep, "/")


def test_display_name_prefers_artist_track():
    assert naming.display_name_from_info({"artist": "A", "track": "T"}) == "A - T"
    assert naming.display_name_from_info({"title": "Only Title"}) == "Only Title"
    assert naming.display_name_from_info({"id": "abc"}) == "abc"
