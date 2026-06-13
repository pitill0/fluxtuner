from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fluxtuner.core.api import search_stations_filtered
from fluxtuner.core.compatibility import filter_supported_stations
from fluxtuner.players.capabilities import PlayerCapabilities

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
    total_found: int = 0
    unsupported_count: int = 0


class SearchService:
    """Shared station search service used by UI entry points."""

    def __init__(
        self,
        backend: StationSearchBackend | None = None,
        capabilities: PlayerCapabilities | None = None,
    ) -> None:
        self._backend = backend or search_stations_filtered
        self._capabilities = capabilities

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

        total_found = len(stations)
        unsupported_count = 0
        if self._capabilities is not None:
            filtered = filter_supported_stations(stations, self._capabilities)  # type: ignore[arg-type]
            unsupported_count = total_found - len(filtered)
            stations = filtered

        return SearchResult(
            stations=stations,
            total_found=total_found,
            unsupported_count=unsupported_count,
        )

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
