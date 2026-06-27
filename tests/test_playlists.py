def test_dynamic_tag_counts_are_profile_scoped(monkeypatch) -> None:
    from fluxtuner.core import playlists

    seen_profile_name = None

    def fake_load_favorites(*, profile_name: str | None = None):
        nonlocal seen_profile_name
        seen_profile_name = profile_name
        return [
            {"name": "Work Radio", "favorite_tags": ["focus", "office"]},
            {"name": "Another Work Radio", "favorite_tags": ["focus"]},
        ]

    monkeypatch.setattr(playlists, "load_favorites", fake_load_favorites)

    assert playlists.get_tag_counts(profile_name="work") == [
        ("focus", 2),
        ("office", 1),
    ]
    assert seen_profile_name == "work"


def test_dynamic_playlist_by_tag_is_profile_scoped(monkeypatch) -> None:
    from fluxtuner.core import playlists

    seen_profile_name = None

    def fake_load_favorites(*, profile_name: str | None = None):
        nonlocal seen_profile_name
        seen_profile_name = profile_name
        return [
            {"name": "Work Radio", "favorite_tags": ["focus"]},
            {"name": "Default Radio", "favorite_tags": ["home"]},
        ]

    monkeypatch.setattr(playlists, "load_favorites", fake_load_favorites)

    assert playlists.get_by_tag("focus", profile_name="work") == [
        {"name": "Work Radio", "favorite_tags": ["focus"]}
    ]
    assert seen_profile_name == "work"
