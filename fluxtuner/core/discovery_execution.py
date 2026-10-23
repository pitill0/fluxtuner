# SPDX-License-Identifier: MIT
"""Execute desktop discovery with a worker-owned, read-only local connection."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from fluxtuner.core import db
from fluxtuner.core.search_service import SearchRequest, SearchResult, SearchService
from fluxtuner.players.capabilities import PlayerCapabilities


def search_desktop_stations(
    request: SearchRequest,
    *,
    profile_name: str | None = None,
    capabilities: PlayerCapabilities | None = None,
    db_path: Path | None = None,
) -> SearchResult:
    """Search without creating profiles or sharing SQLite connections across threads."""
    if request.source == "radio-browser":
        return SearchService(capabilities=capabilities).search(request)

    if request.source not in ("local", "all"):
        raise ValueError("Unknown station discovery source.")

    name = db.DEFAULT_PROFILE_NAME if profile_name is None else profile_name.strip()
    if not name:
        raise ValueError("An existing profile is required.")

    path = db.DB_FILE if db_path is None else db_path
    uri = path.resolve().as_uri() + "?mode=ro"

    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        profile = conn.execute(
            """
            SELECT p.id
            FROM profiles AS p
            JOIN users AS u ON u.id = p.user_id
            WHERE lower(u.username) = lower(?)
              AND lower(p.name) = lower(?)
            """,
            (db.DEFAULT_USER_NAME, name),
        ).fetchone()
        if profile is None:
            raise ValueError("The current profile is unavailable.")

        service = SearchService(
            capabilities=capabilities,
            local_connection=conn,
            profile_id=int(profile["id"]),
        )
        return service.search(request)
