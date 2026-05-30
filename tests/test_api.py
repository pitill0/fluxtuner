import logging
from typing import Any

import requests

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


class FakeResponse:
    def __init__(
        self,
        data: Any = None,
        *,
        status_error: Exception | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.data = data
        self.status_error = status_error
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def json(self) -> Any:
        if self.json_error:
            raise self.json_error
        return self.data


def test_search_stations_returns_api_items(monkeypatch) -> None:
    captured = {}

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(
            [
                {
                    "name": "Test Radio",
                    "url": "https://example.com/stream",
                }
            ]
        )

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == [
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        }
    ]

    assert captured["url"] == f"{api.BASE_URL}/stations/search"
    assert captured["kwargs"]["params"]["name"] == "test"
    assert captured["kwargs"]["headers"] == api.DEFAULT_HEADERS
    assert captured["kwargs"]["timeout"] == api.DEFAULT_TIMEOUT


def test_search_stations_returns_empty_list_on_request_error(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise requests.Timeout("timeout")

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == []


def test_search_stations_returns_empty_list_on_http_error(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(
            [],
            status_error=requests.HTTPError("server error"),
        )

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == []


def test_search_stations_returns_empty_list_on_invalid_json(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(json_error=ValueError("invalid json"))

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == []


def test_search_stations_returns_empty_list_for_non_list_json(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse({"unexpected": "object"})

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == []


def test_search_stations_filters_non_dict_items(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(
            [
                {"name": "Valid", "url": "https://example.com/stream"},
                "not a dict",
                None,
                ["also invalid"],
            ]
        )

    monkeypatch.setattr(api.requests, "get", fake_get)

    assert api.search_stations(name="test") == [
        {"name": "Valid", "url": "https://example.com/stream"}
    ]


def test_search_stations_uppercases_countrycode(monkeypatch) -> None:
    captured = {}

    def fake_get(_url: str, **kwargs: Any) -> FakeResponse:
        captured["params"] = kwargs["params"]
        return FakeResponse([])

    monkeypatch.setattr(api.requests, "get", fake_get)

    api.search_stations(countrycode="es")

    assert captured["params"]["countrycode"] == "ES"


def test_search_stations_logs_request_error(monkeypatch, caplog) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise requests.Timeout("timeout")

    monkeypatch.setattr(api.requests, "get", fake_get)

    with caplog.at_level(logging.DEBUG):
        assert api.search_stations(name="test") == []

    assert "Radio Browser API request failed" in caplog.text


def test_search_stations_logs_invalid_json(monkeypatch, caplog) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(json_error=ValueError("invalid json"))

    monkeypatch.setattr(api.requests, "get", fake_get)

    with caplog.at_level(logging.DEBUG):
        assert api.search_stations(name="test") == []

    assert "Radio Browser API returned invalid JSON" in caplog.text


def test_search_stations_logs_unexpected_response_type(monkeypatch, caplog) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse({"unexpected": "object"})

    monkeypatch.setattr(api.requests, "get", fake_get)

    with caplog.at_level(logging.DEBUG):
        assert api.search_stations(name="test") == []

    assert "Radio Browser API returned unexpected response type" in caplog.text


def test_search_stations_filtered_logs_cache_hit(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        api,
        "get_cached_search",
        lambda _key: [{"name": "Cached", "url": "https://example.com/stream"}],
    )

    with caplog.at_level(logging.DEBUG):
        results = api.search_stations_filtered("rock")

    assert len(results) == 1
    assert "Returning 1 cached search result(s)" in caplog.text


def test_search_stations_filtered_logs_empty_filters(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        assert api.search_stations_filtered("") == []

    assert "Skipping search because no filters were provided" in caplog.text
