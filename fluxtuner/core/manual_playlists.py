from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from fluxtuner.core.favorites import favorite_display_name, load_favorites
from fluxtuner.core.stations import station_key
from fluxtuner.paths import data_file, migrate_legacy_file

LEGACY_PLAYLISTS_FILE = Path.home() / ".fluxtuner_playlists.json"
PLAYLISTS_FILE = data_file("playlists.json")
migrate_legacy_file(LEGACY_PLAYLISTS_FILE, PLAYLISTS_FILE)


def load_playlists() -> list[dict[str, Any]]:
    if not PLAYLISTS_FILE.exists():
        return []
    try:
        data = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [normalize_playlist(item) for item in data if isinstance(item, dict)]


def save_playlists(playlists: list[dict[str, Any]]) -> None:
    normalized = [
        normalize_playlist(item) for item in playlists if str(item.get("name", "")).strip()
    ]
    PLAYLISTS_FILE.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def normalize_playlist(playlist: dict[str, Any]) -> dict[str, Any]:
    name = str(playlist.get("name") or "").strip()
    station_keys = playlist.get("station_keys", [])
    if not isinstance(station_keys, list):
        station_keys = []
    unique_keys = []
    seen = set()
    for key in station_keys:
        clean_key = str(key).strip()
        if clean_key and clean_key not in seen:
            unique_keys.append(clean_key)
            seen.add(clean_key)
    return {"name": name, "station_keys": unique_keys}


def get_playlist(name: str) -> dict[str, Any] | None:
    clean_name = name.strip().lower()
    for playlist in load_playlists():
        if playlist["name"].lower() == clean_name:
            return playlist
    return None


def create_playlist(name: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False
    playlists = load_playlists()
    if any(item["name"].lower() == clean_name.lower() for item in playlists):
        return False
    playlists.append({"name": clean_name, "station_keys": []})
    save_playlists(playlists)
    return True


def delete_playlist(name: str) -> bool:
    clean_name = name.strip().lower()
    playlists = load_playlists()
    filtered = [item for item in playlists if item["name"].lower() != clean_name]
    if len(filtered) == len(playlists):
        return False
    save_playlists(filtered)
    return True


def add_station_to_playlist(name: str, station: dict[str, Any]) -> bool:
    clean_name = name.strip()
    key = station_key(station)
    if not clean_name or not key:
        return False

    playlists = load_playlists()
    for playlist in playlists:
        if playlist["name"].lower() == clean_name.lower():
            if key in playlist["station_keys"]:
                return False
            playlist["station_keys"].append(key)
            save_playlists(playlists)
            return True

    playlists.append({"name": clean_name, "station_keys": [key]})
    save_playlists(playlists)
    return True


def remove_station_from_playlist(name: str, station: dict[str, Any]) -> bool:
    clean_name = name.strip().lower()
    key = station_key(station)
    if not clean_name or not key:
        return False

    playlists = load_playlists()
    changed = False
    for playlist in playlists:
        if playlist["name"].lower() != clean_name:
            continue
        original_len = len(playlist["station_keys"])
        playlist["station_keys"] = [item for item in playlist["station_keys"] if item != key]
        changed = len(playlist["station_keys"]) != original_len
        break

    if changed:
        save_playlists(playlists)
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
    return random.choice(stations)


def playlist_counts() -> list[tuple[str, int]]:
    return [(item["name"], len(get_playlist_stations(item["name"]))) for item in load_playlists()]


def summarize_playlist(name: str, limit: int = 6) -> str:
    stations = get_playlist_stations(name)
    names = [favorite_display_name(item) for item in stations[:limit]]
    preview = "\n".join(f"• {item}" for item in names) if names else "No stations yet."
    extra = "" if len(stations) <= limit else f"\n… and {len(stations) - limit} more"
    return f"{preview}{extra}"
