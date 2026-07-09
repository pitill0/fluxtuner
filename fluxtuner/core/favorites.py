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
    station_name,
    upsert_station,
)
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import data_file, migrate_legacy_file

logger = get_logger(__name__)

LEGACY_FAVORITES_FILE = Path.home() / ".fluxtuner_favorites.json"
FAVORITES_FILE = data_file("favorites.json")
FAVORITES_JSON_MIGRATION = "favorites_json_v1"


def _db_path() -> Path:
    """Return the SQLite DB path next to the current favorites file.

    Tests patch FAVORITES_FILE directly. Deriving the DB path from it keeps the
    SQLite-backed implementation isolated in the same tmp directory without
    requiring every existing test to patch db.DB_FILE too.
    """
    return FAVORITES_FILE.parent / "fluxtuner.db"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def _normalize_favorite_tags(tags: Any) -> list[str]:
    return normalize_favorite_tags(tags)


def normalize_favorite_tags(value: Any) -> list[str]:
    """Return normalized user-defined favorite tags."""
    if not isinstance(value, list):
        return []
    return sorted({str(tag).strip() for tag in value if str(tag).strip()})


def favorite_tags_to_json(value: Any) -> str:
    """Serialize favorite tags using the current FluxTuner normalization rules."""
    return json.dumps(
        normalize_favorite_tags(value),
        ensure_ascii=False,
        sort_keys=True,
    )


def favorite_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a favorite station dict from a joined favorite/station row."""
    favorite = station_from_row(row)

    custom_name = _clean_text(row["custom_name"])
    favorite["custom_name"] = custom_name

    try:
        raw_tags = json.loads(str(row["favorite_tags_json"] or "[]"))
    except json.JSONDecodeError:
        raw_tags = []

    favorite["favorite_tags"] = normalize_favorite_tags(raw_tags)

    if not favorite.get("url_resolved"):
        favorite["url_resolved"] = favorite.get("url")

    return favorite


def list_favorites(
    conn: sqlite3.Connection,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return favorites for a profile as FluxTuner station dictionaries."""
    active_profile_id = profile_id or db.ensure_default_profile(conn)

    rows = conn.execute(
        """
        SELECT
            stations.*,
            favorites.custom_name,
            favorites.favorite_tags_json
        FROM favorites
        JOIN stations ON stations.id = favorites.station_id
        WHERE favorites.profile_id = ?
        ORDER BY favorites.created_at ASC, favorites.id ASC
        """,
        (active_profile_id,),
    ).fetchall()

    return [favorite_from_row(row) for row in rows]


def add_favorite_record(
    conn: sqlite3.Connection,
    station: dict[str, Any],
    profile_id: int | None = None,
) -> bool:
    """Add a favorite for a profile.

    Returns False when the station is already a favorite.
    """
    active_profile_id = profile_id or db.ensure_default_profile(conn)
    station_id = upsert_station(conn, station)
    now = db.utc_now()

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO favorites (
            profile_id,
            station_id,
            custom_name,
            favorite_tags_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            active_profile_id,
            station_id,
            _clean_text(station.get("custom_name")),
            favorite_tags_to_json(station.get("favorite_tags")),
            now,
            now,
        ),
    )

    return cursor.rowcount > 0


def remove_favorite_record(
    conn: sqlite3.Connection,
    key: str,
    profile_id: int | None = None,
) -> bool:
    """Remove a favorite by station key or raw URL."""
    clean_key = key.strip()
    if not clean_key:
        return False

    active_profile_id = profile_id or db.ensure_default_profile(conn)

    cursor = conn.execute(
        """
        DELETE FROM favorites
        WHERE profile_id = ?
          AND station_id IN (
              SELECT id
              FROM stations
              WHERE station_key = ?
                 OR url = ?
                 OR url_resolved = ?
          )
        """,
        (active_profile_id, clean_key, clean_key, clean_key),
    )

    return cursor.rowcount > 0


def update_favorite_record(
    conn: sqlite3.Connection,
    key: str,
    *,
    custom_name: Any = ...,
    favorite_tags: Any = ...,
    profile_id: int | None = None,
) -> bool:
    """Update editable favorite metadata for a saved station."""
    clean_key = key.strip()
    if not clean_key:
        return False

    if custom_name is ... and favorite_tags is ...:
        return False

    active_profile_id = profile_id or db.ensure_default_profile(conn)
    now = db.utc_now()

    if custom_name is not ... and favorite_tags is not ...:
        cursor = conn.execute(
            """
            UPDATE favorites
            SET custom_name = ?,
                favorite_tags_json = ?,
                updated_at = ?
            WHERE profile_id = ?
              AND station_id IN (
                  SELECT id
                  FROM stations
                  WHERE station_key = ?
                     OR url = ?
                     OR url_resolved = ?
              )
            """,
            (
                _clean_text(custom_name),
                favorite_tags_to_json(favorite_tags or []),
                now,
                active_profile_id,
                clean_key,
                clean_key,
                clean_key,
            ),
        )
        return cursor.rowcount > 0

    if custom_name is not ...:
        cursor = conn.execute(
            """
            UPDATE favorites
            SET custom_name = ?,
                updated_at = ?
            WHERE profile_id = ?
              AND station_id IN (
                  SELECT id
                  FROM stations
                  WHERE station_key = ?
                     OR url = ?
                     OR url_resolved = ?
              )
            """,
            (
                _clean_text(custom_name),
                now,
                active_profile_id,
                clean_key,
                clean_key,
                clean_key,
            ),
        )
        return cursor.rowcount > 0

    cursor = conn.execute(
        """
        UPDATE favorites
        SET favorite_tags_json = ?,
            updated_at = ?
        WHERE profile_id = ?
          AND station_id IN (
              SELECT id
              FROM stations
              WHERE station_key = ?
                 OR url = ?
                 OR url_resolved = ?
          )
        """,
        (
            favorite_tags_to_json(favorite_tags or []),
            now,
            active_profile_id,
            clean_key,
            clean_key,
            clean_key,
        ),
    )
    return cursor.rowcount > 0


def replace_favorites(
    conn: sqlite3.Connection,
    favorites: list[dict[str, Any]],
    profile_id: int | None = None,
) -> None:
    """Replace all favorites for a profile with the provided station dictionaries."""
    active_profile_id = profile_id or db.ensure_default_profile(conn)

    conn.execute(
        "DELETE FROM favorites WHERE profile_id = ?",
        (active_profile_id,),
    )

    for favorite in favorites:
        if station_key(favorite):
            add_favorite_record(conn, favorite, active_profile_id)


def _read_json_favorites() -> list[dict[str, Any]]:
    if not FAVORITES_FILE.exists():
        return []

    try:
        data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("Could not read favorites data; returning empty favorites", exc_info=True)
        return []
    except json.JSONDecodeError:
        logger.warning("Invalid favorites JSON; returning empty favorites", exc_info=True)
        return []

    if not isinstance(data, list):
        return []

    return [normalize_favorite(item) for item in data if isinstance(item, dict)]


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


def _ensure_favorites_db() -> None:
    """Create SQLite storage and migrate existing JSON favorites once."""
    migrate_legacy_file(LEGACY_FAVORITES_FILE, FAVORITES_FILE)

    db_path = _db_path()
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        if _migration_applied(conn, FAVORITES_JSON_MIGRATION):
            return

        favorites = _read_json_favorites()
        if favorites:
            replace_favorites(conn, favorites)

        _mark_migration_applied(conn, FAVORITES_JSON_MIGRATION)
        conn.commit()


def load_favorites(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        return [
            normalize_favorite(item) for item in list_favorites(conn, profile_id=active_profile_id)
        ]


def save_favorites(
    favorites: list[dict[str, Any]],
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> None:
    _ensure_favorites_db()

    normalized = [normalize_favorite(item) for item in favorites if station_key(item)]

    try:
        with db.connect(_db_path()) as conn:
            active_profile_id = resolve_profile_id(
                conn,
                profile_id=profile_id,
                profile_name=profile_name,
                user_id=user_id,
            )
            replace_favorites(conn, normalized, profile_id=active_profile_id)
            conn.commit()
    except OSError:
        logger.error("Could not write favorites data", exc_info=True)
        raise


def normalize_favorite(station: dict[str, Any]) -> dict[str, Any]:
    """Return a favorite with the current metadata schema.

    Older FluxTuner favorites were saved as raw Radio Browser station dictionaries.
    This keeps them compatible while adding custom display names and user tags.
    """
    favorite = dict(station)
    favorite.setdefault("custom_name", None)
    favorite.setdefault("favorite_tags", [])

    # Backward compatibility: early v13 experiments used a generic "tags" list for
    # user tags, while Radio Browser uses "tags" as a comma-separated string.
    raw_user_tags = favorite.get("favorite_tags")
    favorite["favorite_tags"] = _normalize_favorite_tags(raw_user_tags)

    if not favorite.get("url_resolved"):
        favorite["url_resolved"] = favorite.get("url")

    return favorite


def favorite_display_name(station: dict[str, Any]) -> str:
    custom_name = station.get("custom_name")
    if isinstance(custom_name, str) and custom_name.strip():
        return custom_name.strip()
    return station_name(station)


def add_favorite(
    station: dict[str, Any],
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> bool:
    key = station_key(station)
    if not key:
        return False

    _ensure_favorites_db()

    favorite = normalize_favorite(station)
    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        added = add_favorite_record(conn, favorite, profile_id=active_profile_id)
        conn.commit()
        return added


def remove_favorite(
    station: dict[str, Any] | str,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> bool:
    key = station_key(station)
    if not key:
        return False

    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        removed = remove_favorite_record(conn, key, profile_id=active_profile_id)
        conn.commit()
        return removed


def update_favorite(
    station: dict[str, Any] | str,
    *,
    custom_name: Any = ...,
    favorite_tags: Any = ...,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> bool:
    key = station.strip() if isinstance(station, str) else station_key(station) or ""

    if not key:
        return False

    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        active_profile_id = resolve_profile_id(
            conn,
            profile_id=profile_id,
            profile_name=profile_name,
            user_id=user_id,
        )
        changed = update_favorite_record(
            conn,
            key,
            custom_name=custom_name,
            favorite_tags=favorite_tags,
            profile_id=active_profile_id,
        )
        conn.commit()
        return changed


def filter_favorites_by_tag(
    tag: str,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return load_favorites(profile_id=profile_id, profile_name=profile_name, user_id=user_id)

    return [
        favorite
        for favorite in load_favorites(
            profile_id=profile_id, profile_name=profile_name, user_id=user_id
        )
        if clean_tag in {item.lower() for item in favorite.get("favorite_tags", [])}
    ]


def all_favorite_tags(
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> list[str]:
    tags: set[str] = set()
    for favorite in load_favorites(
        profile_id=profile_id, profile_name=profile_name, user_id=user_id
    ):
        tags.update(favorite.get("favorite_tags", []))
    return sorted(tags, key=str.lower)
