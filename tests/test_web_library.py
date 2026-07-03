# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from fluxtuner.core import favorites, history, manual_playlists
from fluxtuner.web import library


def configure_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", tmp_path / "playlists.json")


def test_search_payload_normalizes_filters(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_search_stations_filtered(**kwargs):
        seen.update(kwargs)
        return [
            {
                "name": "Alice Radio",
                "url": "https://example.com/alice",
                "country": "Spain",
                "bitrate": 128,
            }
        ]

    monkeypatch.setattr(library, "search_stations_filtered", fake_search_stations_filtered)

    payload = library.search_payload(
        query="  alice  ",
        country="  Spain  ",
        min_bitrate=128,
        limit=10,
    )

    assert seen == {
        "query": "alice",
        "country": "Spain",
        "min_bitrate": 128,
        "limit": 10,
    }
    assert payload["query"] == "alice"
    assert payload["country"] == "Spain"
    assert payload["min_bitrate"] == 128
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Alice Radio"


def test_search_payload_omits_empty_optional_filters(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_search_stations_filtered(**kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(library, "search_stations_filtered", fake_search_stations_filtered)

    payload = library.search_payload(query="", country="  ", min_bitrate=0, limit=25)

    assert seen == {"query": "", "country": None, "min_bitrate": None, "limit": 25}
    assert payload == {
        "query": "",
        "country": "",
        "min_bitrate": 0,
        "limit": 25,
        "count": 0,
        "stations": [],
    }


def test_history_payload_limits_and_serializes_stations(tmp_path, monkeypatch) -> None:
    configure_files(tmp_path, monkeypatch)

    for index in range(3):
        library.record_history_payload(
            {"name": f"Station {index}", "url": f"https://example.com/{index}"},
            user_id=1,
            profile_name="default",
        )

    payload = library.history_payload(user_id=1, profile_name="default", limit=2)

    assert payload["count"] == 2
    assert len(payload["stations"]) == 2
    assert payload["stations"][0]["name"] == "Station 2"


def test_create_favorite_payload_adds_station(tmp_path, monkeypatch) -> None:
    configure_files(tmp_path, monkeypatch)

    payload = library.create_favorite_payload(
        {"name": "Alice Radio", "url": "https://example.com/alice"},
        user_id=1,
        profile_name="default",
    )

    assert payload["status"] == "ok"
    assert payload["added"] is True
    favorites_payload = library.favorites_payload(user_id=1, profile_name="default")
    assert favorites_payload["count"] == 1
    assert favorites_payload["stations"][0]["name"] == "Alice Radio"


def test_playlists_payload_includes_station_count(tmp_path, monkeypatch) -> None:
    configure_files(tmp_path, monkeypatch)

    library.create_playlist_payload("Morning", user_id=1, profile_name="default")
    library.add_station_to_playlist_payload(
        "Morning",
        {"name": "Alice Radio", "url": "https://example.com/alice"},
        user_id=1,
        profile_name="default",
    )

    payload = library.playlists_payload(user_id=1, profile_name="default")

    assert payload == {"count": 1, "playlists": [{"name": "Morning", "count": 1}]}
    stations = library.playlist_stations_payload("Morning", user_id=1, profile_name="default")
    assert stations["count"] == 1
    assert stations["stations"][0]["name"] == "Alice Radio"
