from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.favorites import favorite_display_name, load_favorites
from fluxtuner.core.stations import station_key
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import data_file, migrate_legacy_file

logger = get_logger(__name__)

LEGACY_PLAYLISTS_FILE = Path.home() / ".fluxtuner_playlists.json"
PLAYLISTS_FILE = data_file("playlists.json")
PLAYLISTS_JSON_MIGRATION = "playlists_json_v1"


def _db_path() -> Path:
    """Return the SQLite DB path next to the current playlists file.

    Tests patch PLAYLISTS_FILE directly. Deriving the DB path from it keeps the
    SQLite-backed implementation isolated in the same tmp directory.
    """
    return PLAYLISTS_FILE.parent / "fluxtuner.db"


def _normalize_station_keys(keys: Any) -> list[str]:
    if not isinstance(keys, list):
        return []

    unique_keys: list[str] = []
    seen: set[str] = set()

    for key in keys:
        clean_key = str(key).strip()
        if clean_key and clean_key not in seen:
            unique_keys.append(clean_key)
            seen.add(clean_key)

    return unique_keys


def _read_json_playlists() -> list[dict[str, Any]]:
    if not PLAYLISTS_FILE.exists():
        return []

    try:
        data = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("Could not read playlists data; returning empty playlists", exc_info=True)
        return []
    except json.JSONDecodeError:
        logger.warning("Invalid playlists JSON; returning empty playlists", exc_info=True)
        return []

    if not isinstance(data, list):
        return []

    return [normalize_playlist(item) for item in data if isinstance(item, dict)]


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


def _ensure_playlists_db() -> None:
    """Create SQLite storage and migrate existing JSON playlists once."""
    migrate_legacy_file(LEGACY_PLAYLISTS_FILE, PLAYLISTS_FILE)

    db_path = _db_path()
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        if _migration_applied(conn, PLAYLISTS_JSON_MIGRATION):
            return

        playlists = _read_json_playlists()
        if playlists:
            db.replace_playlists(conn, playlists)

        _mark_migration_applied(conn, PLAYLISTS_JSON_MIGRATION)
        conn.commit()


def load_playlists() -> list[dict[str, Any]]:
    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        return [normalize_playlist(item) for item in db.list_playlists(conn)]


def save_playlists(playlists: list[dict[str, Any]]) -> None:
    _ensure_playlists_db()

    normalized = [
        normalize_playlist(item) for item in playlists if str(item.get("name", "")).strip()
    ]

    with db.connect(_db_path()) as conn:
        db.replace_playlists(conn, normalized)
        conn.commit()


def normalize_playlist(playlist: dict[str, Any]) -> dict[str, Any]:
    name = str(playlist.get("name") or "").strip()
    station_keys = _normalize_station_keys(playlist.get("station_keys", []))
    return {"name": name, "station_keys": station_keys}


def get_playlist(name: str) -> dict[str, Any] | None:
    clean_name = name.strip().lower()
    if not clean_name:
        return None

    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        playlist = db.get_playlist_record(conn, clean_name)

    return normalize_playlist(playlist) if playlist else None


def create_playlist(name: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        created = db.create_playlist_record(conn, clean_name)
        conn.commit()
        return created


def delete_playlist(name: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        removed = db.delete_playlist_record(conn, clean_name)
        conn.commit()
        return removed


def add_station_to_playlist(name: str, station: dict[str, Any]) -> bool:
    clean_name = name.strip()
    key = station_key(station)
    if not clean_name or not key:
        return False

    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        added = db.add_station_to_playlist_record(conn, clean_name, station)
        conn.commit()
        return added


def remove_station_from_playlist(name: str, station: dict[str, Any]) -> bool:
    clean_name = name.strip()
    key = station_key(station)
    if not clean_name or not key:
        return False

    _ensure_playlists_db()

    with db.connect(_db_path()) as conn:
        changed = db.remove_station_from_playlist_record(conn, clean_name, station)
        conn.commit()
        return changed


def get_playlist_stations(name: str) -> list[dict[str, Any]]:
    playlist = get_playlist(name)
    if not playlist:
        return []

    favorites = load_favorites()
    favorite_map = {station_key(item): item for item in favorites if station_key(item)}
    return [favorite_map[key] for key in playlist["station_keys"] if key in favorite_map]


def random_from_playlist(name: str) -> dict[str, Any] | None:
    stations = get_playlist_stations(name)
    if not stations:
        return None
    return secrets.choice(stations)


def playlist_counts() -> list[tuple[str, int]]:
    return [(item["name"], len(get_playlist_stations(item["name"]))) for item in load_playlists()]


def summarize_playlist(name: str, limit: int = 6) -> str:
    stations = get_playlist_stations(name)
    names = [favorite_display_name(item) for item in stations[:limit]]
    preview = "\n".join(f"• {item}" for item in names) if names else "No stations yet."
    extra = "" if len(stations) <= limit else f"\n… and {len(stations) - limit} more"
    return f"{preview}{extra}"
