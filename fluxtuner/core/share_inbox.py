# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Read-only, user-scoped recommendation listings."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

MAX_PAGE_SIZE = 50
MAX_OFFSET = 10_000


def _validate_identity(conn: sqlite3.Connection, user_id: int) -> None:
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("User unavailable.")

    row = conn.execute(
        """
        SELECT 1 FROM users
        WHERE id = ?
          AND is_active = 1
          AND approval_status = 'approved'
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        raise ValueError("User unavailable.")


def list_shares(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    direction: str,
    status: str = "all",
    limit: int = 20,
    offset: int = 0,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """List authorized metadata without reading recommendation snapshots.

    Expired unresolved recommendations are omitted until lifecycle cleanup
    marks them expired and clears their stored snapshots.
    """
    if direction not in ("inbox", "sent"):
        raise ValueError("Invalid recommendation direction.")

    if status not in ("all", "pending", "resolved"):
        raise ValueError("Invalid recommendation status filter.")

    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("Invalid recommendation page size.")

    if type(offset) is not int or not 0 <= offset <= MAX_OFFSET:
        raise ValueError("Invalid recommendation offset.")

    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Invalid recommendation timestamp.")

    current = (datetime.now(UTC) if now is None else now.astimezone(UTC)).isoformat()

    _validate_identity(conn, user_id)

    # Keep both ownership paths as literal SQL. Parameterize every
    # user-controlled value; never interpolate SQL identifiers or clauses.
    if direction == "inbox":
        query = """
            SELECT
                sh.id,
                sh.kind,
                sh.title,
                sh.status,
                sh.created_at,
                sh.expires_at,
                sh.resolved_at,
                counterpart.username AS counterpart_username
            FROM playlist_shares AS sh
            JOIN users AS counterpart
              ON counterpart.id = sh.sender_user_id
            WHERE sh.recipient_user_id = ?
              AND (sh.status != 'pending' OR sh.expires_at > ?)
              AND (
                  ? = 'all'
                  OR (? = 'pending' AND sh.status = 'pending')
                  OR (? = 'resolved' AND sh.status != 'pending')
              )
            ORDER BY sh.created_at DESC, sh.id DESC
            LIMIT ? OFFSET ?
        """
    else:
        query = """
            SELECT
                sh.id,
                sh.kind,
                sh.title,
                sh.status,
                sh.created_at,
                sh.expires_at,
                sh.resolved_at,
                counterpart.username AS counterpart_username
            FROM playlist_shares AS sh
            JOIN users AS counterpart
              ON counterpart.id = sh.recipient_user_id
            WHERE sh.sender_user_id = ?
              AND (sh.status != 'pending' OR sh.expires_at > ?)
              AND (
                  ? = 'all'
                  OR (? = 'pending' AND sh.status = 'pending')
                  OR (? = 'resolved' AND sh.status != 'pending')
              )
            ORDER BY sh.created_at DESC, sh.id DESC
            LIMIT ? OFFSET ?
        """

    rows = conn.execute(
        query,
        (user_id, current, status, status, status, limit, offset),
    ).fetchall()

    return [
        {
            "id": int(row["id"]),
            "kind": str(row["kind"]),
            "title": str(row["title"]),
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
            "expires_at": str(row["expires_at"]),
            "resolved_at": (str(row["resolved_at"]) if row["resolved_at"] is not None else None),
            "counterpart_username": str(row["counterpart_username"]),
        }
        for row in rows
    ]
