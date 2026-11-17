"""Optional artwork resolution must not affect normal station operations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from fluxtuner.core import artwork_service
from fluxtuner.core.artwork_cache import ArtworkCache
from fluxtuner.core.artwork_download import DownloadedArtwork
from fluxtuner.core.artwork_service import ArtworkService

JPEG = (Path(__file__).parent / "fixtures" / "artwork" / "sample.jpg").read_bytes()
URL = "https://radio.example/favicon.jpg"


def test_miss_fetches_once_and_persists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_fetch(url: str, *_args: object, **_kwargs: object) -> DownloadedArtwork:
        calls.append(url)
        return DownloadedArtwork(JPEG, "image/jpeg")

    monkeypatch.setattr(artwork_service, "download_artwork", fake_fetch)
    cache = ArtworkCache(tmp_path)
    service = ArtworkService(cache)

    assert service.get(URL) == DownloadedArtwork(JPEG, "image/jpeg")
    assert service.get(URL) == DownloadedArtwork(JPEG, "image/jpeg")
    assert calls == [URL]
    assert ArtworkService(ArtworkCache(tmp_path)).get(URL) == DownloadedArtwork(JPEG, "image/jpeg")


def test_failures_are_silent_and_backed_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    clock = [100.0]

    def fake_fetch(url: str, *_args: object, **_kwargs: object) -> DownloadedArtwork:
        calls.append(url)
        raise ConnectionError("offline")

    monkeypatch.setattr(artwork_service, "download_artwork", fake_fetch)
    service = ArtworkService(ArtworkCache(tmp_path), clock=lambda: clock[0])

    assert service.get(URL) is None
    assert service.get(URL) is None
    assert calls == [URL]
    clock[0] += 121
    assert service.get(URL) is None
    assert calls == [URL, URL]


def test_invalid_url_never_fetches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_fetch(*_args: object, **_kwargs: object) -> DownloadedArtwork:
        raise AssertionError("Network must not be used for empty artwork")

    monkeypatch.setattr(artwork_service, "download_artwork", fail_fetch)
    service = ArtworkService(ArtworkCache(tmp_path))
    assert service.get("") is None
    assert service.get("  ") is None


def test_nonwritable_cache_does_not_hide_downloaded_artwork(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        artwork_service,
        "download_artwork",
        lambda *_args, **_kwargs: DownloadedArtwork(JPEG, "image/jpeg"),
    )
    cache = ArtworkCache(tmp_path)

    def fail_put(*_args: object, **_kwargs: object) -> None:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(cache, "put", fail_put)
    assert ArtworkService(cache).get(URL) == DownloadedArtwork(JPEG, "image/jpeg")


def test_negative_retry_must_be_nonnegative(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        ArtworkService(ArtworkCache(tmp_path), failure_retry_seconds=-1)


def test_concurrent_requests_share_one_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = Event()
    release = Event()
    calls: list[str] = []

    def fake_fetch(url: str, *_args: object, **_kwargs: object) -> DownloadedArtwork:
        calls.append(url)
        started.set()
        assert release.wait(5)
        return DownloadedArtwork(JPEG, "image/jpeg")

    monkeypatch.setattr(artwork_service, "download_artwork", fake_fetch)
    service = ArtworkService(ArtworkCache(tmp_path))

    with ThreadPoolExecutor(max_workers=6) as workers:
        owner = workers.submit(service.get, URL)
        assert started.wait(5)
        followers = [workers.submit(service.get, URL) for _ in range(5)]
        release.set()
        assert owner.result(timeout=5) == DownloadedArtwork(JPEG, "image/jpeg")
        assert all(
            follower.result(timeout=5) == DownloadedArtwork(JPEG, "image/jpeg")
            for follower in followers
        )

    assert calls == [URL]


def test_follower_wait_is_bounded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    started = Event()
    release = Event()

    def fake_fetch(*_args: object, **_kwargs: object) -> DownloadedArtwork:
        started.set()
        assert release.wait(5)
        return DownloadedArtwork(JPEG, "image/jpeg")

    monkeypatch.setattr(artwork_service, "download_artwork", fake_fetch)
    monkeypatch.setattr(artwork_service, "MAX_INFLIGHT_WAIT_SECONDS", 0.01)
    service = ArtworkService(ArtworkCache(tmp_path))

    with ThreadPoolExecutor(max_workers=2) as workers:
        owner = workers.submit(service.get, URL)
        assert started.wait(5)
        follower = workers.submit(service.get, URL)
        assert follower.result(timeout=2) is None
        release.set()
        assert owner.result(timeout=5) == DownloadedArtwork(JPEG, "image/jpeg")


def test_failure_releases_waiters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    started = Event()
    release = Event()
    calls: list[str] = []

    def fake_fetch(url: str, *_args: object, **_kwargs: object) -> DownloadedArtwork:
        calls.append(url)
        started.set()
        assert release.wait(5)
        raise OSError("offline")

    monkeypatch.setattr(artwork_service, "download_artwork", fake_fetch)
    service = ArtworkService(ArtworkCache(tmp_path))

    with ThreadPoolExecutor(max_workers=2) as workers:
        owner = workers.submit(service.get, URL)
        assert started.wait(5)
        follower = workers.submit(service.get, URL)
        release.set()
        assert owner.result(timeout=5) is None
        assert follower.result(timeout=5) is None

    assert calls == [URL]
