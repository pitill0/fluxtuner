# SPDX-License-Identifier: MIT
"""Profile-owned provenance for shared station records."""

from __future__ import annotations

import secrets
import sqlite3
import unicodedata
from typing import Any

from fluxtuner.core import db

SOURCE_KINDS = frozenset({"local_collection", "remote_collection", "manual_entry"})
MAX_DISPLAY_NAME_LENGTH = 120


def _profile(conn: sqlite3.Connection, profile_id: int) -> None:
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing profile is required.")
    row = conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if row is None:
        raise ValueError("The selected profile no longer exists.")


def _source(conn: sqlite3.Connection, profile_id: int, source_id: int) -> sqlite3.Row:
    _profile(conn, profile_id)
    if type(source_id) is not int or source_id <= 0:
        raise ValueError("Source not found for the selected profile.")
    row = conn.execute(
        "SELECT * FROM station_sources WHERE id = ? AND profile_id = ?",
        (source_id, profile_id),
    ).fetchone()
    if row is None:
        raise ValueError("Source not found for the selected profile.")
    return row


def _display_name(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid source display name.")
    name = value.strip()
    if not name or len(name) > MAX_DISPLAY_NAME_LENGTH:
        raise ValueError("Invalid source display name.")
    if any(unicodedata.category(char).startswith("C") for char in name):
        raise ValueError("Invalid source display name.")
    if any(char in name for char in ("/", "\\", "?", "#", ":", "@")):
        raise ValueError("Source display name cannot contain a path or URL.")
    return name


def _public_source(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "kind": str(row["kind"]),
        "display_name": row["display_name"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def create_source(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    kind: str,
    display_name: str | None = None,
) -> int:
    """Create a profile-owned source; caller owns the transaction."""
    _profile(conn, profile_id)
    if type(kind) is not str or kind not in SOURCE_KINDS:
        raise ValueError("Unsupported collection source kind.")
    name = _display_name(display_name)
    now = db.utc_now()
    cursor = conn.execute(
        """
        INSERT INTO station_sources (
            profile_id, kind, source_ref, display_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (profile_id, kind, secrets.token_urlsafe(24), name, now, now),
    )
    source_id = cursor.lastrowid
    if source_id is None or source_id <= 0:
        raise RuntimeError("Could not create station source.")
    return source_id


def get_source(conn: sqlite3.Connection, *, profile_id: int, source_id: int) -> dict[str, Any]:
    """Return owned source metadata without revealing its opaque reference."""
    return _public_source(_source(conn, profile_id, source_id))


def list_sources(conn: sqlite3.Connection, *, profile_id: int) -> list[dict[str, Any]]:
    """List profile-owned sources without revealing opaque references."""
    _profile(conn, profile_id)
    rows = conn.execute(
        "SELECT id, kind, display_name, created_at, updated_at "
        "FROM station_sources WHERE profile_id = ? ORDER BY id",
        (profile_id,),
    ).fetchall()
    return [_public_source(row) for row in rows]


def record_observation(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    source_id: int,
    station_id: int,
) -> None:
    """Observe one existing station; never modify its shared station record."""
    _source(conn, profile_id, source_id)
    if type(station_id) is not int or station_id <= 0:
        raise ValueError("An existing station is required.")
    if conn.execute("SELECT 1 FROM stations WHERE id = ?", (station_id,)).fetchone() is None:
        raise ValueError("The selected station no longer exists.")
    now = db.utc_now()
    conn.execute(
        """
        INSERT INTO station_source_memberships (
            source_id, station_id, first_observed_at, last_observed_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(source_id, station_id)
        DO UPDATE SET last_observed_at = excluded.last_observed_at
        """,
        (source_id, station_id, now, now),
    )
    conn.execute(
        "UPDATE station_sources SET updated_at = ? WHERE id = ? AND profile_id = ?",
        (now, source_id, profile_id),
    )


def list_station_sources(
    conn: sqlite3.Connection, *, profile_id: int, station_id: int
) -> list[dict[str, Any]]:
    """Return only this profile's observations of a shared station."""
    _profile(conn, profile_id)
    if type(station_id) is not int or station_id <= 0:
        raise ValueError("An existing station is required.")
    rows = conn.execute(
        """
        SELECT src.id, src.kind, src.display_name,
               src.created_at, src.updated_at,
               rel.first_observed_at, rel.last_observed_at
        FROM station_sources AS src
        JOIN station_source_memberships AS rel ON rel.source_id = src.id
        WHERE src.profile_id = ? AND rel.station_id = ?
        ORDER BY src.id
        """,
        (profile_id, station_id),
    ).fetchall()
    return [
        {
            **_public_source(row),
            "first_observed_at": str(row["first_observed_at"]),
            "last_observed_at": str(row["last_observed_at"]),
        }
        for row in rows
    ]


def list_source_stations(
    conn: sqlite3.Connection, *, profile_id: int, source_id: int
) -> list[dict[str, Any]]:
    """List station identities observed in one owned source."""
    _source(conn, profile_id, source_id)
    rows = conn.execute(
        """
        SELECT s.id, s.name,
               rel.first_observed_at, rel.last_observed_at
        FROM station_source_memberships AS rel
        JOIN stations AS s ON s.id = rel.station_id
        JOIN station_sources AS src ON src.id = rel.source_id
        WHERE src.id = ? AND src.profile_id = ?
        ORDER BY s.id
        """,
        (source_id, profile_id),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_source(conn: sqlite3.Connection, *, profile_id: int, source_id: int) -> bool:
    """Delete an owned source and observations, never shared stations."""
    _source(conn, profile_id, source_id)
    cursor = conn.execute(
        "DELETE FROM station_sources WHERE id = ? AND profile_id = ?",
        (source_id, profile_id),
    )
    return cursor.rowcount > 0
