"""Optional artwork lookup; never part of station search or playback execution."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fluxtuner.core.artwork_cache import ArtworkCache
from fluxtuner.core.artwork_download import DownloadedArtwork, download_artwork
from fluxtuner.network.contracts import StreamTargetResolver
from fluxtuner.network.network_policy import SystemStreamTargetResolver
from fluxtuner.network.transport import ProtectedHTTPTransport

logger = logging.getLogger(__name__)
DEFAULT_FAILURE_RETRY_SECONDS = 120
MAX_NEGATIVE_CACHE_ENTRIES = 512
MAX_INFLIGHT_WAIT_SECONDS = 8.0


@dataclass(slots=True)
class _Flight:
    complete: threading.Event = field(default_factory=threading.Event)
    result: DownloadedArtwork | None = None


class ArtworkService:
    """Resolve optional artwork with persistent cache and bounded failure backoff.

    This synchronous API performs network I/O on cache misses. Callers MUST run
    it off the GTK/main event loop or inside an asynchronous worker thread.
    """

    def __init__(
        self,
        cache: ArtworkCache | None = None,
        *,
        resolver: StreamTargetResolver | None = None,
        transport: ProtectedHTTPTransport | None = None,
        failure_retry_seconds: float = DEFAULT_FAILURE_RETRY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_retry_seconds < 0:
            raise ValueError("Artwork failure retry interval cannot be negative.")
        self.cache = cache if cache is not None else ArtworkCache()
        self.resolver = resolver if resolver is not None else SystemStreamTargetResolver()
        self.transport = transport
        self.failure_retry_seconds = failure_retry_seconds
        self._clock = clock
        self._negative: dict[str, float] = {}
        self._inflight: dict[str, _Flight] = {}
        self._lock = threading.Lock()

    def _record_failure(self, url: str) -> None:
        with self._lock:
            now = self._clock()
            self._negative = {key: end for key, end in self._negative.items() if end > now}
            if len(self._negative) >= MAX_NEGATIVE_CACHE_ENTRIES:
                self._negative.pop(next(iter(self._negative)))
            self._negative[url] = now + self.failure_retry_seconds

    def get(self, url: str) -> DownloadedArtwork | None:
        """Return artwork or None; failed artwork never raises into its consumer."""
        if not isinstance(url, str) or not url.strip():
            return None
        candidate = url.strip()
        try:
            cached = self.cache.get(candidate)
        except Exception:
            logger.debug("Optional station artwork cache lookup failed", exc_info=True)
            cached = None
        if cached is not None:
            data, mime_type = cached
            return DownloadedArtwork(data=data, mime_type=mime_type)

        with self._lock:
            if self._negative.get(candidate, 0) > self._clock():
                return None
            flight = self._inflight.get(candidate)
            leader = flight is None
            if flight is None:
                flight = _Flight()
                self._inflight[candidate] = flight

        if not leader:
            # The owner may encounter a stuck DNS resolver; followers never wait forever.
            if flight.complete.wait(MAX_INFLIGHT_WAIT_SECONDS):
                return flight.result
            return None

        try:
            # A second cache read closes the race with another completed owner.
            cached = self.cache.get(candidate)
            if cached is not None:
                data, mime_type = cached
                flight.result = DownloadedArtwork(data=data, mime_type=mime_type)
            else:
                flight.result = download_artwork(candidate, self.resolver, transport=self.transport)
                try:
                    self.cache.put(candidate, flight.result.data)
                except OSError:
                    # Read-only cache must not hide a successfully fetched image.
                    logger.debug("Could not persist optional station artwork", exc_info=True)
            return flight.result
        except Exception:
            logger.debug("Optional station artwork fetch failed", exc_info=True)
            self._record_failure(candidate)
            return None
        finally:
            with self._lock:
                self._inflight.pop(candidate, None)
                flight.complete.set()
