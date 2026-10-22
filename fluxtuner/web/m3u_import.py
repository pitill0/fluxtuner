# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.favorites import list_favorites
from fluxtuner.core.m3u_import import import_m3u, parse_station_collection
from fluxtuner.core.profiles import get_profile_by_name


class DestinationConflict(ValueError):
    """The requested new playlist already exists."""


def _profile_id(conn: sqlite3.Connection, *, user_id: int, profile_name: str | None) -> int:
    name = db.DEFAULT_PROFILE_NAME if profile_name is None else profile_name
    profile = get_profile_by_name(conn, name, user_id=user_id)
    if profile is None:
        raise LookupError("The selected profile is unavailable.")
    return int(profile["id"])


def preview_payload(data: bytes, *, user_id: int, profile_name: str | None) -> dict[str, Any]:
    with closing(db.connect()) as conn:
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile_name)
        preview = parse_station_collection(data)
        if not preview.entries:
            raise ValueError("The file contains no valid stations.")
        existing_urls = {
            station["url_resolved"] for station in list_favorites(conn, profile_id=profile_id)
        }
        return {
            "entries": [
                {**asdict(entry), "existing": entry.url in existing_urls}
                for entry in preview.entries
            ],
            "issues": [asdict(issue) for issue in preview.issues],
            "duplicates": preview.duplicates,
            "playlists": [
                playlist["name"] for playlist in db.list_playlists(conn, profile_id=profile_id)
            ],
        }


def import_payload(
    data: bytes,
    *,
    user_id: int,
    profile_name: str | None,
    playlist_name: str,
    existing: bool,
) -> dict[str, Any]:
    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile_name)
        preview = parse_station_collection(data)
        if not preview.entries:
            raise ValueError("The file contains no valid stations.")

        destination = db.get_playlist_record(conn, playlist_name, profile_id=profile_id)
        if existing and destination is None:
            raise LookupError("The selected playlist is unavailable.")
        if not existing and destination is not None:
            raise DestinationConflict("A playlist with this name already exists.")

        result = import_m3u(
            conn,
            profile_id=profile_id,
            playlist_name=playlist_name,
            entries=preview.entries,
        )
        conn.commit()
        return {"status": "ok", "name": playlist_name.strip(), **asdict(result)}
