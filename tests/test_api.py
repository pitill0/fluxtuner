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


def test_search_relevance_rank_orders_match_kinds() -> None:
    query = "  ROCK   FM "

    assert api._search_relevance_rank({"name": "Rock FM"}, query) == 0
    assert api._search_relevance_rank({"name": "Rock FM Classic"}, query) == 1
    assert api._search_relevance_rank({"name": "Best Rock FM Radio"}, query) == 2
    assert (
        api._search_relevance_rank(
            {"name": "Music Station", "tags": "pop,rock   fm,classic"},
            query,
        )
        == 3
    )
    assert (
        api._search_relevance_rank(
            {"name": "Jazz Station", "tags": "jazz"},
            query,
        )
        == 4
    )


def test_search_relevance_rank_is_neutral_without_query() -> None:
    assert api._search_relevance_rank({"name": "Any Station"}, "") == 0
    assert api._search_relevance_rank({"name": "Any Station"}, "   ") == 0


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


def test_search_stations_filtered_debug_reports_source_counts(monkeypatch) -> None:
    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
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

    results, debug = api.search_stations_filtered_debug(
        "rock",
        country="ES",
        min_bitrate=128,
        limit=10,
        use_cache=False,
    )

    assert [station["name"] for station in results] == ["Rock One", "Rock Tag"]
    assert debug == {
        "query": "rock",
        "country": "ES",
        "min_bitrate": 128,
        "limit": 10,
        "api_limit": 200,
        "cache_hit": False,
        "cache_bypassed": True,
        "name_results": 3,
        "tag_results": 2,
        "country_results": 0,
        "fallback_name_results": 0,
        "fallback_tag_results": 0,
        "fallback_country_results": 0,
        "raw_results": 5,
        "name_returned_results": 1,
        "tag_returned_results": 1,
        "country_returned_results": 0,
        "fallback_name_returned_results": 0,
        "fallback_tag_returned_results": 0,
        "fallback_country_returned_results": 0,
        "deduped_results": 1,
        "country_filtered_results": 1,
        "bitrate_filtered_results": 1,
        "returned_results": 2,
        "sources": {
            "name": {
                "status": "ok",
                "elapsed_ms": None,
                "http_status": None,
                "error_kind": None,
                "fetched": 3,
                "skipped_items": 0,
            },
            "tag": {
                "status": "ok",
                "elapsed_ms": None,
                "http_status": None,
                "error_kind": None,
                "fetched": 2,
                "skipped_items": 0,
            },
        },
    }


def test_search_stations_filtered_ranks_exact_name_before_earlier_candidates(
    monkeypatch,
) -> None:
    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
        if "name" in kwargs:
            return [
                {
                    "name": "Rock Around the Clock",
                    "url": "https://example.com/contains",
                    "tags": "oldies",
                },
                {"name": "Rock Radio", "url": "https://example.com/prefix", "tags": "rock"},
            ]
        return [
            {"name": "Rock", "url": "https://example.com/exact", "tags": "rock"},
            {"name": "Music Station", "url": "https://example.com/tag", "tags": "rock"},
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)
    results = api.search_stations_filtered("rock", limit=2, use_cache=False)

    assert [station["name"] for station in results] == [
        "Rock",
        "Rock Around the Clock",
    ]


def test_search_stations_filtered_preserves_original_order_for_equal_rank(monkeypatch) -> None:
    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
        if "name" in kwargs:
            return [
                {"name": "Rock One", "url": "https://example.com/one"},
                {"name": "Rock Two", "url": "https://example.com/two"},
            ]
        return [
            {"name": "Rock Three", "url": "https://example.com/three"},
            {"name": "Rock Four", "url": "https://example.com/four"},
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)
    results = api.search_stations_filtered("rock", limit=4, use_cache=False)

    assert [station["name"] for station in results] == [
        "Rock One",
        "Rock Three",
        "Rock Two",
        "Rock Four",
    ]


def test_search_stations_filtered_returns_empty_for_negative_limit(monkeypatch) -> None:
    def fake_search_stations(**_kwargs: Any) -> list[dict[str, Any]]:
        return [{"name": "Rock", "url": "https://example.com/rock"}]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)

    results, debug = api.search_stations_filtered_debug(
        "rock",
        limit=-1,
        use_cache=False,
    )

    assert results == []
    assert debug["returned_results"] == 0
    assert debug["name_returned_results"] == 0
    assert debug["tag_returned_results"] == 0


def test_search_stations_filtered_interleaves_name_and_tag_results(monkeypatch) -> None:
    def fake_search_stations(**kwargs: Any) -> list[dict[str, Any]]:
        if "name" in kwargs:
            return [
                {
                    "name": "Name One",
                    "url": "https://example.com/name-one",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 128,
                },
                {
                    "name": "Name Two",
                    "url": "https://example.com/name-two",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 128,
                },
            ]

        return [
            {
                "name": "Tag One",
                "url": "https://example.com/tag-one",
                "country": "Spain",
                "countrycode": "ES",
                "tags": "rock",
                "bitrate": 128,
            }
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)

    results = api.search_stations_filtered("rock", limit=2, use_cache=False)

    assert [station["name"] for station in results] == ["Name One", "Tag One"]


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
        status_code: int | None = 200,
    ) -> None:
        self.data = data
        self.status_error = status_error
        self.json_error = json_error
        self.status_code = status_code

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


def test_search_stations_diagnostics_distinguish_valid_empty_response(monkeypatch) -> None:
    monkeypatch.setattr(api.requests, "get", lambda *_args, **_kwargs: FakeResponse([]))
    diagnostics: dict[str, Any] = {}

    assert api.search_stations(name="test", _diagnostics=diagnostics) == []

    assert diagnostics["status"] == "ok"
    assert diagnostics["error_kind"] is None
    assert diagnostics["fetched"] == 0
    assert diagnostics["http_status"] == 200
    assert isinstance(diagnostics["elapsed_ms"], float)


def test_search_stations_diagnostics_capture_request_error(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise requests.Timeout("timeout")

    monkeypatch.setattr(api.requests, "get", fake_get)
    diagnostics: dict[str, Any] = {}

    assert api.search_stations(name="test", _diagnostics=diagnostics) == []

    assert diagnostics["status"] == "request_error"
    assert diagnostics["error_kind"] == "request_error"
    assert diagnostics["http_status"] is None


def test_search_stations_diagnostics_capture_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(
            [],
            status_error=requests.HTTPError("unavailable"),
            status_code=503,
        ),
    )
    diagnostics: dict[str, Any] = {}

    assert api.search_stations(name="test", _diagnostics=diagnostics) == []

    assert diagnostics["status"] == "http_error"
    assert diagnostics["error_kind"] == "http_error"
    assert diagnostics["http_status"] == 503


def test_search_stations_diagnostics_capture_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(json_error=ValueError("invalid")),
    )
    diagnostics: dict[str, Any] = {}

    assert api.search_stations(name="test", _diagnostics=diagnostics) == []

    assert diagnostics["status"] == "invalid_json"
    assert diagnostics["error_kind"] == "invalid_json"


def test_search_stations_diagnostics_capture_unexpected_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse({"unexpected": "object"}),
    )
    diagnostics: dict[str, Any] = {}

    assert api.search_stations(name="test", _diagnostics=diagnostics) == []

    assert diagnostics["status"] == "unexpected_payload"
    assert diagnostics["error_kind"] == "unexpected_payload"


def test_search_stations_filtered_debug_preserves_partial_request_outcomes(
    monkeypatch,
) -> None:
    def fake_get(*_args: Any, **kwargs: Any) -> FakeResponse:
        params = kwargs["params"]
        if "name" in params:
            raise requests.Timeout("name request timed out")
        return FakeResponse(
            [
                {
                    "name": "Tag Result",
                    "url": "https://example.com/tag-result",
                    "country": "Spain",
                    "countrycode": "ES",
                    "tags": "rock",
                    "bitrate": 128,
                }
            ]
        )

    monkeypatch.setattr(api.requests, "get", fake_get)

    results, debug = api.search_stations_filtered_debug(
        "rock",
        limit=10,
        use_cache=False,
    )

    assert [station["name"] for station in results] == ["Tag Result"]
    assert debug["sources"]["name"]["status"] == "request_error"
    assert debug["sources"]["name"]["fetched"] == 0
    assert debug["sources"]["tag"]["status"] == "ok"
    assert debug["sources"]["tag"]["fetched"] == 1
    assert debug["returned_results"] == 1


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


def test_repeated_identical_filtered_search_uses_cached_results(monkeypatch) -> None:
    calls = 0

    def fake_search_stations(**_kwargs: Any) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return [
            {
                "name": "Cached Candidate",
                "url": "https://example.com/cached",
                "url_resolved": "https://example.com/cached",
                "country": "Spain",
                "countrycode": "ES",
                "tags": "rock",
                "bitrate": 128,
            }
        ]

    memory_cache: dict[str, list[dict[str, Any]]] = {}

    def fake_get_cached_search(key: str) -> list[dict[str, Any]] | None:
        return memory_cache.get(key)

    def fake_set_cached_search(key: str, results: list[dict[str, Any]]) -> None:
        memory_cache[key] = results

    monkeypatch.setattr(api, "search_stations", fake_search_stations)
    monkeypatch.setattr(api, "get_cached_search", fake_get_cached_search)
    monkeypatch.setattr(api, "set_cached_search", fake_set_cached_search)

    first = api.search_stations_filtered("rock", country="ES", min_bitrate=128, limit=10)
    second = api.search_stations_filtered("rock", country="ES", min_bitrate=128, limit=10)

    assert first == second
    assert calls == 2


def test_search_stations_filtered_cache_miss_stores_filtered_normalized_results(
    monkeypatch,
) -> None:
    stored = {}

    def fake_search_stations(**_kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "name": "Valid High",
                "url": "https://example.com/high",
                "url_resolved": "https://example.com/high-resolved",
                "country": "Spain",
                "countrycode": "ES",
                "tags": "jazz",
                "bitrate": 192,
            },
            {
                "name": "Too Low",
                "url": "https://example.com/low",
                "country": "Spain",
                "countrycode": "ES",
                "tags": "jazz",
                "bitrate": 64,
            },
            {
                "name": "Wrong Country",
                "url": "https://example.com/france",
                "country": "France",
                "countrycode": "FR",
                "tags": "jazz",
                "bitrate": 192,
            },
        ]

    monkeypatch.setattr(api, "search_stations", fake_search_stations)
    monkeypatch.setattr(api, "get_cached_search", lambda _key: None)
    monkeypatch.setattr(
        api, "set_cached_search", lambda key, results: stored.setdefault(key, results)
    )

    results = api.search_stations_filtered("jazz", country="ES", min_bitrate=128, limit=10)

    assert results == [
        {
            "name": "Valid High",
            "url": "https://example.com/high",
            "url_resolved": "https://example.com/high-resolved",
            "country": "Spain",
            "countrycode": "ES",
            "tags": "jazz",
            "codec": "",
            "bitrate": 192,
            "homepage": "",
            "language": "",
        }
    ]
    assert list(stored.values()) == [results]


def test_search_stations_filtered_with_cache_disabled_does_not_read_or_write_cache(
    monkeypatch,
) -> None:
    def fail_get_cache(_key: str) -> None:
        raise AssertionError("cache should not be read when use_cache=False")

    def fail_set_cache(_key: str, _results: list[dict[str, Any]]) -> None:
        raise AssertionError("cache should not be written when use_cache=False")

    monkeypatch.setattr(api, "get_cached_search", fail_get_cache)
    monkeypatch.setattr(api, "set_cached_search", fail_set_cache)
    monkeypatch.setattr(
        api,
        "search_stations",
        lambda **_kwargs: [
            {
                "name": "No Cache",
                "url": "https://example.com/no-cache",
                "country": "Spain",
                "countrycode": "ES",
                "bitrate": 128,
            }
        ],
    )

    results = api.search_stations_filtered("rock", use_cache=False)

    assert [station["name"] for station in results] == ["No Cache"]


def test_search_stations_filtered_empty_filters_do_not_read_cache_or_network(monkeypatch) -> None:
    def fail_get_cache(_key: str) -> None:
        raise AssertionError("cache should not be read for empty filters")

    def fail_search(**_kwargs: Any) -> None:
        raise AssertionError("network search should not run for empty filters")

    monkeypatch.setattr(api, "get_cached_search", fail_get_cache)
    monkeypatch.setattr(api, "search_stations", fail_search)

    assert api.search_stations_filtered("", country=" ", min_bitrate=None) == []
