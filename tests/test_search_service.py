from fluxtuner.core.search_service import SearchRequest, SearchService, search_stations


def test_search_service_delegates_normalized_request_to_backend() -> None:
    calls = []

    def backend(
        query: str,
        country: str | None = None,
        min_bitrate: int | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[dict[str, object]]:
        calls.append(
            {
                "query": query,
                "country": country,
                "min_bitrate": min_bitrate,
                "limit": limit,
                "use_cache": use_cache,
            }
        )
        return [{"name": "Test Radio", "url": "https://example.com/stream"}]

    service = SearchService(backend=backend)

    result = service.search(
        SearchRequest(
            query="  rock  ",
            country=" ES ",
            min_bitrate=-10,
            limit=0,
            use_cache=False,
        )
    )

    assert result.stations == [{"name": "Test Radio", "url": "https://example.com/stream"}]
    assert calls == [
        {
            "query": "rock",
            "country": "ES",
            "min_bitrate": 0,
            "limit": 1,
            "use_cache": False,
        }
    ]


def test_search_service_preserves_empty_query_for_filter_only_search() -> None:
    calls = []

    def backend(
        query: str,
        country: str | None = None,
        min_bitrate: int | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[dict[str, object]]:
        calls.append((query, country, min_bitrate, limit, use_cache))
        return []

    service = SearchService(backend=backend)

    result = service.search(SearchRequest(query="   ", country="Spain", min_bitrate=128))

    assert result.stations == []
    assert calls == [("", "Spain", 128, 50, True)]


def test_search_stations_convenience_wrapper_uses_service() -> None:
    class FakeService:
        def __init__(self) -> None:
            self.requests = []

        def search(self, request: SearchRequest):
            self.requests.append(request)
            return type(
                "Result",
                (),
                {"stations": [{"name": "Wrapped", "url": "https://example.com"}]},
            )()

    service = FakeService()

    results = search_stations(
        "jazz",
        country="France",
        min_bitrate=192,
        limit=25,
        use_cache=False,
        service=service,  # type: ignore[arg-type]
    )

    assert results == [{"name": "Wrapped", "url": "https://example.com"}]
    assert service.requests == [
        SearchRequest(
            query="jazz",
            country="France",
            min_bitrate=192,
            limit=25,
            use_cache=False,
        )
    ]


def test_search_request_defaults_to_radio_browser() -> None:
    request = SearchRequest(query="jazz")

    assert request.source == "radio-browser"


def test_search_request_accepts_explicit_discovery_scopes() -> None:
    for source in ("radio-browser", "local", "all"):
        request = SearchRequest(query="rock", source=source)

        assert request.source == source


def test_local_source_dispatches_with_explicit_profile(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    calls = []

    def local_backend(conn, *, profile_id, query, country, min_bitrate, limit):
        calls.append((conn, profile_id, query, country, min_bitrate, limit))
        return [{"name": "My radio", "url": "https://example.org/local"}]

    monkeypatch.setattr(search_service, "search_local_stations", local_backend)
    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(local_connection=conn, profile_id=7)
        result = service.search(
            SearchRequest(
                query="  rock  ",
                country=" ES ",
                min_bitrate=-4,
                limit=0,
                source="local",
            )
        )
        assert result.stations[0]["name"] == "My radio"
        assert calls == [(conn, 7, "rock", "ES", 0, 1)]
    finally:
        conn.close()


def test_local_source_requires_explicit_context() -> None:
    import pytest

    service = SearchService(backend=lambda *_args: [])
    with pytest.raises(ValueError, match="connection and profile"):
        service.search(SearchRequest(source="local"))


def test_combined_source_requires_explicit_context() -> None:
    import pytest

    with pytest.raises(ValueError, match="connection and profile"):
        SearchService().search(SearchRequest(source="all"))


def test_combined_search_deduplicates_urls_and_keeps_both_sources(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    remote_calls = []
    local_calls = []

    def local_backend(conn, *, profile_id, query, country, min_bitrate, limit):
        local_calls.append((conn, profile_id, query, country, min_bitrate, limit))
        return [
            {
                "name": "Rock Local",
                "url": "https://example.org/shared",
                "custom_name": "Rock",
                "favorite_tags": ["favorite"],
            },
            {"name": "Rock Two", "url": "https://example.org/local"},
        ]

    def remote_backend(query, country, min_bitrate, limit, use_cache):
        remote_calls.append((query, country, min_bitrate, limit, use_cache))
        return [
            {"name": "Rock", "url": "https://example.org/shared"},
            {"name": "Rock", "url": "https://example.org/other"},
        ]

    monkeypatch.setattr(search_service, "search_local_stations", local_backend)
    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(backend=remote_backend, local_connection=conn, profile_id=4)
        request = SearchRequest(
            query=" rock ",
            country=" ES ",
            min_bitrate=-10,
            limit=5,
            use_cache=False,
            source="all",
        )
        first = service.search(request)
        second = service.search(request)

        assert first == second
        assert len(first.stations) == 3
        assert first.total_found == 3
        assert first.source_observations == {
            "https://example.org/shared": ("local", "radio-browser"),
            "https://example.org/other": ("radio-browser",),
            "https://example.org/local": ("local",),
        }
        shared = next(
            station for station in first.stations if station["url"] == "https://example.org/shared"
        )
        assert shared["custom_name"] == "Rock"
        assert local_calls == [(conn, 4, "rock", "ES", 0, 10)] * 2
        assert remote_calls == [("rock", "ES", 0, 10, False)] * 2
    finally:
        conn.close()


def test_combined_search_limit_follows_ranking_not_source_order(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    monkeypatch.setattr(
        search_service,
        "search_local_stations",
        lambda *_args, **_kwargs: [{"name": "Jazz Somewhere", "url": "https://example.org/local"}],
    )

    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(
            backend=lambda *_args: [{"name": "Jazz", "url": "https://example.org/exact"}],
            local_connection=conn,
            profile_id=3,
        )
        result = service.search(SearchRequest(query="Jazz", limit=1, source="all"))
        assert [item["url"] for item in result.stations] == ["https://example.org/exact"]
        assert result.total_found == 2
        assert result.source_observations == {"https://example.org/exact": ("radio-browser",)}
    finally:
        conn.close()


def test_invalid_source_does_not_silently_fall_back() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown"):
        SearchService().search(SearchRequest(source="unrecognized"))  # type: ignore[arg-type]


def test_combined_search_reflects_updated_local_library(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    local_items = [
        {"name": "Jazz One", "url": "https://example.org/one"},
    ]
    calls = []

    def local_backend(conn, *, profile_id, query, country, min_bitrate, limit):
        calls.append(profile_id)
        return list(local_items)

    monkeypatch.setattr(search_service, "search_local_stations", local_backend)

    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(
            backend=lambda *_args: [],
            local_connection=conn,
            profile_id=9,
        )

        request = SearchRequest(query="Jazz", source="all")

        first = service.search(request)
        assert [item["name"] for item in first.stations] == ["Jazz One"]

        local_items[:] = [{"name": "Jazz Two", "url": "https://example.org/two"}]

        second = service.search(request)
        assert [item["name"] for item in second.stations] == ["Jazz Two"]
        assert calls == [9, 9]
    finally:
        conn.close()


def test_combined_search_filters_unsupported_before_final_limit(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service
    from fluxtuner.players.capabilities import PlayerCapabilities

    monkeypatch.setattr(
        search_service,
        "search_local_stations",
        lambda *_args, **_kwargs: [
            {
                "name": "Jazz",
                "url": "https://example.org/unsupported.flac",
                "codec": "FLAC",
            },
        ],
    )

    conn = sqlite3.connect(":memory:")
    try:
        capabilities = PlayerCapabilities(
            supported_codecs=frozenset({"mp3"}),
        )
        service = SearchService(
            backend=lambda *_args: [
                {
                    "name": "Jazz Live",
                    "url": "https://example.org/supported.mp3",
                    "codec": "MP3",
                }
            ],
            capabilities=capabilities,
            local_connection=conn,
            profile_id=5,
        )

        result = service.search(SearchRequest(query="Jazz", limit=1, source="all"))

        assert [item["name"] for item in result.stations] == ["Jazz Live"]
        assert result.total_found == 2
        assert result.unsupported_count == 1
    finally:
        conn.close()


def test_combined_remote_diagnostic_classification(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    cases = [
        ({"name": {"status": "ok"}}, "ok"),
        (
            {"name": {"status": "request_error"}, "tag": {"status": "ok"}},
            "partial_error",
        ),
        (
            {"name": {"status": "http_error"}, "tag": {"status": "invalid_json"}},
            "error",
        ),
        ({}, "not_queried"),
        ({"name": {"status": "undocumented"}}, "unknown"),
    ]

    monkeypatch.setattr(
        search_service,
        "search_local_stations",
        lambda *_args, **_kwargs: [{"name": "Local Jazz", "url": "https://example.org/local"}],
    )

    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(local_connection=conn, profile_id=4)
        for sources, expected in cases:
            calls = []

            def make_fake_debug(expected_sources, recorded_calls):
                def debug_backend(query, country, min_bitrate, limit, use_cache):
                    recorded_calls.append((query, country, min_bitrate, limit, use_cache))
                    return [], {"sources": expected_sources, "cache_hit": False}

                return debug_backend

            fake_debug = make_fake_debug(sources, calls)

            with monkeypatch.context() as patch:
                patch.setattr(search_service, "search_stations_filtered_debug", fake_debug)
                result = service.search(SearchRequest(query="jazz", source="all", use_cache=False))

            assert result.remote_status == expected
            assert [item["name"] for item in result.stations] == ["Local Jazz"]
            assert calls == [("jazz", None, None, 100, False)]
    finally:
        conn.close()


def test_combined_cached_remote_results_are_not_claimed_as_live_success(
    monkeypatch,
) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    monkeypatch.setattr(
        search_service,
        "search_local_stations",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        search_service,
        "search_stations_filtered_debug",
        lambda *_args: (
            [{"name": "Cached", "url": "https://example.org/cached"}],
            {"cache_hit": True, "sources": {}},
        ),
    )

    conn = sqlite3.connect(":memory:")
    try:
        result = SearchService(local_connection=conn, profile_id=1).search(
            SearchRequest(query="cached", source="all")
        )

        assert result.remote_status == "unknown"
        assert [item["name"] for item in result.stations] == ["Cached"]
    finally:
        conn.close()


def test_combined_custom_backend_preserves_existing_contract(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    monkeypatch.setattr(
        search_service,
        "search_local_stations",
        lambda *_args, **_kwargs: [],
    )

    calls = []

    def backend(query, country, min_bitrate, limit, use_cache):
        calls.append((query, country, min_bitrate, limit, use_cache))
        return [{"name": "Injected", "url": "https://example.org/injected"}]

    conn = sqlite3.connect(":memory:")
    try:
        result = SearchService(backend=backend, local_connection=conn, profile_id=2).search(
            SearchRequest(query="injected", source="all")
        )

        assert result.remote_status == "unknown"
        assert calls == [("injected", None, None, 100, True)]
    finally:
        conn.close()


def test_combined_candidate_window_recovers_overlapping_sources(monkeypatch) -> None:
    import sqlite3

    from fluxtuner.core import search_service

    shared = {"name": "Jazz", "url": "https://example.org/shared"}
    local_candidates = [
        shared,
        {"name": "Jazz B", "url": "https://example.org/local"},
    ]
    remote_candidates = [
        shared,
        {"name": "Jazz C", "url": "https://example.org/remote"},
    ]
    calls = []

    def local_backend(conn, *, profile_id, query, country, min_bitrate, limit):
        calls.append(("local", limit))
        return local_candidates[:limit]

    def remote_backend(query, country, min_bitrate, limit, use_cache):
        calls.append(("remote", limit))
        return remote_candidates[:limit]

    monkeypatch.setattr(search_service, "search_local_stations", local_backend)

    conn = sqlite3.connect(":memory:")
    try:
        service = SearchService(
            backend=remote_backend,
            local_connection=conn,
            profile_id=3,
        )
        result = service.search(SearchRequest(query="Jazz", limit=2, source="all"))

        assert len(result.stations) == 2
        assert result.total_found == 3
        assert calls == [("local", 4), ("remote", 4)]
        assert result.source_observations is not None
        assert result.source_observations["https://example.org/shared"] == (
            "local",
            "radio-browser",
        )
    finally:
        conn.close()


def test_radio_browser_does_not_cache_complete_provider_failure(monkeypatch) -> None:
    from fluxtuner.core import api

    def exercise(statuses):
        writes = []
        calls = []

        def fake_search(*_args, **kwargs):
            diagnostics = kwargs["_diagnostics"]
            status = statuses[len(calls)]
            calls.append(status)
            diagnostics["status"] = status
            return []

        with monkeypatch.context() as patch:
            patch.setattr(api, "search_stations", fake_search)
            patch.setattr(api, "get_cached_search", lambda _key: None)
            patch.setattr(
                api,
                "set_cached_search",
                lambda key, results: writes.append((key, results)),
            )

            results, diagnostic = api.search_stations_filtered_debug(
                "cache-regression",
                limit=10,
                use_cache=True,
            )

        assert results == []
        assert len(calls) == 2
        assert len(writes) <= 1
        return writes, diagnostic

    failed_writes, failed_debug = exercise(("request_error", "http_error"))
    assert failed_writes == []
    assert failed_debug["sources"]["name"]["status"] == "request_error"
    assert failed_debug["sources"]["tag"]["status"] == "http_error"

    empty_writes, empty_debug = exercise(("ok", "ok"))
    assert len(empty_writes) == 1
    assert empty_writes[0][1] == []
    assert empty_debug["sources"]["name"]["status"] == "ok"

    partial_writes, partial_debug = exercise(("request_error", "ok"))
    assert len(partial_writes) == 1
    assert partial_debug["sources"]["name"]["status"] == "request_error"
    assert partial_debug["sources"]["tag"]["status"] == "ok"
