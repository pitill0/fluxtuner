# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from .client import fetch_protected_stream_metadata
from .contracts import MetadataFetchPolicy, StreamTargetResolver
from .urls import normalize_stream_target

logger = logging.getLogger(__name__)

MetadataValue = dict[str, Any]
MetadataFetcher = Callable[[str], MetadataValue | None]


class MetadataCacheStatus(StrEnum):
    """Public state exposed by the process-wide metadata cache."""

    PENDING = "pending"
    FRESH = "fresh"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MetadataCacheSnapshot:
    """Immutable point-in-time view returned without waiting for remote I/O."""

    url: str
    status: MetadataCacheStatus
    metadata: Mapping[str, Any] | None
    updated_at: float | None
    retry_at: float | None
    failure_count: int


@dataclass(slots=True)
class _CacheEntry:
    url: str
    status: MetadataCacheStatus
    metadata: MetadataValue | None = None
    updated_at: float | None = None
    retry_at: float | None = None
    failure_count: int = 0
    in_flight: bool = False
    touched_at: float = 0.0


class WorkSubmitter(Protocol):
    def submit(self, fn: Callable[[], None]) -> Future[None]: ...

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None: ...


class _ExecutorSubmitter:
    def __init__(self, max_workers: int) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="fluxtuner-metadata",
        )

    def submit(self, fn: Callable[[], None]) -> Future[None]:
        return self._executor.submit(fn)

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)


class MetadataCoordinator:
    """Process-wide cache and bounded background coordinator for stream metadata."""

    def __init__(
        self,
        resolver: StreamTargetResolver,
        *,
        policy: MetadataFetchPolicy | None = None,
        fetcher: MetadataFetcher | None = None,
        submitter: WorkSubmitter | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_workers: int = 4,
        max_pending: int = 32,
        max_entries: int = 512,
        success_ttl_seconds: float = 15.0,
        empty_ttl_seconds: float = 30.0,
        error_backoff_base_seconds: float = 15.0,
        error_backoff_max_seconds: float = 300.0,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive.")
        if max_pending <= 0:
            raise ValueError("max_pending must be positive.")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive.")
        if success_ttl_seconds <= 0 or empty_ttl_seconds <= 0:
            raise ValueError("metadata TTLs must be positive.")
        if error_backoff_base_seconds <= 0 or error_backoff_max_seconds <= 0:
            raise ValueError("metadata backoff values must be positive.")
        if error_backoff_base_seconds > error_backoff_max_seconds:
            raise ValueError("metadata backoff base cannot exceed its maximum.")

        active_policy = policy or MetadataFetchPolicy()
        self._policy = active_policy
        self._fetcher = fetcher or (
            lambda url: fetch_protected_stream_metadata(
                url,
                resolver,
                policy=active_policy,
            )
        )
        self._submitter = submitter or _ExecutorSubmitter(max_workers)
        self._owns_submitter = submitter is None
        self._clock = clock
        self._max_pending = max_pending
        self._max_entries = max_entries
        self._success_ttl = success_ttl_seconds
        self._empty_ttl = empty_ttl_seconds
        self._error_backoff_base = error_backoff_base_seconds
        self._error_backoff_max = error_backoff_max_seconds

        self._entries: dict[str, _CacheEntry] = {}
        self._pending_count = 0
        self._closed = False
        self._lock = threading.Lock()

    def get_or_schedule(self, raw_url: str) -> MetadataCacheSnapshot:
        """Return cached state immediately and enqueue one refresh when due."""
        target = normalize_stream_target(raw_url, self._policy)
        key = target.url
        now = self._clock()

        with self._lock:
            self._ensure_open()
            entry = self._entries.get(key)
            if entry is None:
                self._evict_one_if_needed()
                entry = _CacheEntry(
                    url=key,
                    status=MetadataCacheStatus.PENDING,
                    touched_at=now,
                )
                self._entries[key] = entry
            else:
                entry.touched_at = now

            if self._should_schedule(entry, now):
                self._schedule_locked(entry)

            return self._snapshot(entry)

    def peek(self, raw_url: str) -> MetadataCacheSnapshot | None:
        """Return cached state without scheduling remote work."""
        target = normalize_stream_target(raw_url, self._policy)
        now = self._clock()
        with self._lock:
            entry = self._entries.get(target.url)
            if entry is None:
                return None
            entry.touched_at = now
            return self._snapshot(entry)

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self._owns_submitter:
            self._submitter.shutdown(wait=wait, cancel_futures=True)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Metadata coordinator is closed.")

    def _should_schedule(self, entry: _CacheEntry, now: float) -> bool:
        if entry.in_flight:
            return False
        if self._pending_count >= self._max_pending:
            return False
        if entry.status is MetadataCacheStatus.PENDING:
            return True
        return entry.retry_at is None or now >= entry.retry_at

    def _schedule_locked(self, entry: _CacheEntry) -> None:
        entry.in_flight = True
        entry.status = MetadataCacheStatus.PENDING
        self._pending_count += 1
        key = entry.url

        try:
            self._submitter.submit(lambda: self._refresh(key))
        except Exception:
            entry.in_flight = False
            self._pending_count -= 1
            raise

    def _refresh(self, key: str) -> None:
        try:
            metadata = self._fetcher(key)
        except Exception:
            logger.debug("Protected metadata refresh failed", exc_info=True)
            self._finish_error(key)
            return

        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._pending_count -= 1
                return
            entry.in_flight = False
            self._pending_count -= 1
            entry.updated_at = now
            entry.touched_at = now
            entry.failure_count = 0
            entry.metadata = metadata
            if metadata is None:
                entry.status = MetadataCacheStatus.EMPTY
                entry.retry_at = now + self._empty_ttl
            else:
                entry.status = MetadataCacheStatus.FRESH
                entry.retry_at = now + self._success_ttl

    def _finish_error(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._pending_count -= 1
                return
            entry.in_flight = False
            self._pending_count -= 1
            entry.updated_at = now
            entry.touched_at = now
            entry.metadata = None
            entry.status = MetadataCacheStatus.ERROR
            entry.failure_count += 1
            max_exponent = math.ceil(
                math.log2(
                    self._error_backoff_max / self._error_backoff_base,
                )
            )
            exponent = min(entry.failure_count - 1, max_exponent)
            backoff = min(
                self._error_backoff_base * (2**exponent),
                self._error_backoff_max,
            )
            entry.retry_at = now + backoff

    def _evict_one_if_needed(self) -> None:
        if len(self._entries) < self._max_entries:
            return
        candidates = [entry for entry in self._entries.values() if not entry.in_flight]
        if not candidates:
            raise RuntimeError("Metadata cache capacity is exhausted by active work.")
        oldest = min(candidates, key=lambda entry: entry.touched_at)
        del self._entries[oldest.url]

    @staticmethod
    def _snapshot(entry: _CacheEntry) -> MetadataCacheSnapshot:
        metadata = MappingProxyType(dict(entry.metadata)) if entry.metadata is not None else None
        return MetadataCacheSnapshot(
            url=entry.url,
            status=entry.status,
            metadata=metadata,
            updated_at=entry.updated_at,
            retry_at=entry.retry_at,
            failure_count=entry.failure_count,
        )
