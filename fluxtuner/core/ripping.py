"""UI-independent requests and observations for track ripping."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fluxtuner.core.stations import station_name, station_url
from fluxtuner.players.security import is_supported_stream_url


@dataclass(frozen=True)
class RippedTrack:
    """One finalized track, distinct from the still-open track at shutdown."""

    title: str
    path: Path


class RippingError(RuntimeError):
    """A ripping failure that retains already finalized output references."""

    def __init__(self, message: str, *, tracks: tuple[RippedTrack, ...] = ()) -> None:
        super().__init__(message)
        self.tracks = tracks


@dataclass(frozen=True)
class RippingRequest:
    """Snapshot the explicit station and profile independently of UI selection."""

    station_name: str
    source_url: str
    output_directory: Path
    profile_name: str | None = None
    profile_id: int | None = None

    def __post_init__(self) -> None:
        name = self.station_name.strip()
        url = self.source_url.strip()
        if not name:
            raise RippingError("Ripping station name is required.")
        try:
            supported = is_supported_stream_url(url)
        except ValueError as exc:
            raise RippingError("Ripping requires a valid HTTP(S) stream URL.") from exc
        if not supported:
            raise RippingError("Ripping requires a valid HTTP(S) stream URL.")
        object.__setattr__(self, "station_name", name)
        object.__setattr__(self, "source_url", url)
        object.__setattr__(self, "output_directory", self.output_directory.expanduser().absolute())

    @classmethod
    def from_station(
        cls,
        station: dict[str, Any],
        *,
        output_directory: Path,
        profile_name: str | None = None,
        profile_id: int | None = None,
    ) -> RippingRequest:
        return cls(
            station_name=station_name(station),
            source_url=station_url(station) or "",
            output_directory=output_directory,
            profile_name=profile_name,
            profile_id=profile_id,
        )


@dataclass(frozen=True)
class RippingAvailability:
    """Local backend readiness, not a promise of station compatibility."""

    available: bool
    reason: str = ""


@dataclass(frozen=True)
class RippingStarted:
    """The stream has opened and its codec and ICY interval are known."""

    codec: str
    metaint: int


@dataclass(frozen=True)
class RippingResult:
    request: RippingRequest
    codec: str
    metaint: int
    stopped: bool
    tracks: tuple[RippedTrack, ...] = ()
    incomplete_track_title: str | None = None


class RippingBackend(Protocol):
    """Blocking backend contract; a coordinator must own worker scheduling."""

    def availability(self) -> RippingAvailability: ...

    def run(
        self,
        request: RippingRequest,
        *,
        on_started: Callable[[RippingStarted], None] | None = None,
        on_track_written: Callable[[RippedTrack], None] | None = None,
    ) -> RippingResult: ...

    def stop(self) -> None: ...
