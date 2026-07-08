# SPDX-License-Identifier: MIT
#
# FluxTuner core storage remains MIT for local application use.
# Web/server-specific user and account-state storage behavior in this file is
# additionally governed by LICENSE-WEB when used to operate, host, sell or
# monetize FluxTuner Web/server features.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

APPROVAL_APPROVED = "approved"
APPROVAL_PENDING = "pending"
APPROVAL_REJECTED = "rejected"
APPROVAL_DISABLED = "disabled"
APPROVAL_STATUSES = {
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    APPROVAL_DISABLED,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def validate_approval_status(status: str) -> str:
    clean_status = str(status or "").strip().lower()
    if clean_status not in APPROVAL_STATUSES:
        raise ValueError(f"Invalid approval status: {status}")
    return clean_status


def active_for_approval_status(status: str) -> bool:
    """Return whether a user with the approval status may authenticate."""
    return validate_approval_status(status) == APPROVAL_APPROVED


def normalize_username(username: str) -> str:
    """Normalize a username for storage and lookup."""
    return username.strip()


def user_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a public user dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "display_name": str(row["display_name"] or row["username"]),
        "password_hash": (str(row["password_hash"]) if row["password_hash"] is not None else None),
        "is_admin": bool(row["is_admin"]),
        "is_active": bool(row["is_active"]),
        "approval_status": str(row["approval_status"]),
        "signup_note": (str(row["signup_note"]) if row["signup_note"] is not None else None),
        "reviewed_at": (str(row["reviewed_at"]) if row["reviewed_at"] is not None else None),
        "reviewed_by_user_id": (
            int(row["reviewed_by_user_id"]) if row["reviewed_by_user_id"] is not None else None
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def get_user_by_username(
    conn: sqlite3.Connection,
    username: str,
) -> dict[str, Any] | None:
    """Return a user by username using case-insensitive lookup."""
    clean_username = normalize_username(username)
    if not clean_username:
        return None

    row = conn.execute(
        """
        SELECT
            id,
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        FROM users
        WHERE lower(username) = lower(?)
        """,
        (clean_username,),
    ).fetchone()

    if row is None:
        return None

    return user_from_row(row)


def get_or_create_user(
    conn: sqlite3.Connection,
    username: str,
    *,
    display_name: str | None = None,
    password_hash: str | None = None,
    is_admin: bool = False,
    is_active: bool = True,
    approval_status: str | None = None,
    signup_note: str | None = None,
) -> int:
    """Return a user id, creating the user if needed."""
    clean_username = normalize_username(username)
    if not clean_username:
        raise ValueError("Username is required.")

    existing = get_user_by_username(conn, clean_username)
    if existing is not None:
        return int(existing["id"])

    now = utc_now()
    clean_display_name = _clean_text(display_name) or clean_username
    clean_approval_status = validate_approval_status(
        approval_status or (APPROVAL_APPROVED if is_active else APPROVAL_DISABLED)
    )
    resolved_is_active = active_for_approval_status(clean_approval_status)

    cursor = conn.execute(
        """
        INSERT INTO users (
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_username,
            clean_display_name,
            password_hash,
            1 if is_admin else 0,
            1 if resolved_is_active else 0,
            clean_approval_status,
            _clean_text(signup_note),
            None,
            None,
            now,
            now,
        ),
    )

    user_id = cursor.lastrowid
    if user_id is None:
        raise RuntimeError("Could not create user.")

    return int(user_id)


def create_pending_user(
    conn: sqlite3.Connection,
    username: str,
    *,
    password_hash: str,
    display_name: str | None = None,
    signup_note: str | None = None,
) -> int:
    """Create an inactive user pending administrator approval."""
    return get_or_create_user(
        conn,
        username,
        display_name=display_name,
        password_hash=password_hash,
        is_admin=False,
        is_active=False,
        approval_status=APPROVAL_PENDING,
        signup_note=signup_note,
    )


def set_user_approval_status(
    conn: sqlite3.Connection,
    user_id: int,
    status: str,
    *,
    reviewed_by_user_id: int | None = None,
) -> None:
    """Update a user's approval status and effective active flag."""
    clean_status = validate_approval_status(status)
    conn.execute(
        """
        UPDATE users
        SET
            approval_status = ?,
            is_active = ?,
            reviewed_at = ?,
            reviewed_by_user_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            clean_status,
            1 if active_for_approval_status(clean_status) else 0,
            utc_now(),
            reviewed_by_user_id,
            utc_now(),
            user_id,
        ),
    )


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all known users."""
    rows = conn.execute(
        """
        SELECT
            id,
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        FROM users
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()

    return [user_from_row(row) for row in rows]


def delete_user(conn: sqlite3.Connection, user_id: int) -> bool:
    """Delete a user and all owned web data.

    Foreign keys cascade profiles, sessions, favorites, playlists, playlist stations,
    history entries and password-change requests owned by the user. Requests that
    were resolved by this user keep their audit trail with a NULL resolver.
    """
    cursor = conn.execute(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return cursor.rowcount > 0
