# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from fluxtuner.core import db
from fluxtuner.web import auth, password_change_actions, registration_actions
from fluxtuner.web import context as web_context
from fluxtuner.web import guards as web_guards
from fluxtuner.web import setup as web_setup
from fluxtuner.web.payloads import public_user_payload
from fluxtuner.web.security import (
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
    delete_session_cookie,
    session_cookie_max_age,
    set_session_cookie,
)

AUTH_ERROR_DETAIL = "Invalid username or password."
RATE_LIMIT_DETAIL = "Too many login attempts. Try again later."
AUTH_REQUIRED_DETAIL = "Authentication required."
ACCOUNT_PENDING_DETAIL = "Account pending approval."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
MAX_USERNAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 120
MAX_SIGNUP_NOTE_LENGTH = 1000
MAX_ACCOUNT_CHANGE_NOTE_LENGTH = 1000
ACCOUNT_CHANGE_PENDING_DETAIL = password_change_actions.ACCOUNT_CHANGE_PENDING_DETAIL
REGISTER_RECEIVED_MESSAGE = registration_actions.REGISTER_RECEIVED_MESSAGE
REGISTER_USER_EXISTS_DETAIL = registration_actions.REGISTER_USER_EXISTS_DETAIL
REGISTER_INVALID_DETAIL = registration_actions.REGISTER_INVALID_DETAIL
REGISTER_RATE_LIMIT_USERNAME = registration_actions.REGISTER_RATE_LIMIT_USERNAME
ACCOUNT_CHANGE_RATE_LIMIT_KEY = password_change_actions.ACCOUNT_CHANGE_RATE_LIMIT_KEY
ACCOUNT_CHANGE_INVALID_DETAIL = password_change_actions.ACCOUNT_CHANGE_INVALID_DETAIL
ACCOUNT_CHANGE_RECEIVED_MESSAGE = password_change_actions.ACCOUNT_CHANGE_RECEIVED_MESSAGE

router = APIRouter()
required_body = Body(...)


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


@router.post("/api/auth/password-change-requests")
def request_password_change(
    request: Request,
    payload: dict[str, Any] = required_body,
) -> dict[str, str]:
    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return password_change_actions.request_password_change_payload(
            conn,
            payload,
            client_key=web_setup.request_client_host(request),
            max_username_length=MAX_USERNAME_LENGTH,
            max_note_length=MAX_ACCOUNT_CHANGE_NOTE_LENGTH,
            field_too_long_detail=FIELD_TOO_LONG_DETAIL,
            rate_limit_detail=RATE_LIMIT_DETAIL,
        )


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

        if db.user_has_pending_password_change_request(conn, int(user["id"])):
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=False,
            )
            conn.commit()
            raise HTTPException(status_code=403, detail=ACCOUNT_CHANGE_PENDING_DETAIL)

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
        token = auth.create_session(
            conn,
            int(authenticated_user["id"]),
            max_age_seconds=session_cookie_max_age(),
        )
        auth.record_login_attempt(
            conn,
            username,
            client_key,
            success=True,
        )
        conn.commit()

    set_session_cookie(response, token)
    return {
        "authenticated": True,
        "user": public_user_payload(authenticated_user),
        "csrf_token": csrf_token_for_session_token(token),
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
    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        user = auth.get_session_user(conn, token)

    if user is None:
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

    return {
        "authenticated": True,
        "user": public_user_payload(user),
        "csrf_token": csrf_token_for_session_token(token),
    }
