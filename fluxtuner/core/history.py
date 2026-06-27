from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fluxtuner.core import db
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


def _resolve_profile_id(
    conn,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> int | None:
    if profile_id is not None:
        return profile_id

    if profile_name is None:
        return None

    return db.get_or_create_profile(conn, profile_name)


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
            db.replace_history(conn, history, limit=MAX_HISTORY_ITEMS)

        _mark_migration_applied(conn, HISTORY_JSON_MIGRATION)
        conn.commit()


def load_history(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = _resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
        )
        return db.list_history(conn, limit=MAX_HISTORY_ITEMS, profile_id=active_profile_id)


def save_history(
    history: list[dict[str, Any]],
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> None:
    _ensure_history_db()

    try:
        with db.connect(_db_path()) as conn:
            active_profile_id = _resolve_profile_id(
                conn,
                profile_id=profile_id,
                profile_name=profile_name,
            )
            db.replace_history(
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
) -> None:
    if not station.get("url"):
        return

    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = _resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
        )
        db.add_history_record(conn, station, profile_id=active_profile_id)
        conn.commit()


def clear_history(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> None:
    _ensure_history_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = _resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
        )
        db.clear_history_records(conn, profile_id=active_profile_id)
        conn.commit()
