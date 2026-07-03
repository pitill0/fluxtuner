# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core import db
from fluxtuner.core.favorites import load_favorites
from fluxtuner.core.history import load_history
from fluxtuner.core.manual_playlists import get_playlist_stations, load_playlists
from fluxtuner.web.payloads import safe_int, station_payload


def server_health_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "app": __app_name__,
        "version": __version__,
        "mode": "web",
    }


def admin_user_counts(conn: Any) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS users_count,
            SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END)
                AS users_created_today,
            SUM(CASE WHEN created_at >= datetime('now', '-7 days') THEN 1 ELSE 0 END)
                AS users_created_7_days,
            SUM(CASE WHEN created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                AS users_created_30_days,
            SUM(CASE WHEN approval_status = ? THEN 1 ELSE 0 END)
                AS pending_users_count
        FROM users
        """,
        (db.APPROVAL_PENDING,),
    ).fetchone()
    password_change_row = conn.execute(
        """
        SELECT COUNT(*)
        FROM web_password_change_requests
        WHERE status = ?
        """,
        (db.ACCOUNT_CHANGE_PENDING,),
    ).fetchone()

    return {
        "users_count": int(row["users_count"] or 0),
        "users_created_today": int(row["users_created_today"] or 0),
        "users_created_7_days": int(row["users_created_7_days"] or 0),
        "users_created_30_days": int(row["users_created_30_days"] or 0),
        "pending_users_count": int(row["pending_users_count"] or 0),
        "pending_password_change_requests_count": int(password_change_row[0] or 0),
    }


def dashboard_user_payload(user_id: int, profile_name: str | None) -> dict[str, Any]:
    favorites = load_favorites(profile_name=profile_name, user_id=user_id)
    history = load_history(profile_name=profile_name, user_id=user_id)
    playlists = load_playlists(profile_name=profile_name, user_id=user_id)
    playlist_stations_count = 0

    for playlist in playlists:
        playlist_stations_count += len(
            get_playlist_stations(
                str(playlist["name"]),
                profile_name=profile_name,
                user_id=user_id,
            )
        )

    favorite_highlights = sorted(
        favorites,
        key=lambda station: (
            safe_int(station.get("play_count")),
            str(station.get("last_played_at") or ""),
        ),
        reverse=True,
    )[:5]

    return {
        "favorites_count": len(favorites),
        "playlists_count": len(playlists),
        "playlist_stations_count": playlist_stations_count,
        "history_count": len(history),
        "recent_history": [station_payload(station) for station in history[:5]],
        "favorite_highlights": [station_payload(station) for station in favorite_highlights],
    }
