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

    def fake_search_stations_filtered_debug(**kwargs):
        seen.update(kwargs)
        return (
            [
                {
                    "name": "Alice Radio",
                    "url": "https://example.com/alice",
                    "country": "Spain",
                    "bitrate": 128,
                }
            ],
            {"cache_hit": False, "sources": {"name": {"status": "ok"}}},
        )

    monkeypatch.setattr(
        library, "search_stations_filtered_debug", fake_search_stations_filtered_debug
    )
    payload = library.search_payload(
        query="  alice  ", country="  Spain  ", min_bitrate=128, limit=10
    )

    assert seen == {
        "query": "alice",
        "country": "Spain",
        "min_bitrate": 128,
        "limit": 10,
        "use_cache": True,
    }
    assert payload["status"] == "ok"
    assert payload["query"] == "alice"
    assert payload["country"] == "Spain"
    assert payload["min_bitrate"] == 128
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Alice Radio"
    assert "debug" not in payload


def test_search_payload_can_include_debug_metadata(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_search_stations_filtered_debug(**kwargs):
        seen.update(kwargs)
        return (
            [{"name": "Tag Radio", "url": "https://example.com/tag", "tags": "rock"}],
            {
                "query": "rock",
                "name_results": 1,
                "tag_results": 1,
                "returned_results": 1,
                "sources": {
                    "name": {"status": "ok"},
                    "tag": {"status": "ok"},
                },
            },
        )

    monkeypatch.setattr(
        library, "search_stations_filtered_debug", fake_search_stations_filtered_debug
    )
    payload = library.search_payload(
        query=" rock ", country=" ", min_bitrate=0, limit=25, debug=True
    )

    assert seen == {
        "query": "rock",
        "country": None,
        "min_bitrate": None,
        "limit": 25,
        "use_cache": False,
    }
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["stations"][0]["tags"] == "rock"
    assert payload["debug"] == {
        "query": "rock",
        "name_results": 1,
        "tag_results": 1,
        "returned_results": 1,
        "sources": {
            "name": {"status": "ok"},
            "tag": {"status": "ok"},
        },
    }


def test_search_payload_reports_partial_when_sources_are_mixed(monkeypatch) -> None:
    monkeypatch.setattr(
        library,
        "search_stations_filtered_debug",
        lambda **_kwargs: (
            [{"name": "Tag Radio", "url": "https://example.com/tag"}],
            {
                "sources": {
                    "name": {"status": "request_error"},
                    "tag": {"status": "ok"},
                }
            },
        ),
    )

    payload = library.search_payload(query="rock", country="", min_bitrate=0, limit=25)
    assert payload["status"] == "partial"
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Tag Radio"
    assert "debug" not in payload


def test_search_payload_reports_unavailable_when_all_sources_fail(monkeypatch) -> None:
    monkeypatch.setattr(
        library,
        "search_stations_filtered_debug",
        lambda **_kwargs: (
            [],
            {
                "sources": {
                    "name": {"status": "request_error"},
                    "tag": {"status": "http_error"},
                }
            },
        ),
    )

    payload = library.search_payload(query="rock", country="", min_bitrate=0, limit=25)
    assert payload["status"] == "unavailable"
    assert payload["count"] == 0
    assert payload["stations"] == []


def test_search_payload_reports_ok_for_cached_results(monkeypatch) -> None:
    def fake_search_stations_filtered_debug(**kwargs):
        assert kwargs["use_cache"] is True
        return (
            [{"name": "Cached Radio", "url": "https://example.com/cached"}],
            {"cache_hit": True, "sources": {}},
        )

    monkeypatch.setattr(
        library, "search_stations_filtered_debug", fake_search_stations_filtered_debug
    )
    payload = library.search_payload(query="rock", country="", min_bitrate=0, limit=25)
    assert payload["status"] == "ok"
    assert payload["count"] == 1


def test_search_payload_omits_empty_optional_filters(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_search_stations_filtered_debug(**kwargs):
        seen.update(kwargs)
        return [], {"cache_hit": False, "sources": {}}

    monkeypatch.setattr(
        library, "search_stations_filtered_debug", fake_search_stations_filtered_debug
    )
    payload = library.search_payload(query="", country="  ", min_bitrate=0, limit=25)

    assert seen == {
        "query": "",
        "country": None,
        "min_bitrate": None,
        "limit": 25,
        "use_cache": True,
    }
    assert payload == {
        "status": "ok",
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
