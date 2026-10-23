from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal, Protocol

from fluxtuner.core.api import (
    search_stations_filtered,
    search_stations_filtered_debug,
)
from fluxtuner.core.compatibility import filter_supported_stations
from fluxtuner.core.favorites import favorite_display_name
from fluxtuner.core.local_station_search import search_local_stations
from fluxtuner.core.stations import station_key, station_tags
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
    source: Literal["radio-browser", "local", "all"] = "radio-browser"


@dataclass(frozen=True)
class SearchResult:
    stations: list[dict[str, object]]
    total_found: int = 0
    unsupported_count: int = 0
    source_observations: dict[str, tuple[str, ...]] | None = None
    remote_status: Literal["ok", "partial_error", "error", "unknown", "not_queried"] = "unknown"


class SearchService:
    """Shared station search service used by UI entry points."""

    def __init__(
        self,
        backend: StationSearchBackend | None = None,
        capabilities: PlayerCapabilities | None = None,
        local_connection: sqlite3.Connection | None = None,
        profile_id: int | None = None,
    ) -> None:
        self._uses_default_backend = backend is None
        self._backend = backend if backend is not None else search_stations_filtered
        self._capabilities = capabilities
        self._local_connection = local_connection
        self._profile_id = profile_id

    def search(self, request: SearchRequest) -> SearchResult:
        query = request.query.strip()
        country = request.country.strip() if request.country else None
        min_bitrate = self._normalize_min_bitrate(request.min_bitrate)
        limit = max(1, int(request.limit))

        if request.source not in ("radio-browser", "local", "all"):
            raise ValueError("Unknown station discovery source.")

        if request.source in ("local", "all") and (
            self._local_connection is None or self._profile_id is None
        ):
            raise ValueError("Local discovery requires a connection and profile.")

        if request.source == "all":
            return self._search_combined(query, country, min_bitrate, limit, request.use_cache)

        if request.source == "local":
            if self._local_connection is None or self._profile_id is None:
                raise ValueError("Local discovery requires a connection and profile.")
            stations = search_local_stations(
                self._local_connection,
                profile_id=self._profile_id,
                query=query,
                country=country,
                min_bitrate=min_bitrate,
                limit=limit,
            )
        else:
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
    def _combined_rank(station: Station, query: str) -> int:
        """Use the same relevance tiers for local and remote stations."""
        needle = " ".join(query.casefold().split())
        if not needle:
            return 0

        name = " ".join(favorite_display_name(station).casefold().split())
        if name == needle:
            return 0
        if name.startswith(needle):
            return 1
        if needle in name:
            return 2

        tags = station_tags(station)
        favorite_tags = station.get("favorite_tags")
        if isinstance(favorite_tags, list):
            tags.extend(str(tag) for tag in favorite_tags)

        if any(needle in " ".join(tag.casefold().split()) for tag in tags):
            return 3
        return 4

    def _search_combined(
        self,
        query: str,
        country: str | None,
        min_bitrate: int | None,
        limit: int,
        use_cache: bool,
    ) -> SearchResult:
        """Compose both sources without persisting or caching local results."""
        if self._local_connection is None or self._profile_id is None:
            raise ValueError("Local discovery requires a connection and profile.")

        # Fetch a bounded surplus to accommodate overlap between sources.
        candidate_limit = limit + min(limit, 50)
        local = search_local_stations(
            self._local_connection,
            profile_id=self._profile_id,
            query=query,
            country=country,
            min_bitrate=min_bitrate,
            limit=candidate_limit,
        )
        remote_status: Literal["ok", "partial_error", "error", "unknown", "not_queried"] = "unknown"

        if self._uses_default_backend:
            remote, diagnostics = search_stations_filtered_debug(
                query, country, min_bitrate, candidate_limit, use_cache
            )
            remote_status = self._remote_status(diagnostics)
        else:
            remote = self._backend(query, country, min_bitrate, candidate_limit, use_cache)

        by_key: dict[str, Station] = {}
        observations: dict[str, list[str]] = {}

        # Local records win ties to preserve profile-specific display metadata.
        for source, candidates in (("local", local), ("radio-browser", remote)):
            for station in candidates:
                key = station_key(station)
                if key is None:
                    continue
                if key not in by_key:
                    by_key[key] = station
                    observations[key] = []
                if source not in observations[key]:
                    observations[key].append(source)

        ordered = sorted(
            by_key.values(),
            key=lambda station: (
                self._combined_rank(station, query),
                favorite_display_name(station).casefold(),
                station_key(station) or "",
            ),
        )

        total_found = len(ordered)
        unsupported_count = 0
        if self._capabilities is not None:
            supported = filter_supported_stations(ordered, self._capabilities)
            unsupported_count = total_found - len(supported)
            ordered = supported

        selected = ordered[:limit]
        return SearchResult(
            stations=selected,
            total_found=total_found,
            unsupported_count=unsupported_count,
            source_observations={
                key: tuple(observations[key])
                for station in selected
                if (key := station_key(station)) is not None
            },
            remote_status=remote_status,
        )

    @staticmethod
    def _remote_status(
        diagnostics: dict[str, object],
    ) -> Literal["ok", "partial_error", "error", "unknown", "not_queried"]:
        """Classify actual HTTP outcomes without equating cache hits with success."""
        if diagnostics.get("cache_hit"):
            return "unknown"

        sources = diagnostics.get("sources")
        if not isinstance(sources, dict) or not sources:
            return "not_queried"

        statuses = [detail.get("status") for detail in sources.values() if isinstance(detail, dict)]
        if not statuses or any(
            not isinstance(status, str)
            or status
            not in {
                "ok",
                "request_error",
                "http_error",
                "invalid_json",
                "unexpected_payload",
            }
            for status in statuses
        ):
            return "unknown"

        successes = sum(status == "ok" for status in statuses)
        if successes == len(statuses):
            return "ok"
        if successes:
            return "partial_error"
        return "error"

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
