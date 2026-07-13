from __future__ import annotations

import socket
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

import pytest

from fluxtuner.web.metadata.contracts import (
    NetworkAddressScope,
    ResolvedAddress,
)
from fluxtuner.web.metadata.coordinator import (
    MetadataCacheStatus,
    MetadataCoordinator,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ManualSubmitter:
    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []
        self.shutdown_calls: list[tuple[bool, bool]] = []

    def submit(self, fn: Callable[[], None]) -> Future[None]:
        self.jobs.append(fn)
        return Future()

    def run_next(self) -> None:
        self.jobs.pop(0)()

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


class FakeResolver:
    def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
        return (
            ResolvedAddress(
                hostname=hostname,
                port=port,
                family=socket.AddressFamily.AF_INET,
                address="8.8.8.8",
                scope=NetworkAddressScope.GLOBAL,
            ),
        )


def metadata(title: str) -> dict[str, Any]:
    return {
        "raw": title,
        "artist": "",
        "title": title,
        "source": "icy",
    }


def test_get_or_schedule_returns_pending_without_running_remote_work() -> None:
    submitter = ManualSubmitter()
    calls: list[str] = []
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: calls.append(url) or metadata("Song"),
        submitter=submitter,
    )

    snapshot = coordinator.get_or_schedule("HTTP://Radio.Example")

    assert snapshot.url == "http://radio.example/"
    assert snapshot.status is MetadataCacheStatus.PENDING
    assert calls == []
    assert len(submitter.jobs) == 1


def test_normalized_url_deduplicates_in_flight_work() -> None:
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
    )

    first = coordinator.get_or_schedule("HTTP://Radio.Example")
    second = coordinator.get_or_schedule("http://radio.example/")

    assert first.url == second.url
    assert len(submitter.jobs) == 1


def test_success_is_cached_until_ttl_expires() -> None:
    clock = FakeClock()
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
        clock=clock,
        success_ttl_seconds=10.0,
    )

    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()

    fresh = coordinator.get_or_schedule("https://radio.example/live")
    assert fresh.status is MetadataCacheStatus.FRESH
    assert fresh.metadata == metadata("Song")
    assert fresh.retry_at == 10.0
    assert submitter.jobs == []

    clock.advance(10.0)
    refreshing = coordinator.get_or_schedule("https://radio.example/live")
    assert refreshing.status is MetadataCacheStatus.PENDING
    assert refreshing.metadata == metadata("Song")
    assert len(submitter.jobs) == 1


def test_snapshot_metadata_cannot_be_mutated() -> None:
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
    )

    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()
    snapshot = coordinator.peek("https://radio.example/live")

    assert snapshot is not None
    assert snapshot.metadata is not None
    with pytest.raises(TypeError):
        snapshot.metadata["title"] = "Changed"  # type: ignore[index]


def test_error_backoff_caps_without_unbounded_exponentiation() -> None:
    clock = FakeClock()
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("failure")),
        submitter=submitter,
        clock=clock,
        error_backoff_base_seconds=5.0,
        error_backoff_max_seconds=20.0,
    )

    key = "https://radio.example/live"
    coordinator.get_or_schedule(key)
    entry = coordinator._entries[key]  # type: ignore[attr-defined]
    entry.failure_count = 1_000_000

    submitter.run_next()
    snapshot = coordinator.peek(key)

    assert snapshot is not None
    assert snapshot.retry_at == 20.0


def test_empty_result_uses_empty_ttl() -> None:
    clock = FakeClock()
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: None,
        submitter=submitter,
        clock=clock,
        empty_ttl_seconds=20.0,
    )

    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()

    snapshot = coordinator.peek("https://radio.example/live")
    assert snapshot is not None
    assert snapshot.status is MetadataCacheStatus.EMPTY
    assert snapshot.retry_at == 20.0


def test_errors_apply_exponential_backoff_and_reset_after_success() -> None:
    clock = FakeClock()
    submitter = ManualSubmitter()
    outcomes: list[dict[str, Any] | Exception] = [
        RuntimeError("first"),
        RuntimeError("second"),
        metadata("Recovered"),
    ]

    def fetcher(url: str) -> dict[str, Any] | None:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=fetcher,
        submitter=submitter,
        clock=clock,
        error_backoff_base_seconds=5.0,
        error_backoff_max_seconds=20.0,
    )

    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()
    first = coordinator.peek("https://radio.example/live")
    assert first is not None
    assert first.status is MetadataCacheStatus.ERROR
    assert first.failure_count == 1
    assert first.retry_at == 5.0

    clock.advance(5.0)
    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()
    second = coordinator.peek("https://radio.example/live")
    assert second is not None
    assert second.failure_count == 2
    assert second.retry_at == 15.0

    clock.advance(10.0)
    coordinator.get_or_schedule("https://radio.example/live")
    submitter.run_next()
    recovered = coordinator.peek("https://radio.example/live")
    assert recovered is not None
    assert recovered.status is MetadataCacheStatus.FRESH
    assert recovered.failure_count == 0


def test_pending_bound_prevents_unbounded_queue_growth() -> None:
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
        max_pending=1,
    )

    first = coordinator.get_or_schedule("https://one.example/live")
    second = coordinator.get_or_schedule("https://two.example/live")

    assert first.status is MetadataCacheStatus.PENDING
    assert second.status is MetadataCacheStatus.PENDING
    assert len(submitter.jobs) == 1


def test_cache_evicts_oldest_idle_entry() -> None:
    clock = FakeClock()
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
        clock=clock,
        max_entries=2,
    )

    coordinator.get_or_schedule("https://one.example/live")
    submitter.run_next()
    clock.advance(1.0)
    coordinator.get_or_schedule("https://two.example/live")
    submitter.run_next()
    clock.advance(1.0)
    coordinator.get_or_schedule("https://three.example/live")

    assert coordinator.peek("https://one.example/live") is None
    assert coordinator.peek("https://two.example/live") is not None


def test_close_is_idempotent_and_rejects_new_work() -> None:
    submitter = ManualSubmitter()
    coordinator = MetadataCoordinator(
        FakeResolver(),
        fetcher=lambda url: metadata("Song"),
        submitter=submitter,
    )

    coordinator.close()
    coordinator.close()

    with pytest.raises(RuntimeError, match="closed"):
        coordinator.get_or_schedule("https://radio.example/live")
