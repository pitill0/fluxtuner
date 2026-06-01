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
