# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.validation import text_too_long

REGISTER_RATE_LIMIT_USERNAME = "__register__"
REGISTER_INVALID_DETAIL = "Username and password are required."
REGISTER_USER_EXISTS_DETAIL = "Username is unavailable."
REGISTER_RECEIVED_MESSAGE = "Account request received. Try signing in later after approval."


def register_payload(
    conn: Any,
    payload: dict[str, Any],
    *,
    client_key: str,
    max_username_length: int,
    max_display_name_length: int,
    max_signup_note_length: int,
    field_too_long_detail: str,
    rate_limit_detail: str,
) -> dict[str, str]:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or "").strip() or None
    signup_note = str(payload.get("note") or payload.get("signup_note") or "").strip() or None

    if not username or not password:
        raise HTTPException(status_code=400, detail=REGISTER_INVALID_DETAIL)
    if (
        len(username) > max_username_length
        or text_too_long(display_name, max_display_name_length)
        or text_too_long(signup_note, max_signup_note_length)
    ):
        raise HTTPException(status_code=400, detail=field_too_long_detail)

    clean_username = db.normalize_username(username)
    if not clean_username:
        raise HTTPException(status_code=400, detail=REGISTER_INVALID_DETAIL)

    if auth.is_login_rate_limited(conn, REGISTER_RATE_LIMIT_USERNAME, client_key):
        raise HTTPException(status_code=429, detail=rate_limit_detail)

    if db.get_user_by_username(conn, clean_username) is not None:
        auth.record_login_attempt(
            conn,
            REGISTER_RATE_LIMIT_USERNAME,
            client_key,
            success=False,
        )
        conn.commit()
        raise HTTPException(status_code=409, detail=REGISTER_USER_EXISTS_DETAIL)

    try:
        password_hash = auth.hash_password(password)
    except auth.PasswordValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if db.get_user_by_username(conn, clean_username) is not None:
        auth.record_login_attempt(
            conn,
            REGISTER_RATE_LIMIT_USERNAME,
            client_key,
            success=False,
        )
        conn.commit()
        raise HTTPException(status_code=409, detail=REGISTER_USER_EXISTS_DETAIL)

    user_id = db.create_pending_user(
        conn,
        clean_username,
        password_hash=password_hash,
        display_name=display_name,
        signup_note=signup_note,
    )
    db.ensure_default_profile(conn, user_id=user_id)
    auth.record_login_attempt(
        conn,
        REGISTER_RATE_LIMIT_USERNAME,
        client_key,
        success=False,
    )
    conn.commit()

    return {
        "status": db.APPROVAL_PENDING,
        "message": REGISTER_RECEIVED_MESSAGE,
    }
