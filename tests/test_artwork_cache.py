from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from fluxtuner.core.artwork_cache import ArtworkCache

FIXTURES = Path(__file__).parent / "fixtures" / "artwork"
JPEG_SAMPLE = (FIXTURES / "sample.jpg").read_bytes()


def test_cache_roundtrip_survives_new_instance(tmp_path: Path) -> None:
    directory = tmp_path / "artwork"
    first = ArtworkCache(directory)
    stored = first.put("https://example.com/logo.jpg", JPEG_SAMPLE)

    assert stored.is_file()
    assert stored.parent == directory
    assert "example.com" not in stored.name
    assert ArtworkCache(directory).get("https://example.com/logo.jpg") == (
        JPEG_SAMPLE,
        "image/jpeg",
    )


def test_cache_entries_expire(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path, ttl_seconds=60)
    stored = cache.put("https://example.com/old.jpg", JPEG_SAMPLE)
    old = time.time() - 120
    os.utime(stored, (old, old))

    assert cache.get("https://example.com/old.jpg") is None


def test_cache_rejects_invalid_payload(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path)

    with pytest.raises(ValueError, match="Unsupported"):
        cache.put("https://example.com/logo.svg", b"<svg>unsafe</svg>")

    assert not list(tmp_path.iterdir())


def test_cache_does_not_follow_symlink(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path / "cache")
    stored = cache.put("https://example.com/logo.jpg", JPEG_SAMPLE)
    stored.unlink()
    stored.symlink_to(tmp_path / "missing-file")

    assert cache.get("https://example.com/logo.jpg") is None


def test_cache_rejects_negative_ttl(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TTL"):
        ArtworkCache(tmp_path, ttl_seconds=-1)


def test_cache_removes_older_format_for_same_url(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path)
    url = "https://example.com/logo"
    jpeg_path = cache.put(url, JPEG_SAMPLE)
    webp = (FIXTURES / "sample.webp").read_bytes()

    webp_path = cache.put(url, webp)

    assert not jpeg_path.exists()
    assert webp_path.exists()
    assert cache.get(url) == (webp, "image/webp")


def test_cache_evicts_oldest_without_touching_unrelated_files(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path, max_entries=2)
    oldest = cache.put("https://example.com/oldest", JPEG_SAMPLE)
    old = time.time() - 120
    os.utime(oldest, (old, old))
    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("keep")

    cache.put("https://example.com/middle", JPEG_SAMPLE)
    cache.put("https://example.com/newest", JPEG_SAMPLE)

    assert not oldest.exists()
    assert unrelated.read_text() == "keep"
    assert cache.get("https://example.com/newest") is not None


def test_cache_enforces_disk_quota(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path, max_cache_bytes=len(JPEG_SAMPLE) + 1)
    oldest = cache.put("https://example.com/oldest", JPEG_SAMPLE)
    old = time.time() - 120
    os.utime(oldest, (old, old))

    cache.put("https://example.com/newest", JPEG_SAMPLE)

    assert not oldest.exists()
    assert cache.get("https://example.com/newest") is not None


def test_cache_rejects_payload_larger_than_quota(tmp_path: Path) -> None:
    cache = ArtworkCache(tmp_path, max_cache_bytes=len(JPEG_SAMPLE) - 1)
    with pytest.raises(ValueError, match="cache size"):
        cache.put("https://example.com/logo", JPEG_SAMPLE)


def test_cache_requires_positive_limits(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        ArtworkCache(tmp_path, max_entries=0)
    with pytest.raises(ValueError, match="positive"):
        ArtworkCache(tmp_path, max_cache_bytes=0)
