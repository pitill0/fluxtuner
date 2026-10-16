# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from fluxtuner.core import db, recovery_codes
from fluxtuner.web import auth, registration_actions
from fluxtuner.web import context as web_context
from fluxtuner.web import guards as web_guards
from fluxtuner.web import setup as web_setup
from fluxtuner.web.payloads import public_user_payload
from fluxtuner.web.security import (
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
    delete_session_cookie,
    session_initial_max_age,
    set_session_cookie,
)

AUTH_ERROR_DETAIL = "Invalid username or password."
RATE_LIMIT_DETAIL = "Too many login attempts. Try again later."
AUTH_REQUIRED_DETAIL = "Authentication required."
RECOVERY_ERROR_DETAIL = "Invalid recovery credentials."
RECOVERY_RATE_LIMIT_DETAIL = "Too many recovery attempts. Try again later."
ACCOUNT_PENDING_DETAIL = "Account pending approval."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
MAX_USERNAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 120
MAX_SIGNUP_NOTE_LENGTH = 1000
REGISTER_RECEIVED_MESSAGE = registration_actions.REGISTER_RECEIVED_MESSAGE
REGISTER_USER_EXISTS_DETAIL = registration_actions.REGISTER_USER_EXISTS_DETAIL
REGISTER_INVALID_DETAIL = registration_actions.REGISTER_INVALID_DETAIL
REGISTER_RATE_LIMIT_USERNAME = registration_actions.REGISTER_RATE_LIMIT_USERNAME

router = APIRouter()
required_body = Body(...)
optional_body = Body(default=None)


def require_csrf(request: Request) -> None:
    web_guards.require_csrf(
        request,
        csrf_error_detail=CSRF_ERROR_DETAIL,
    )


@router.post("/api/auth/register")
def register(
    request: Request,
    payload: dict[str, Any] = required_body,
) -> dict[str, str]:
    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return registration_actions.register_payload(
            conn,
            payload,
            client_key=web_setup.request_client_host(request),
            max_username_length=MAX_USERNAME_LENGTH,
            max_display_name_length=MAX_DISPLAY_NAME_LENGTH,
            max_signup_note_length=MAX_SIGNUP_NOTE_LENGTH,
            field_too_long_detail=FIELD_TOO_LONG_DETAIL,
            rate_limit_detail=RATE_LIMIT_DETAIL,
        )


@router.post("/api/auth/recover-password")
def recover_password(
    request: Request,
    payload: dict[str, Any] = required_body,
) -> dict[str, Any]:
    username = str(payload.get("username") or "").strip()
    recovery_code = str(payload.get("recovery_code") or "").strip()
    new_password = str(payload.get("new_password") or "")
    client_key = web_setup.request_client_host(request)

    if not username or not recovery_code or not new_password:
        raise HTTPException(status_code=401, detail=RECOVERY_ERROR_DETAIL)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        recovery_codes.purge_old_recovery_attempts(conn)
        if recovery_codes.is_recovery_rate_limited(
            conn,
            username,
            client_key,
        ):
            conn.commit()
            raise HTTPException(
                status_code=429,
                detail=RECOVERY_RATE_LIMIT_DETAIL,
            )

        if (
            recovery_codes.recovery_code_user_id(
                conn,
                username,
                recovery_code,
            )
            is None
        ):
            recovery_codes.record_recovery_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=401, detail=RECOVERY_ERROR_DETAIL)

        conn.commit()

    try:
        password_hash = auth.hash_password(new_password)
    except auth.PasswordValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)

        # Schema setup may perform compatibility writes. Start the recovery
        # transaction from a known clean boundary, then acquire the SQLite
        # write reservation before checking or consuming the recovery code.
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")

        recovery_codes.purge_old_recovery_attempts(conn)

        if recovery_codes.is_recovery_rate_limited(
            conn,
            username,
            client_key,
        ):
            conn.rollback()
            raise HTTPException(
                status_code=429,
                detail=RECOVERY_RATE_LIMIT_DETAIL,
            )

        user_id = recovery_codes.consume_recovery_code(
            conn,
            username,
            recovery_code,
        )
        if user_id is None:
            recovery_codes.record_recovery_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=401, detail=RECOVERY_ERROR_DETAIL)

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

        conn.execute(
            """
            UPDATE web_sessions
            SET revoked_at = ?
            WHERE user_id = ?
              AND revoked_at IS NULL
            """,
            (db.utc_now(), user_id),
        )

        new_recovery_codes = recovery_codes.rotate_recovery_codes(
            conn,
            user_id,
        )

        recovery_codes.record_recovery_attempt(
            conn,
            username,
            client_key,
            success=True,
        )

        conn.commit()

    return {
        "status": "ok",
        "recovery_codes": new_recovery_codes,
    }


@router.post("/api/auth/login")
def login(
    request: Request,
    response: Response,
    payload: dict[str, Any] = required_body,
) -> dict[str, Any]:
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    client_key = web_setup.request_client_host(request)

    if not username or not password:
        raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        if auth.is_login_rate_limited(conn, username, client_key):
            raise HTTPException(status_code=429, detail=RATE_LIMIT_DETAIL)

        user = db.get_user_by_username(conn, username)
        password_hash = str(user["password_hash"] or "") if user is not None else ""

        if not password_hash:
            auth.verify_password(password, auth.DUMMY_PASSWORD_HASH)
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        if not auth.verify_password(password, password_hash):
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        approval_status = str(user["approval_status"])
        if approval_status == db.APPROVAL_PENDING:
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=403, detail=ACCOUNT_PENDING_DETAIL)

        if approval_status != db.APPROVAL_APPROVED or not bool(user["is_active"]):
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        authenticated_user = user
        new_recovery_codes = recovery_codes.bootstrap_recovery_codes(
            conn,
            int(authenticated_user["id"]),
        )
        initial_max_age = session_initial_max_age()
        token = auth.create_session(
            conn,
            int(authenticated_user["id"]),
            max_age_seconds=initial_max_age,
        )
        auth.record_login_attempt(
            conn,
            username,
            client_key,
            success=True,
        )
        conn.commit()

    set_session_cookie(response, token, max_age=initial_max_age)
    result: dict[str, Any] = {
        "authenticated": True,
        "user": public_user_payload(authenticated_user),
        "csrf_token": csrf_token_for_session_token(token),
    }
    if new_recovery_codes is not None:
        result["recovery_codes"] = new_recovery_codes
    return result


@router.post("/api/auth/recovery-codes/regenerate")
def regenerate_recovery_codes(
    request: Request,
    payload: dict[str, Any] | None = optional_body,
) -> dict[str, Any]:
    user = web_context.authenticated_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

    require_csrf(request)

    current_password = str((payload or {}).get("current_password") or "")
    if not current_password:
        raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

    user_id = int(user["id"])

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)

        # Keep reauthentication and recovery-code rotation in the same
        # serialized credential-management transaction.
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")

        current_user = conn.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = ?
              AND is_active = 1
              AND approval_status = ?
            """,
            (user_id, db.APPROVAL_APPROVED),
        ).fetchone()

        password_hash = str(current_user["password_hash"] or "") if current_user is not None else ""

        if not password_hash or not auth.verify_password(
            current_password,
            password_hash,
        ):
            conn.rollback()
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        codes = recovery_codes.rotate_recovery_codes(
            conn,
            user_id,
        )
        conn.commit()

    return {
        "status": "ok",
        "recovery_codes": codes,
    }


@router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, Any]:
    require_csrf(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    with db.connect() as conn:
        revoked = auth.revoke_session(conn, token)
        conn.commit()

    delete_session_cookie(response)
    return {"status": "ok", "revoked": revoked}


@router.get("/api/auth/me")
def me(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_context.authenticated_user(request)

    if user is None:
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

    return {
        "authenticated": True,
        "user": public_user_payload(user),
        "csrf_token": csrf_token_for_session_token(token),
    }
