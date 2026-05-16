from typing import Any

from fluxtuner.core import api


def test_normalize_station_applies_defaults() -> None:
    station = api.normalize_station({})

    assert station == {
        "name": "Unknown station",
        "url": "",
        "url_resolved": "",
        "country": "Unknown",
        "countrycode": "",
        "tags": "",
        "codec": "",
        "bitrate": 0,
        "homepage": "",
        "language": "",
    }


def test_country_api_filters_detects_country_code() -> None:
    assert api._country_api_filters(" es ") == (None, "ES")
    assert api._country_api_filters("Spain") == ("Spain", None)
    assert api._country_api_filters(None) == (None, None)


def test_search_stations_filtered_returns_empty_for_empty_filters() -> None:
    assert api.search_stations_filtered("", use_cache=False) == []


def test_search_stations_filtered_uses_cache(monkeypatch) -> None:
    cached = [{"name": "Cached Radio", "url": "https://example.com/cached"}]

    monkeypatch.setattr(api, "get_cached_search", lambda _key: cached)

    def fail_search(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise AssertionError("search_stations should not be called when cache hits")

    monkeypatch.setattr(api, "search_stations", fail_search)

    assert api.search_stations_filtered("rock") == cached


def test_search_stations_filtered_deduplicates_and_filters_results(monkeypatch) -> None:
    calls = []

    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
        calls.append(kwargs)
        if "name" in kwargs:
            return [
                {
                    "name": "Rock One",
                    "url": "https://example.com/rock",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 128,
                },
                {
                    "name": "Rock Duplicate",
                    "url": "https://example.com/rock",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 128,
                },
                {
                    "name": "Low Bitrate",
                    "url": "https://example.com/low",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 64,
                },
            ]

        return [
            {
                "name": "Rock Tag",
                "url": "https://example.com/tag",
                "country": "Spain",
                "countrycode": "ES",
                "tags": "rock",
                "bitrate": 192,
            },
            {
                "name": "Wrong Country",
                "url": "https://example.com/wrong",
                "country": "France",
                "countrycode": "FR",
                "tags": "rock",
                "bitrate": 192,
            },
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)

    stored_cache = {}

    def fake_set_cached_search(key: str, results: list[dict[str, Any]]) -> None:
        stored_cache[key] = results

    monkeypatch.setattr(api, "set_cached_search", fake_set_cached_search)

    results = api.search_stations_filtered(
        "rock",
        country="ES",
        min_bitrate=128,
        limit=10,
        use_cache=True,
    )

    assert [station["name"] for station in results] == ["Rock One", "Rock Tag"]
    assert calls[0]["name"] == "rock"
    assert calls[0]["countrycode"] == "ES"
    assert calls[1]["tag"] == "rock"
    assert calls[1]["countrycode"] == "ES"
    assert len(stored_cache) == 1


def test_search_stations_filtered_falls_back_to_broad_search_when_country_too_strict(
    monkeypatch,
) -> None:
    calls = []

    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
        calls.append(kwargs)
        if kwargs.get("country") == "Atlantis":
            return []
        return [
            {
                "name": "Atlantis Radio",
                "url": "https://example.com/atlantis",
                "country": "Atlantis",
                "countrycode": "AT",
                "tags": "ambient",
                "bitrate": 128,
            }
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)

    results = api.search_stations_filtered(
        "ambient",
        country="Atlantis",
        use_cache=False,
    )

    assert [station["name"] for station in results] == ["Atlantis Radio"]
    assert calls[0]["country"] == "Atlantis"
    assert calls[1]["country"] == "Atlantis"
    assert "country" not in calls[2]
    assert "country" not in calls[3]
