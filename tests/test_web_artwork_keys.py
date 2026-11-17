"""Artwork signing key must be persistent, private and process-safe."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fluxtuner.web.artwork_keys import (
    ARTWORK_KEY_BYTES,
    load_or_create_artwork_signing_key,
)


def test_creates_private_persistent_key(tmp_path: Path) -> None:
    destination = tmp_path / "web" / "artwork-signing.key"
    first = load_or_create_artwork_signing_key(destination)
    assert len(first) == ARTWORK_KEY_BYTES
    assert destination.stat().st_mode & 0o777 == 0o600
    assert load_or_create_artwork_signing_key(destination) == first
    assert not list(destination.parent.glob(".artwork-key-*"))


def test_parallel_first_startups_share_one_key(tmp_path: Path) -> None:
    destination = tmp_path / "web" / "artwork-signing.key"
    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(lambda _: load_or_create_artwork_signing_key(destination), range(32)))
    assert len(set(keys)) == 1
    assert not list(destination.parent.glob(".artwork-key-*"))


def test_rejects_unsafe_permissions_without_overwriting(tmp_path: Path) -> None:
    destination = tmp_path / "artwork-signing.key"
    destination.write_bytes(b"x" * ARTWORK_KEY_BYTES)
    destination.chmod(0o644)
    with pytest.raises(PermissionError):
        load_or_create_artwork_signing_key(destination)
    assert destination.read_bytes() == b"x" * ARTWORK_KEY_BYTES


def test_rejects_corrupt_existing_key(tmp_path: Path) -> None:
    destination = tmp_path / "artwork-signing.key"
    destination.write_bytes(b"short")
    destination.chmod(0o600)
    with pytest.raises(PermissionError):
        load_or_create_artwork_signing_key(destination)
    assert destination.read_bytes() == b"short"


def test_rejects_symlink_without_following_it(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(os.urandom(ARTWORK_KEY_BYTES))
    target.chmod(0o600)
    destination = tmp_path / "artwork-signing.key"
    destination.symlink_to(target)
    with pytest.raises(OSError):
        load_or_create_artwork_signing_key(destination)
    assert destination.is_symlink()


def test_rejects_hardlinked_key(tmp_path: Path) -> None:
    destination = tmp_path / "artwork-signing.key"
    destination.write_bytes(os.urandom(ARTWORK_KEY_BYTES))
    destination.chmod(0o600)
    os.link(destination, tmp_path / "other-link")
    with pytest.raises(PermissionError):
        load_or_create_artwork_signing_key(destination)
