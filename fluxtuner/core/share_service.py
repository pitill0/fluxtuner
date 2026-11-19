# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Instance-local, user-owned station and playlist recommendations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.playlist_export import resolve_playlist_entries
from fluxtuner.core.share_snapshots import (
    build_share_snapshot,
    validate_share_title,
)
from fluxtuner.core.users import get_user_by_username

SHARE_TTL_DAYS = 7
MAX_PENDING_SENT = 20
MAX_PENDING_INBOX = 20
MAX_PENDING_TO_RECIPIENT = 5
MAX_SENT_PER_DAY = 30


def _approved_user(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM users
        WHERE id = ?
          AND is_active = 1
          AND approval_status = 'approved'
        """,
        (user_id,),
    ).fetchone()
    return row is not None


def _owned_station(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    station_key: str,
) -> M3UEntry:
    if not isinstance(station_key, str) or not station_key.strip():
        raise ValueError("Station unavailable.")

    row = conn.execute(
        """
        SELECT
            s.station_key,
            COALESCE(f.custom_name, s.name) AS display_name
        FROM stations AS s
        JOIN profiles AS p
          ON p.id = ?
         AND p.user_id = ?
        LEFT JOIN favorites AS f
          ON f.station_id = s.id
         AND f.profile_id = p.id
        WHERE s.station_key = ?
          AND (
              f.id IS NOT NULL
              OR EXISTS (
                  SELECT 1
                  FROM playlist_stations AS ps
                  JOIN playlists AS pl ON pl.id = ps.playlist_id
                  WHERE ps.station_id = s.id
                    AND pl.profile_id = p.id
              )
          )
        """,
        (profile_id, user_id, station_key),
    ).fetchone()

    if row is None:
        raise ValueError("Station unavailable.")

    return M3UEntry(
        name=str(row["display_name"]),
        url=str(row["station_key"]),
    )


def _source_snapshot(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    kind: str,
    station_key: str | None,
    playlist_name: str | None,
) -> tuple[str, str]:
    if kind == "station":
        if station_key is None or playlist_name is not None:
            raise ValueError("Invalid station selection.")
        entry = _owned_station(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_key=station_key,
        )
        title = validate_share_title(entry.name)
        return title, build_share_snapshot(kind="station", entries=(entry,))

    if kind == "playlist":
        if playlist_name is None or station_key is not None:
            raise ValueError("Invalid playlist selection.")

        entries = resolve_playlist_entries(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            playlist_name=playlist_name,
        )

        row = conn.execute(
            """
            SELECT pl.name
            FROM playlists AS pl
            JOIN profiles AS p ON p.id = pl.profile_id
            WHERE p.user_id = ?
              AND p.id = ?
              AND lower(pl.name) = lower(?)
            """,
            (user_id, profile_id, playlist_name.strip()),
        ).fetchone()

        if row is None:
            raise ValueError("Playlist unavailable.")

        title = validate_share_title(str(row["name"]))
        return title, build_share_snapshot(kind="playlist", entries=entries)

    raise ValueError("Invalid recommendation kind.")


def _check_send_limits(
    conn: sqlite3.Connection,
    *,
    sender_id: int,
    recipient_id: int,
    kind: str,
    snapshot: str,
    now: datetime,
) -> None:
    current = now.isoformat()
    cutoff = (now - timedelta(days=1)).isoformat()

    pending_sent = conn.execute(
        """
        SELECT COUNT(*) FROM playlist_shares
        WHERE sender_user_id = ?
          AND status = 'pending'
          AND expires_at > ?
        """,
        (sender_id, current),
    ).fetchone()[0]

    if pending_sent >= MAX_PENDING_SENT:
        raise ValueError("Recommendation sending limit reached.")

    pending_inbox = conn.execute(
        """
        SELECT COUNT(*) FROM playlist_shares
        WHERE recipient_user_id = ?
          AND status = 'pending'
          AND expires_at > ?
        """,
        (recipient_id, current),
    ).fetchone()[0]

    if pending_inbox >= MAX_PENDING_INBOX:
        raise ValueError("Recommendation inbox limit reached.")

    pending_to_recipient = conn.execute(
        """
        SELECT COUNT(*) FROM playlist_shares
        WHERE sender_user_id = ?
          AND recipient_user_id = ?
          AND status = 'pending'
          AND expires_at > ?
        """,
        (sender_id, recipient_id, current),
    ).fetchone()[0]

    if pending_to_recipient >= MAX_PENDING_TO_RECIPIENT:
        raise ValueError("Recommendation sending limit reached.")

    duplicate = conn.execute(
        """
        SELECT 1 FROM playlist_shares
        WHERE sender_user_id = ?
          AND recipient_user_id = ?
          AND kind = ?
          AND snapshot_json = ?
          AND status = 'pending'
          AND expires_at > ?
        LIMIT 1
        """,
        (sender_id, recipient_id, kind, snapshot, current),
    ).fetchone()

    if duplicate is not None:
        raise ValueError("Recommendation is already pending.")

    recent_sent = conn.execute(
        """
        SELECT COUNT(*) FROM playlist_shares
        WHERE sender_user_id = ?
          AND created_at > ?
        """,
        (sender_id, cutoff),
    ).fetchone()[0]

    if recent_sent >= MAX_SENT_PER_DAY:
        raise ValueError("Recommendation sending limit reached.")


def create_share(
    conn: sqlite3.Connection,
    *,
    sender_user_id: int,
    recipient_username: str,
    source_profile_id: int,
    kind: str,
    station_key: str | None = None,
    playlist_name: str | None = None,
    now: datetime | None = None,
) -> int:
    """Create one recommendation atomically from server-owned library data.

    Requires a connection without an existing transaction. The caller supplies
    a trusted authenticated sender identity, not an identity from request data.
    """
    if conn.in_transaction:
        raise ValueError("Recommendation requires an independent transaction.")

    if (
        type(sender_user_id) is not int
        or sender_user_id <= 0
        or type(source_profile_id) is not int
        or source_profile_id <= 0
    ):
        raise ValueError("Invalid recommendation identity.")

    if not isinstance(recipient_username, str) or not 1 <= len(recipient_username.strip()) <= 80:
        raise ValueError("Recipient unavailable.")

    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Invalid recommendation timestamp.")

    current = datetime.now(UTC) if now is None else now.astimezone(UTC)

    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _approved_user(conn, sender_user_id):
            raise ValueError("Sender unavailable.")

        recipient = get_user_by_username(conn, recipient_username)
        if (
            recipient is None
            or not recipient["is_active"]
            or recipient["approval_status"] != "approved"
            or recipient["id"] == sender_user_id
        ):
            raise ValueError("Recipient unavailable.")

        profile = conn.execute(
            """
            SELECT 1 FROM profiles
            WHERE id = ? AND user_id = ?
            """,
            (source_profile_id, sender_user_id),
        ).fetchone()

        if profile is None:
            raise ValueError("Source unavailable.")

        title, snapshot = _source_snapshot(
            conn,
            user_id=sender_user_id,
            profile_id=source_profile_id,
            kind=kind,
            station_key=station_key,
            playlist_name=playlist_name,
        )

        recipient_id = int(recipient["id"])

        _check_send_limits(
            conn,
            sender_id=sender_user_id,
            recipient_id=recipient_id,
            kind=kind,
            snapshot=snapshot,
            now=current,
        )

        cursor = conn.execute(
            """
            INSERT INTO playlist_shares (
                sender_user_id,
                recipient_user_id,
                source_profile_id,
                kind,
                title,
                snapshot_json,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sender_user_id,
                recipient_id,
                source_profile_id,
                kind,
                title,
                snapshot,
                current.isoformat(),
                (current + timedelta(days=SHARE_TTL_DAYS)).isoformat(),
            ),
        )

        if cursor.lastrowid is None:
            raise RuntimeError("Could not create recommendation.")

        share_id = int(cursor.lastrowid)
        conn.commit()
        return share_id
    except Exception:
        conn.rollback()
        raise
