# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.profiles import resolve_profile_id
from fluxtuner.paths import data_file

RECORDINGS_DIR = data_file("recordings")
STATUS_COMPLETED = "completed"


def ensure_recordings_dir() -> Path:
    """Return the recordings directory, creating it when needed."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return RECORDINGS_DIR


def _resolve_recording_profile_id(
    conn: sqlite3.Connection,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> int:
    """Resolve recording ownership, falling back to the default profile."""
    resolved_profile_id = resolve_profile_id(
        conn,
        profile_id=profile_id,
        profile_name=profile_name,
    )
    if resolved_profile_id is not None:
        return resolved_profile_id

    return db.ensure_default_profile(conn)


def recording_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a public recording dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "profile_id": int(row["profile_id"]),
        "station_name": str(row["station_name"]),
        "source_url": str(row["source_url"]),
        "file_path": str(row["file_path"]),
        "started_at": str(row["started_at"]),
        "stopped_at": str(row["stopped_at"]),
        "duration_seconds": float(row["duration_seconds"]),
        "file_size": int(row["file_size"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
    }


def add_recording(
    conn: sqlite3.Connection,
    *,
    station_name: str,
    source_url: str,
    file_path: Path,
    started_at: str,
    stopped_at: str,
    duration_seconds: float,
    file_size: int,
    status: str = STATUS_COMPLETED,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> int:
    """Persist one completed recording and return its database id."""
    active_profile_id = _resolve_recording_profile_id(
        conn,
        profile_id=profile_id,
        profile_name=profile_name,
    )

    clean_station_name = station_name.strip()
    clean_source_url = source_url.strip()
    clean_status = status.strip()

    if not clean_station_name:
        raise ValueError("Recording station name is required.")
    if not clean_source_url:
        raise ValueError("Recording source URL is required.")
    if not clean_status:
        raise ValueError("Recording status is required.")
    if duration_seconds < 0:
        raise ValueError("Recording duration cannot be negative.")
    if file_size < 0:
        raise ValueError("Recording file size cannot be negative.")

    cursor = conn.execute(
        """
        INSERT INTO recordings (
            profile_id,
            station_name,
            source_url,
            file_path,
            started_at,
            stopped_at,
            duration_seconds,
            file_size,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            active_profile_id,
            clean_station_name,
            clean_source_url,
            str(file_path),
            started_at,
            stopped_at,
            float(duration_seconds),
            int(file_size),
            clean_status,
            db.utc_now(),
        ),
    )
    recording_id = cursor.lastrowid
    if recording_id is None:
        raise RuntimeError("Could not create recording.")

    return int(recording_id)


def list_recordings(
    conn: sqlite3.Connection,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return recordings for one profile, newest first."""
    active_profile_id = _resolve_recording_profile_id(
        conn,
        profile_id=profile_id,
        profile_name=profile_name,
    )

    rows = conn.execute(
        """
        SELECT *
        FROM recordings
        WHERE profile_id = ?
        ORDER BY started_at DESC, id DESC
        """,
        (active_profile_id,),
    ).fetchall()
    return [recording_from_row(row) for row in rows]


def get_recording(
    conn: sqlite3.Connection,
    recording_id: int,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> dict[str, Any] | None:
    """Return one recording owned by the selected profile."""
    active_profile_id = _resolve_recording_profile_id(
        conn,
        profile_id=profile_id,
        profile_name=profile_name,
    )

    row = conn.execute(
        """
        SELECT *
        FROM recordings
        WHERE id = ?
          AND profile_id = ?
        """,
        (recording_id, active_profile_id),
    ).fetchone()
    return recording_from_row(row) if row is not None else None


def delete_recording(
    conn: sqlite3.Connection,
    recording_id: int,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> bool:
    """Delete one recording metadata row owned by the selected profile.

    File deletion is intentionally not performed here. Storage cleanup will be
    coordinated separately so metadata and filesystem error handling stay
    explicit.
    """
    active_profile_id = _resolve_recording_profile_id(
        conn,
        profile_id=profile_id,
        profile_name=profile_name,
    )

    cursor = conn.execute(
        """
        DELETE FROM recordings
        WHERE id = ?
          AND profile_id = ?
        """,
        (recording_id, active_profile_id),
    )
    return cursor.rowcount > 0
