# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.admin_users import (
    ADMIN_USER_NOT_FOUND_DETAIL,
    admin_target_user,
    ensure_not_last_active_admin,
    revoke_user_sessions,
)
from fluxtuner.web.payloads import admin_user_payload
from fluxtuner.web.validation import text_too_long

ADMIN_USER_EXISTS_DETAIL = "Web user already exists."
ADMIN_SELF_DELETE_DETAIL = "Administrators cannot delete their own account."
ADMIN_INVALID_USER_DETAIL = "Username and password are required."
ADMIN_MISSING_VALUE_DETAIL = "Missing required value."


def list_users_payload(conn: Any) -> dict[str, Any]:
    users = db.list_users(conn)
    return {
        "count": len(users),
        "users": [admin_user_payload(user) for user in users],
    }


def create_user_payload(
    conn: Any,
    payload: dict[str, Any],
    *,
    max_username_length: int,
    max_display_name_length: int,
    field_too_long_detail: str,
) -> dict[str, Any]:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or "").strip() or None
    is_admin = bool(payload.get("is_admin", False))
    is_active = bool(payload.get("is_active", True))

    if not username or not password:
        raise HTTPException(status_code=400, detail=ADMIN_INVALID_USER_DETAIL)
    if len(username) > max_username_length or text_too_long(
        display_name,
        max_display_name_length,
    ):
        raise HTTPException(status_code=400, detail=field_too_long_detail)

    try:
        password_hash = auth.hash_password(password)
    except auth.PasswordValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clean_username = db.normalize_username(username)
    if not clean_username:
        raise HTTPException(status_code=400, detail=ADMIN_INVALID_USER_DETAIL)

    if db.get_user_by_username(conn, clean_username) is not None:
        raise HTTPException(status_code=409, detail=ADMIN_USER_EXISTS_DETAIL)

    user_id = db.get_or_create_user(
        conn,
        clean_username,
        display_name=display_name,
        password_hash=password_hash,
        is_admin=is_admin,
        is_active=is_active,
    )
    db.ensure_default_profile(conn, user_id=user_id)
    conn.commit()

    user = admin_target_user(conn, clean_username)
    return {"user": admin_user_payload(user)}


def set_user_password_payload(
    conn: Any,
    username: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    password = str(payload.get("password") or "")
    if not password:
        raise HTTPException(status_code=400, detail=ADMIN_MISSING_VALUE_DETAIL)

    try:
        password_hash = auth.hash_password(password)
    except auth.PasswordValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = admin_target_user(conn, username)
    user_id = int(user["id"])
    conn.execute(
        """
        UPDATE users
        SET
            password_hash = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (password_hash, db.utc_now(), user_id),
    )
    revoke_user_sessions(conn, user_id)
    conn.commit()

    updated_user = admin_target_user(conn, username)
    return {"user": admin_user_payload(updated_user)}


def set_user_approval_payload(
    conn: Any,
    username: str,
    *,
    approval_status: str,
    reviewed_by_user_id: int,
    revoke_sessions: bool,
    protect_last_admin: bool,
) -> dict[str, Any]:
    user = admin_target_user(conn, username)
    if protect_last_admin:
        ensure_not_last_active_admin(conn, user)
    user_id = int(user["id"])

    db.set_user_approval_status(
        conn,
        user_id,
        approval_status,
        reviewed_by_user_id=reviewed_by_user_id,
    )
    if revoke_sessions:
        revoke_user_sessions(conn, user_id)
    conn.commit()

    updated_user = admin_target_user(conn, username)
    return {"user": admin_user_payload(updated_user)}


def delete_user(
    conn: Any,
    username: str,
    *,
    admin_user_id: int,
) -> None:
    user = admin_target_user(conn, username)
    user_id = int(user["id"])

    if user_id == admin_user_id:
        raise HTTPException(status_code=400, detail=ADMIN_SELF_DELETE_DETAIL)

    ensure_not_last_active_admin(conn, user)
    deleted = db.delete_user(conn, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=ADMIN_USER_NOT_FOUND_DETAIL)
    conn.commit()


def set_user_admin_payload(
    conn: Any,
    username: str,
    *,
    is_admin: bool,
    protect_last_admin: bool,
) -> dict[str, Any]:
    user = admin_target_user(conn, username)
    if protect_last_admin:
        ensure_not_last_active_admin(conn, user)
    user_id = int(user["id"])

    conn.execute(
        """
        UPDATE users
        SET
            is_admin = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (1 if is_admin else 0, db.utc_now(), user_id),
    )
    conn.commit()

    updated_user = admin_target_user(conn, username)
    return {"user": admin_user_payload(updated_user)}
