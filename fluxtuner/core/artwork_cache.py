"""Persistent, bounded artwork cache independent of playback and networking."""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from fluxtuner.core.artwork_validation import MAX_ARTWORK_BYTES, detect_artwork_type
from fluxtuner.paths import CACHE_DIR

DEFAULT_ARTWORK_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_CACHE_ENTRIES = 512
MAX_CACHE_BYTES = 128 * 1024 * 1024
_CACHE_NAME = re.compile(r"[0-9a-f]{64}\.(?:png|jpg|webp)\Z")
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class ArtworkCache:
    """Store validated artwork bytes under deterministic, opaque filenames."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        ttl_seconds: int = DEFAULT_ARTWORK_TTL_SECONDS,
        max_entries: int = MAX_CACHE_ENTRIES,
        max_cache_bytes: int = MAX_CACHE_BYTES,
    ) -> None:
        if ttl_seconds < 0:
            raise ValueError("Artwork cache TTL cannot be negative.")
        if max_entries <= 0 or max_cache_bytes <= 0:
            raise ValueError("Artwork cache limits must be positive.")
        self.directory = directory if directory is not None else CACHE_DIR / "artwork"
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_cache_bytes = max_cache_bytes

    def _path(self, url: str, extension: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}{extension}"

    def get(self, url: str) -> tuple[bytes, str] | None:
        """Return cached bytes and MIME type when the entry remains usable."""
        candidates: list[tuple[float, str, Path]] = []
        for mime, extension in _EXTENSIONS.items():
            path = self._path(url, extension)
            try:
                info = path.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            candidates.append((info.st_mtime, mime, path))

        for _mtime, mime, path in sorted(candidates, reverse=True):
            descriptor: int | None = None
            try:
                descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    continue
                if time.time() - info.st_mtime > self.ttl_seconds:
                    continue
                if not 24 <= info.st_size <= MAX_ARTWORK_BYTES:
                    continue
                with os.fdopen(descriptor, "rb") as stream:
                    descriptor = None
                    data = stream.read(MAX_ARTWORK_BYTES + 1)
            except OSError:
                continue
            finally:
                if descriptor is not None:
                    os.close(descriptor)
            if detect_artwork_type(data) == mime:
                return data, mime
        return None

    def _enforce_limits(self) -> None:
        """Evict oldest cache-owned regular files; never touch unrelated paths."""
        entries: list[tuple[float, int, Path]] = []
        try:
            for path in self.directory.iterdir():
                if not _CACHE_NAME.fullmatch(path.name):
                    continue
                info = path.lstat()
                if stat.S_ISREG(info.st_mode):
                    entries.append((info.st_mtime, info.st_size, path))
        except OSError:
            return

        total_bytes = sum(size for _, size, _ in entries)
        count = len(entries)
        for _, size, path in sorted(entries):
            if count <= self.max_entries and total_bytes <= self.max_cache_bytes:
                break
            try:
                path.unlink()
            except OSError:
                continue
            total_bytes -= size
            count -= 1

    def put(self, url: str, data: bytes) -> Path:
        """Atomically persist a bounded, recognized artwork payload."""
        mime = detect_artwork_type(data)
        if mime is None:
            raise ValueError("Unsupported or malformed artwork payload.")
        if len(data) > self.max_cache_bytes:
            raise ValueError("Artwork exceeds the configured cache size.")

        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self._path(url, _EXTENSIONS[mime])
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".artwork-",
                suffix=".tmp",
                dir=self.directory,
                delete=False,
            ) as stream:
                temporary = stream.name
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temporary)

        # The same URL may return another image format after a broadcaster update.
        for extension in _EXTENSIONS.values():
            old = self._path(url, extension)
            if old != destination:
                with contextlib.suppress(FileNotFoundError):
                    old.unlink()
        self._enforce_limits()
        return destination
