from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.stations import station_key, station_name
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


def _normalize_favorite_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    return sorted({str(tag).strip() for tag in tags if str(tag).strip()})


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
            db.replace_favorites(conn, favorites)

        _mark_migration_applied(conn, FAVORITES_JSON_MIGRATION)
        conn.commit()


def load_favorites() -> list[dict[str, Any]]:
    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        return [normalize_favorite(item) for item in db.list_favorites(conn)]


def save_favorites(favorites: list[dict[str, Any]]) -> None:
    _ensure_favorites_db()

    normalized = [normalize_favorite(item) for item in favorites if station_key(item)]

    with db.connect(_db_path()) as conn:
        db.replace_favorites(conn, normalized)
        conn.commit()


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


def add_favorite(station: dict[str, Any]) -> bool:
    _ensure_favorites_db()

    key = station_key(station)
    if not key:
        return False

    favorite = normalize_favorite(station)

    with db.connect(_db_path()) as conn:
        added = db.add_favorite_record(conn, favorite)
        conn.commit()
        return added


def remove_favorite(url: str) -> bool:
    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        removed = db.remove_favorite_record(conn, url)
        conn.commit()
        return removed


def update_favorite(
    url: str,
    *,
    custom_name: str | None | object = ...,
    favorite_tags: list[str] | None | object = ...,
) -> bool:
    _ensure_favorites_db()

    with db.connect(_db_path()) as conn:
        changed = db.update_favorite_record(
            conn,
            url,
            custom_name=custom_name,
            favorite_tags=favorite_tags,
        )
        conn.commit()
        return changed


def filter_favorites_by_tag(tag: str) -> list[dict[str, Any]]:
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return load_favorites()
    return [
        favorite
        for favorite in load_favorites()
        if clean_tag in {str(item).lower() for item in favorite.get("favorite_tags", [])}
    ]


def all_favorite_tags() -> list[str]:
    tags: set[str] = set()
    for favorite in load_favorites():
        tags.update(_normalize_favorite_tags(favorite.get("favorite_tags")))
    return sorted(tags, key=str.lower)
