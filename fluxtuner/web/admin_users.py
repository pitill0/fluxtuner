# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fluxtuner.core import db

ADMIN_USER_NOT_FOUND_DETAIL = "Web user not found."
ADMIN_LAST_ADMIN_DETAIL = "Cannot remove the last active administrator."


def active_admin_count(conn: Any) -> int:
    """Return the number of active admin users that can still sign in."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE
            is_admin = 1
            AND is_active = 1
            AND password_hash IS NOT NULL
            AND length(trim(password_hash)) > 0
        """
    ).fetchone()
    return int(row[0])


def revoke_user_sessions(conn: Any, user_id: int) -> None:
    """Revoke every currently valid Web session for a user."""
    conn.execute(
        """
        UPDATE web_sessions
        SET revoked_at = ?
        WHERE user_id = ? AND revoked_at IS NULL
        """,
        (db.utc_now(), user_id),
    )


def admin_target_user(conn: Any, username: str) -> dict[str, Any]:
    """Return an admin mutation target user or raise a Web 404."""
    from fastapi import HTTPException

    user = db.get_user_by_username(conn, username)
    if user is None:
        raise HTTPException(status_code=404, detail=ADMIN_USER_NOT_FOUND_DETAIL)

    return user


def ensure_not_last_active_admin(conn: Any, user: dict[str, Any]) -> None:
    """Prevent mutations that would remove the last active administrator."""
    from fastapi import HTTPException

    if not bool(user["is_admin"]) or not bool(user["is_active"]):
        return

    if active_admin_count(conn) <= 1:
        raise HTTPException(status_code=409, detail=ADMIN_LAST_ADMIN_DETAIL)
