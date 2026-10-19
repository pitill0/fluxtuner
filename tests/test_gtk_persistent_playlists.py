from __future__ import annotations

import pytest

from fluxtuner.gui.gtk_view_state import ViewState


def test_saved_playlist_replaces_active_tag_filter() -> None:
    state = ViewState()
    state.show_tag_playlist("jazz")

    state.show_playlist("Morning")

    assert state.current_view == "playlist"
    assert state.active_playlist_name == "Morning"
    assert state.active_playlist_tag is None


def test_opening_another_saved_playlist_replaces_previous_name() -> None:
    state = ViewState()
    state.show_playlist("Morning")

    state.show_playlist("Evening")

    assert state.current_view == "playlist"
    assert state.active_playlist_name == "Evening"


@pytest.mark.parametrize(
    ("method", "arguments", "expected_view", "expected_tag"),
    [
        ("show_search", (), "search", None),
        ("show_favorites", (), "favorites", None),
        ("show_history", (), "history", None),
        ("show_tag_playlist", ("jazz",), "tag_playlist", "jazz"),
    ],
)
def test_leaving_saved_playlist_clears_its_active_name(
    method: str,
    arguments: tuple[str, ...],
    expected_view: str,
    expected_tag: str | None,
) -> None:
    state = ViewState()
    state.show_playlist("Morning")

    getattr(state, method)(*arguments)

    assert state.current_view == expected_view
    assert state.active_playlist_name is None
    assert state.active_playlist_tag == expected_tag


@pytest.fixture
def playlist_store(tmp_path, monkeypatch):
    from fluxtuner.core import db, favorites, manual_playlists
    from fluxtuner.core.profiles import resolve_profile_id

    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(favorites, "LEGACY_FAVORITES_FILE", tmp_path / "legacy-favorites.json")
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    monkeypatch.setattr(
        manual_playlists, "LEGACY_PLAYLISTS_FILE", tmp_path / "legacy-playlists.json"
    )
    manual_playlists.create_playlist("Morning")
    manual_playlists.create_playlist("Work only", profile_name="work")
    with db.connect(tmp_path / "fluxtuner.db") as conn:
        default_id = db.ensure_default_profile(conn)
        work_id = resolve_profile_id(conn, profile_name="work")
        conn.commit()
    return default_id, work_id


def test_picker_captures_station_and_profile_without_adding_on_open(playlist_store) -> None:
    from fluxtuner.core.favorites import load_favorites
    from fluxtuner.core.manual_playlists import get_playlist_stations
    from fluxtuner.gui.gtk_playlists import create_playlist_picker

    default_id, work_id = playlist_store
    clicked = {
        "name": "Clicked FM",
        "url": "https://example.com/clicked",
        "favorite_tags": ["jazz"],
    }
    picker = create_playlist_picker(clicked, profile_id=default_id)
    assert picker.names == ("Morning",)
    assert load_favorites(profile_id=default_id) == []

    clicked["name"] = "Changed selection"
    clicked["url"] = "https://example.com/other"
    clicked["favorite_tags"].append("changed")

    assert picker.add("Morning") is True
    tracks = get_playlist_stations("Morning", profile_id=default_id)
    assert len(tracks) == 1
    assert tracks[0]["name"] == "Clicked FM"
    assert tracks[0]["url"] == "https://example.com/clicked"
    assert tracks[0]["favorite_tags"] == ["jazz"]
    assert load_favorites(profile_id=work_id) == []


def test_picker_only_offers_playlists_from_captured_profile(playlist_store) -> None:
    from fluxtuner.gui.gtk_playlists import create_playlist_picker

    _, work_id = playlist_store
    picker = create_playlist_picker(
        {"name": "Work FM", "url": "https://example.com/work"},
        profile_id=work_id,
    )
    assert picker.names == ("Work only",)
    with pytest.raises(ValueError, match="offered playlists"):
        picker.add("Morning")
    assert picker.add("Work only") is True


def test_picker_does_not_recreate_deleted_playlist_or_add_favorite(playlist_store) -> None:
    from fluxtuner.core.favorites import load_favorites
    from fluxtuner.core.manual_playlists import delete_playlist, get_playlist
    from fluxtuner.gui.gtk_playlists import create_playlist_picker

    default_id, _ = playlist_store
    picker = create_playlist_picker(
        {"name": "Clicked FM", "url": "https://example.com/clicked"},
        profile_id=default_id,
    )
    assert delete_playlist("Morning", profile_id=default_id)
    with pytest.raises(ValueError, match="no longer exists"):
        picker.add("Morning")
    assert get_playlist("Morning", profile_id=default_id) is None
    assert load_favorites(profile_id=default_id) == []


def test_repeated_picker_add_does_not_duplicate_membership(playlist_store) -> None:
    from fluxtuner.core.manual_playlists import get_playlist_stations
    from fluxtuner.gui.gtk_playlists import create_playlist_picker

    default_id, _ = playlist_store
    picker = create_playlist_picker(
        {"name": "Clicked FM", "url": "https://example.com/clicked"},
        profile_id=default_id,
    )
    assert picker.add("Morning") is True
    assert picker.add("Morning") is False
    assert len(get_playlist_stations("Morning", profile_id=default_id)) == 1


def test_removing_membership_and_deleting_playlist_keep_favorite(playlist_store) -> None:
    from fluxtuner.core.favorites import load_favorites
    from fluxtuner.core.manual_playlists import (
        delete_playlist,
        get_playlist_stations,
        remove_station_from_playlist,
    )
    from fluxtuner.gui.gtk_playlists import create_playlist_picker

    default_id, _ = playlist_store
    station = {"name": "Clicked FM", "url": "https://example.com/clicked"}
    picker = create_playlist_picker(station, profile_id=default_id)
    assert picker.add("Morning")
    assert remove_station_from_playlist("Morning", station, profile_id=default_id)
    assert get_playlist_stations("Morning", profile_id=default_id) == []
    assert picker.add("Morning")
    assert delete_playlist("Morning", profile_id=default_id)
    assert [item["url"] for item in load_favorites(profile_id=default_id)] == [station["url"]]
