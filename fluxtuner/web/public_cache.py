# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Small per-worker cache invalidated by commits from other SQLite connections."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fluxtuner.core import db

TTL_SECONDS = 60
MAX_ENTRIES = 8


class PublicResponseCache:
    """Cache public aggregates without serving them after a database commit.

    A persistent observer connection makes PRAGMA data_version meaningful:
    comparing values on freshly opened connections would not detect changes.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._path: Path | None = None
        self._identity: tuple[int, int] | None = None
        self._version: int | None = None
        self._entries: dict[str, tuple[float, dict[str, Any]]] = {}

    def _observe(self, path: Path) -> int:
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self._connection is None or self._path != path or self._identity != identity:
            if self._connection is not None:
                self._connection.close()
            self._connection = sqlite3.connect(path, check_same_thread=False)
            self._path = path
            self._identity = identity
            self._version = None
            self._entries.clear()

        version = int(self._connection.execute("PRAGMA data_version").fetchone()[0])
        if version != self._version:
            self._entries.clear()
            self._version = version
        return version

    def get(
        self,
        key: str,
        calculate: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> dict[str, Any]:
        """Return a fresh aggregate; never reuse across observed DB writes."""
        with self._lock:
            path = Path(db.DB_FILE).resolve()
            version = self._observe(path)
            cached = self._entries.get(key)
            now = time.monotonic()
            if cached is not None and now - cached[0] < TTL_SECONDS:
                return cached[1]

            with db.connect() as conn:
                value = calculate(conn)

            # If a writer committed during calculation, return the result
            # without caching a potentially inconsistent snapshot.
            if self._observe(path) == version:
                self._entries[key] = (time.monotonic(), value)
                # Bound memory even if a read-only instance never commits.
                while len(self._entries) > MAX_ENTRIES:
                    oldest = next(iter(self._entries))
                    del self._entries[oldest]
            return value


public_response_cache = PublicResponseCache()
