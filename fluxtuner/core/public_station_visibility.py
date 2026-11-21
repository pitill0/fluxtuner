# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Owner-scoped, opt-in publication of favorites from the shared catalog."""

from __future__ import annotations

import sqlite3

from fluxtuner.core import db
from fluxtuner.core.public_featured import _safe_directory_url


def public_station_urls_safe(url: object, resolved_url: object) -> bool:
    """Require both original and resolved stream URLs to be shareable."""
    return _safe_directory_url(url) and _safe_directory_url(resolved_url)


def _owned_favorite_id(
    conn: sqlite3.Connection, *, user_id: int, profile_id: int, station_id: int
) -> int:
    """Validate ownership without revealing another user's station or profile."""
    if any(type(value) is not int or value <= 0 for value in (user_id, profile_id, station_id)):
        raise ValueError("Station unavailable.")
    row = conn.execute(
        """
        SELECT f.id
        FROM favorites AS f
        JOIN profiles AS p ON p.id = f.profile_id AND p.user_id = ?
        JOIN users AS u ON u.id = p.user_id
        WHERE f.profile_id = ? AND f.station_id = ?
          AND u.is_active = 1 AND u.approval_status = 'approved'
        """,
        (user_id, profile_id, station_id),
    ).fetchone()
    if row is None:
        raise ValueError("Station unavailable.")
    return int(row["id"])


def _safe_station(conn: sqlite3.Connection, station_id: int) -> bool:
    row = conn.execute(
        "SELECT url, url_resolved FROM stations WHERE id = ?", (station_id,)
    ).fetchone()
    return bool(
        row and _safe_directory_url(row["url"]) and _safe_directory_url(row["url_resolved"])
    )


def set_station_publication(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    station_id: int,
    published: bool,
) -> None:
    """Change only the requesting user's favorite; caller owns the transaction."""
    if type(published) is not bool:
        raise ValueError("Invalid publication choice.")
    favorite_id = _owned_favorite_id(
        conn, user_id=user_id, profile_id=profile_id, station_id=station_id
    )
    if published:
        if not _safe_station(conn, station_id):
            raise ValueError("Station URL is not eligible for public discovery.")
        conn.execute(
            """
            INSERT INTO public_station_opt_ins (favorite_id, published_at)
            VALUES (?, ?)
            ON CONFLICT(favorite_id) DO NOTHING
            """,
            (favorite_id, db.utc_now()),
        )
    else:
        conn.execute("DELETE FROM public_station_opt_ins WHERE favorite_id = ?", (favorite_id,))


def get_station_publication(
    conn: sqlite3.Connection, *, user_id: int, profile_id: int, station_id: int
) -> bool:
    """Read only the publication choice associated with an owned favorite."""
    favorite_id = _owned_favorite_id(
        conn, user_id=user_id, profile_id=profile_id, station_id=station_id
    )
    return (
        conn.execute(
            "SELECT 1 FROM public_station_opt_ins WHERE favorite_id = ?", (favorite_id,)
        ).fetchone()
        is not None
    )


def list_public_station_ids(conn: sqlite3.Connection) -> list[int]:
    """Return distinct station IDs with a current valid opt-in from an active owner."""
    rows = conn.execute(
        """
        SELECT DISTINCT f.station_id, s.url, s.url_resolved
        FROM public_station_opt_ins AS o
        JOIN favorites AS f ON f.id = o.favorite_id
        JOIN profiles AS p ON p.id = f.profile_id
        JOIN users AS u ON u.id = p.user_id
        JOIN stations AS s ON s.id = f.station_id
        WHERE u.is_active = 1 AND u.approval_status = 'approved'
        ORDER BY f.station_id
        """
    ).fetchall()
    return [
        int(row["station_id"])
        for row in rows
        if _safe_directory_url(row["url"]) and _safe_directory_url(row["url_resolved"])
    ]
