# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Load a server-only artwork signing key, shared safely across Web workers."""

from __future__ import annotations

import contextlib
import fcntl
import os
import secrets
import stat
import tempfile
from pathlib import Path

from fluxtuner import paths

ARTWORK_KEY_BYTES = 32


def artwork_signing_key_path() -> Path:
    """Keep the signing key in persistent application data, not the image cache."""
    return paths.DATA_DIR / "web" / "artwork-signing.key"


def _read_private_key(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o077
            or metadata.st_size != ARTWORK_KEY_BYTES
        ):
            raise PermissionError("Artwork signing key has unsafe ownership or permissions.")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            key = stream.read(ARTWORK_KEY_BYTES + 1)
        if len(key) != ARTWORK_KEY_BYTES:
            raise ValueError("Invalid artwork signing key length.")
        return key
    finally:
        os.close(descriptor)


def load_or_create_artwork_signing_key(path: Path | None = None) -> bytes:
    """Atomically publish a private key without overwriting an existing key.

    Every worker gets the same bytes, including simultaneous first startups.
    Unsafe existing files fail closed instead of being repaired or replaced.
    """
    destination = path if path is not None else artwork_signing_key_path()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = destination.with_name(f".{destination.name}.lock")
    lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock_path, lock_flags, 0o600)
    try:
        lock_info = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.geteuid()
            or lock_info.st_nlink != 1
            or lock_info.st_mode & 0o077
        ):
            raise PermissionError("Unsafe artwork signing key lock file.")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            return _read_private_key(destination)
        except FileNotFoundError:
            return _create_private_key(destination)
    finally:
        os.close(lock_fd)


def _create_private_key(destination: Path) -> bytes:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".artwork-key-", dir=destination.parent, delete=False
        ) as stream:
            temporary = stream.name
            os.fchmod(stream.fileno(), 0o600)
            stream.write(secrets.token_bytes(ARTWORK_KEY_BYTES))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            pass
        else:
            directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)

    return _read_private_key(destination)
