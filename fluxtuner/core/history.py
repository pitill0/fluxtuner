# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.profiles import resolve_profile_id
from fluxtuner.core.stations import (
    station_from_row,
    station_key,
    station_metadata,
    upsert_station,
)
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import data_file, migrate_legacy_file

logger = get_logger(__name__)
LEGACY_HISTORY_FILE = Path.home() / ".fluxtuner_history.json"
HISTORY_FILE = data_file("history.json")
HISTORY_JSON_MIGRATION = "history_json_v1"
MAX_HISTORY_ITEMS = 100


def _db_path() -> Path:
    """Return the SQLite DB path next to the current history file.

    Tests patch HISTORY_FILE directly. Deriving the DB path from it keeps the
    SQLite-backed implementation isolated in the same tmp directory.
    """
    return HISTORY_FILE.parent / "fluxtuner.db"


def _station_key(station: dict[str, Any]) -> str:
    return str(station.get("url") or station.get("name") or "")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def history_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a history station dict from a joined history/station row.

    History entries are snapshots. FluxTuner 0.6.0 returned the saved JSON item
    mostly as-is, so migrated history should not grow station defaults such as
    codec, bitrate or url_resolved unless they were already present.
    """
    try:
        snapshot = json.loads(str(row["station_snapshot_json"] or "{}"))
    except json.JSONDecodeError:
        snapshot = {}

    if isinstance(snapshot, dict) and snapshot:
        return dict(snapshot)

    station = station_from_row(row)
    station["last_played_at"] = str(row["last_played_at"] or "")
    station["play_count"] = _safe_int(row["play_count"])

    return station


def list_history(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return profile history, newest first."""
    active_profile_id = profile_id or db.ensure_default_profile(conn)
    safe_limit = max(0, int(limit))

    rows = conn.execute(
        """
        SELECT
            stations.*,
            history_entries.last_played_at,
            history_entries.play_count,
            history_entries.station_snapshot_json
        FROM history_entries
        JOIN stations ON stations.id = history_entries.station_id
        WHERE history_entries.profile_id = ?
        ORDER BY history_entries.last_played_at DESC, history_entries.id DESC
        LIMIT ?
        """,
        (active_profile_id, safe_limit),
    ).fetchall()

    return [history_from_row(row) for row in rows]


def add_history_record(
    conn: sqlite3.Connection,
    station: dict[str, Any],
    *,
    played_at: str | None = None,
    profile_id: int | None = None,
) -> None:
    """Insert or update one history entry for a station.

    FluxTuner history keeps one row per station and increments play_count on
    repeated plays. It is not a raw play-event log.
    """
    key = station_key(station)
    if not key:
        return

    active_profile_id = profile_id or db.ensure_default_profile(conn)
    station_id = upsert_station(conn, station)
    timestamp = played_at or db.utc_now()

    previous = conn.execute(
        """
        SELECT play_count
        FROM history_entries
        WHERE profile_id = ?
          AND station_id = ?
        """,
        (active_profile_id, station_id),
    ).fetchone()
    play_count = _safe_int(previous["play_count"]) + 1 if previous is not None else 1

    snapshot_data = dict(station)
    snapshot_data["last_played_at"] = timestamp
    snapshot_data["play_count"] = play_count
    snapshot = station_metadata(snapshot_data)

    conn.execute(
        """
        INSERT INTO history_entries (
            profile_id,
            station_id,
            last_played_at,
            play_count,
            station_snapshot_json
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, station_id) DO UPDATE SET
            last_played_at = excluded.last_played_at,
            play_count = excluded.play_count,
            station_snapshot_json = excluded.station_snapshot_json
        """,
        (
            active_profile_id,
            station_id,
            timestamp,
            play_count,
            snapshot,
        ),
    )


def replace_history(
    conn: sqlite3.Connection,
    history: list[dict[str, Any]],
    *,
    limit: int = 100,
    profile_id: int | None = None,
) -> None:
    """Replace profile history with the provided station dictionaries."""
    active_profile_id = profile_id or db.ensure_default_profile(conn)

    conn.execute(
        "DELETE FROM history_entries WHERE profile_id = ?",
        (active_profile_id,),
    )

    for item in history[:limit]:
        if not station_key(item):
            continue

        station_id = upsert_station(conn, item)
        last_played_at = str(item.get("last_played_at") or db.utc_now())

        conn.execute(
            """
            INSERT OR REPLACE INTO history_entries (
                profile_id,
                station_id,
                last_played_at,
                play_count,
                station_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                active_profile_id,
                station_id,
                last_played_at,
                max(1, _safe_int(item.get("play_count"))),
                station_metadata(item),
            ),
        )


def clear_history_records(
    conn: sqlite3.Connection,
    profile_id: int | None = None,
) -> None:
    """Clear profile history."""
    active_profile_id = profile_id or db.ensure_default_profile(conn)
    conn.execute(
        "DELETE FROM history_entries WHERE profile_id = ?",
        (active_profile_id,),
    )


def _read_json_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("Could not read history data; returning empty history", exc_info=True)
        return []
    except json.JSONDecodeError:
        logger.warning("Invalid history JSON; returning empty history", exc_info=True)
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def _migration_applied(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _mark_migration_applied(conn, name: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (name, applied_at)
        VALUES (?, ?)
        """,
        (name, db.utc_now()),
    )


def _ensure_history_db() -> None:
    """Create SQLite storage and migrate existing JSON history once."""
    migrate_legacy_file(LEGACY_HISTORY_FILE, HISTORY_FILE)

    db_path = _db_path()
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        if _migration_applied(conn, HISTORY_JSON_MIGRATION):
            return

        history = _read_json_history()
        if history:
            replace_history(conn, history, limit=MAX_HISTORY_ITEMS)

        _mark_migration_applied(conn, HISTORY_JSON_MIGRATION)
        conn.commit()


def load_history(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        return list_history(conn, limit=MAX_HISTORY_ITEMS, profile_id=active_profile_id)


def save_history(
    history: list[dict[str, Any]],
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> None:
    _ensure_history_db()

    try:
        with db.connect(_db_path()) as conn:
            active_profile_id = resolve_profile_id(
                conn,
                profile_id=profile_id,
                profile_name=profile_name,
                user_id=user_id,
            )
            replace_history(
                conn,
                history,
                limit=MAX_HISTORY_ITEMS,
                profile_id=active_profile_id,
            )
            conn.commit()
    except OSError:
        logger.error("Could not write history data", exc_info=True)
        raise


def add_history(
    station: dict[str, Any],
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> None:
    if not station.get("url"):
        return

    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        add_history_record(conn, station, profile_id=active_profile_id)
        conn.commit()


def clear_history(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> None:
    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        clear_history_records(conn, profile_id=active_profile_id)
        conn.commit()
