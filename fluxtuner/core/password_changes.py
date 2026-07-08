# SPDX-License-Identifier: MIT
#
# FluxTuner core storage remains MIT for local application use.
# Web/server-specific password-change request storage behavior in this file is
# additionally governed by LICENSE-WEB when used to operate, host, sell or
# monetize FluxTuner Web/server features.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

ACCOUNT_CHANGE_PENDING = "pending"
ACCOUNT_CHANGE_APPROVED = "approved"
ACCOUNT_CHANGE_REJECTED = "rejected"
ACCOUNT_CHANGE_EXPIRED = "expired"
ACCOUNT_CHANGE_STATUSES = {
    ACCOUNT_CHANGE_PENDING,
    ACCOUNT_CHANGE_APPROVED,
    ACCOUNT_CHANGE_REJECTED,
    ACCOUNT_CHANGE_EXPIRED,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def validate_password_change_status(status: str) -> str:
    clean_status = str(status or "").strip().lower()
    if clean_status not in ACCOUNT_CHANGE_STATUSES:
        raise ValueError(f"Invalid password change request status: {status}")
    return clean_status


def password_change_request_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a password change request dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "username": str(row["username"]),
        "display_name": str(row["display_name"] or row["username"]),
        "password_hash": str(row["password_hash"]),
        "note": (str(row["note"]) if row["note"] is not None else None),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]),
        "resolved_at": (str(row["resolved_at"]) if row["resolved_at"] is not None else None),
        "resolved_by_user_id": (
            int(row["resolved_by_user_id"]) if row["resolved_by_user_id"] is not None else None
        ),
    }


def upsert_pending_password_change_request(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    password_hash: str,
    note: str | None = None,
    created_at: str | None = None,
    expires_at: str,
) -> int:
    """Create or replace the active pending password change request for a user."""
    now = created_at or utc_now()
    clean_note = _clean_text(note)

    row = conn.execute(
        """
        SELECT id
        FROM web_password_change_requests
        WHERE user_id = ? AND status = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, ACCOUNT_CHANGE_PENDING),
    ).fetchone()

    if row is not None:
        request_id = int(row["id"])
        conn.execute(
            """
            UPDATE web_password_change_requests
            SET
                password_hash = ?,
                note = ?,
                created_at = ?,
                expires_at = ?,
                resolved_at = NULL,
                resolved_by_user_id = NULL
            WHERE id = ?
            """,
            (password_hash, clean_note, now, expires_at, request_id),
        )
        return request_id

    cursor = conn.execute(
        """
        INSERT INTO web_password_change_requests (
            user_id,
            password_hash,
            note,
            status,
            created_at,
            expires_at,
            resolved_at,
            resolved_by_user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (user_id, password_hash, clean_note, ACCOUNT_CHANGE_PENDING, now, expires_at),
    )

    inserted_request_id = cursor.lastrowid
    if inserted_request_id is None:
        raise RuntimeError("Could not create password change request.")
    return int(inserted_request_id)


def list_password_change_requests(
    conn: sqlite3.Connection,
    *,
    status: str | None = ACCOUNT_CHANGE_PENDING,
) -> list[dict[str, Any]]:
    """Return password change requests joined with their target users."""
    base_query = """
        SELECT
            r.id,
            r.user_id,
            u.username,
            u.display_name,
            r.password_hash,
            r.note,
            r.status,
            r.created_at,
            r.expires_at,
            r.resolved_at,
            r.resolved_by_user_id
        FROM web_password_change_requests r
        JOIN users u ON u.id = r.user_id
    """
    if status is None:
        query = (
            base_query
            + """
        ORDER BY r.created_at DESC, r.id DESC
        """
        )
        params: tuple[Any, ...] = ()
    else:
        query = (
            base_query
            + """
        WHERE r.status = ?
        ORDER BY r.created_at DESC, r.id DESC
        """
        )
        params = (validate_password_change_status(status),)

    rows = conn.execute(query, params).fetchall()

    return [password_change_request_from_row(row) for row in rows]


def user_has_pending_password_change_request(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    now: str | None = None,
) -> bool:
    """Return whether an active pending password change request locks login."""
    row = conn.execute(
        """
        SELECT 1
        FROM web_password_change_requests
        WHERE user_id = ?
          AND status = ?
          AND expires_at > ?
        LIMIT 1
        """,
        (user_id, ACCOUNT_CHANGE_PENDING, now or utc_now()),
    ).fetchone()
    return row is not None


def get_password_change_request(
    conn: sqlite3.Connection,
    request_id: int,
) -> dict[str, Any] | None:
    """Return one password change request joined with its target user."""
    row = conn.execute(
        """
        SELECT
            r.id,
            r.user_id,
            u.username,
            u.display_name,
            r.password_hash,
            r.note,
            r.status,
            r.created_at,
            r.expires_at,
            r.resolved_at,
            r.resolved_by_user_id
        FROM web_password_change_requests r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()

    if row is None:
        return None
    return password_change_request_from_row(row)


def set_password_change_request_status(
    conn: sqlite3.Connection,
    request_id: int,
    status: str,
    *,
    resolved_by_user_id: int | None = None,
) -> None:
    """Resolve a password change request with a final status."""
    clean_status = validate_password_change_status(status)
    conn.execute(
        """
        UPDATE web_password_change_requests
        SET
            status = ?,
            resolved_at = ?,
            resolved_by_user_id = ?
        WHERE id = ?
        """,
        (clean_status, utc_now(), resolved_by_user_id, request_id),
    )
