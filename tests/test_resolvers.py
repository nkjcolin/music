from app.core import resolvers


def test_streaming_url_detection():
    assert resolvers.is_streaming_url("https://open.spotify.com/track/abc123")
    assert resolvers.is_streaming_url("https://www.deezer.com/en/album/123")
    assert resolvers.is_streaming_url("https://music.apple.com/us/album/x/123?i=456")
    assert not resolvers.is_streaming_url("https://youtube.com/watch?v=x")


def test_find_first_url():
    assert resolvers.find_first_url("look at https://x.com/a here") == "https://x.com/a"
    assert resolvers.find_first_url("no link") is None


def test_plain_link_is_not_streaming():
    # regex-only, no network
    assert resolvers.resolve("https://youtu.be/x") is None


def test_collapse_duplicate_url():
    u = "https://www.youtube.com/watch?v=abc"
    assert resolvers.collapse_duplicate_url(u + u) == u   # doubled -> single
    assert resolvers.collapse_duplicate_url(u) == u       # single untouched
    # distinct concatenation is left alone (we only collapse exact duplicates)
    two = "https://x/a" + "https://x/b"
    assert resolvers.collapse_duplicate_url(two) == two


def test_spotify_entity_playlist():
    title, tracks = resolvers._spotify_tracks_from_entity({
        "name": "My Playlist",
        "trackList": [
            {"title": "Song A", "subtitle": "Artist A"},
            {"title": "Song B", "subtitle": "Artist B"},
        ],
    })
    assert title == "My Playlist"
    assert [t.name for t in tracks] == ["Artist A - Song A", "Artist B - Song B"]
    assert tracks[0].query == "Artist A Song A"


def test_spotify_entity_single_track():
    _, tracks = resolvers._spotify_tracks_from_entity(
        {"name": "Solo", "artists": [{"name": "Nobody"}]})
    assert tracks[0].name == "Nobody - Solo"
