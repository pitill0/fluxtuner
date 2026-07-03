# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth, password_changes
from fluxtuner.web.admin_users import admin_target_user, revoke_user_sessions
from fluxtuner.web.payloads import (
    admin_password_change_request_payload,
    admin_user_payload,
)
from fluxtuner.web.validation import text_too_long

ACCOUNT_CHANGE_RATE_LIMIT_KEY = password_changes.ACCOUNT_CHANGE_RATE_LIMIT_KEY
ACCOUNT_CHANGE_INVALID_DETAIL = password_changes.ACCOUNT_CHANGE_INVALID_DETAIL
ACCOUNT_CHANGE_RECEIVED_MESSAGE = password_changes.ACCOUNT_CHANGE_RECEIVED_MESSAGE
ACCOUNT_CHANGE_NOT_FOUND_DETAIL = password_changes.ACCOUNT_CHANGE_NOT_FOUND_DETAIL
ACCOUNT_CHANGE_NOT_PENDING_DETAIL = password_changes.ACCOUNT_CHANGE_NOT_PENDING_DETAIL
ACCOUNT_CHANGE_PENDING_DETAIL = password_changes.ACCOUNT_CHANGE_PENDING_DETAIL
ACCOUNT_CHANGE_EXPIRED_DETAIL = password_changes.ACCOUNT_CHANGE_EXPIRED_DETAIL


def request_password_change_payload(
    conn: Any,
    payload: dict[str, Any],
    *,
    client_key: str,
    max_username_length: int,
    max_note_length: int,
    field_too_long_detail: str,
    rate_limit_detail: str,
) -> dict[str, str]:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("new_password") or payload.get("password") or "")
    note = str(payload.get("note") or "").strip() or None

    if not username or not password:
        raise HTTPException(status_code=400, detail=ACCOUNT_CHANGE_INVALID_DETAIL)
    if len(username) > max_username_length or text_too_long(note, max_note_length):
        raise HTTPException(status_code=400, detail=field_too_long_detail)

    clean_username = db.normalize_username(username)
    if not clean_username:
        raise HTTPException(status_code=400, detail=ACCOUNT_CHANGE_INVALID_DETAIL)

    if auth.is_login_rate_limited(conn, ACCOUNT_CHANGE_RATE_LIMIT_KEY, client_key):
        raise HTTPException(status_code=429, detail=rate_limit_detail)

    try:
        password_hash = auth.hash_password(password)
    except auth.PasswordValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = db.get_user_by_username(conn, clean_username)
    if (
        user is not None
        and bool(user["is_active"])
        and str(user["approval_status"]) == db.APPROVAL_APPROVED
        and not bool(user["is_admin"])
    ):
        user_id = int(user["id"])
        db.upsert_pending_password_change_request(
            conn,
            user_id,
            password_hash=password_hash,
            note=note,
            expires_at=password_changes.password_change_expires_at(),
        )
        revoke_user_sessions(conn, user_id)

    auth.record_login_attempt(
        conn,
        ACCOUNT_CHANGE_RATE_LIMIT_KEY,
        client_key,
        success=False,
    )
    conn.commit()

    return {"message": ACCOUNT_CHANGE_RECEIVED_MESSAGE}


def list_password_change_requests_payload(conn: Any) -> dict[str, Any]:
    requests = db.list_password_change_requests(conn)
    return {
        "count": len(requests),
        "requests": [
            admin_password_change_request_payload(request_payload) for request_payload in requests
        ],
    }


def _pending_password_change_request(conn: Any, request_id: int) -> dict[str, Any]:
    request_payload = db.get_password_change_request(conn, request_id)
    if request_payload is None:
        raise HTTPException(status_code=404, detail=ACCOUNT_CHANGE_NOT_FOUND_DETAIL)
    if str(request_payload["status"]) != db.ACCOUNT_CHANGE_PENDING:
        raise HTTPException(status_code=409, detail=ACCOUNT_CHANGE_NOT_PENDING_DETAIL)
    return request_payload


def approve_password_change_request_payload(
    conn: Any,
    request_id: int,
    *,
    resolved_by_user_id: int,
) -> dict[str, Any]:
    request_payload = _pending_password_change_request(conn, request_id)
    if password_changes.password_change_is_expired(request_payload):
        db.set_password_change_request_status(
            conn,
            request_id,
            db.ACCOUNT_CHANGE_EXPIRED,
            resolved_by_user_id=resolved_by_user_id,
        )
        conn.commit()
        raise HTTPException(status_code=409, detail=ACCOUNT_CHANGE_EXPIRED_DETAIL)

    user_id = int(request_payload["user_id"])
    conn.execute(
        """
        UPDATE users
        SET
            password_hash = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (str(request_payload["password_hash"]), db.utc_now(), user_id),
    )
    db.set_password_change_request_status(
        conn,
        request_id,
        db.ACCOUNT_CHANGE_APPROVED,
        resolved_by_user_id=resolved_by_user_id,
    )
    revoke_user_sessions(conn, user_id)
    conn.commit()

    updated_user = admin_target_user(conn, str(request_payload["username"]))
    return {"user": admin_user_payload(updated_user)}


def reject_password_change_request_payload(
    conn: Any,
    request_id: int,
    *,
    resolved_by_user_id: int,
) -> dict[str, str]:
    _pending_password_change_request(conn, request_id)
    db.set_password_change_request_status(
        conn,
        request_id,
        db.ACCOUNT_CHANGE_REJECTED,
        resolved_by_user_id=resolved_by_user_id,
    )
    conn.commit()

    return {"status": db.ACCOUNT_CHANGE_REJECTED}
