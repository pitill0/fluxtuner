from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fluxtuner.core.api import search_stations_filtered

Station = dict[str, object]


class StationSearchBackend(Protocol):
    def __call__(
        self,
        query: str,
        country: str | None = None,
        min_bitrate: int | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class SearchRequest:
    query: str = ""
    country: str | None = None
    min_bitrate: int | None = None
    limit: int = 50
    use_cache: bool = True


@dataclass(frozen=True)
class SearchResult:
    stations: list[dict[str, object]]


class SearchService:
    """Shared station search service used by UI entry points."""

    def __init__(
        self,
        backend: StationSearchBackend | None = None,
    ) -> None:
        self._backend = backend or search_stations_filtered

    def search(self, request: SearchRequest) -> SearchResult:
        query = request.query.strip()
        country = request.country.strip() if request.country else None
        min_bitrate = self._normalize_min_bitrate(request.min_bitrate)
        limit = max(1, int(request.limit))

        stations = self._backend(
            query,
            country,
            min_bitrate,
            limit,
            request.use_cache,
        )

        return SearchResult(stations=stations)

    @staticmethod
    def _normalize_min_bitrate(value: int | None) -> int | None:
        if value is None:
            return None
        return max(0, int(value))


def search_stations(
    query: str,
    *,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
    use_cache: bool = True,
    service: SearchService | None = None,
) -> list[dict[str, object]]:
    """Convenience wrapper for simple callers."""
    active_service = service or SearchService()
    result = active_service.search(
        SearchRequest(
            query=query,
            country=country,
            min_bitrate=min_bitrate,
            limit=limit,
            use_cache=use_cache,
        )
    )
    return result.stations
