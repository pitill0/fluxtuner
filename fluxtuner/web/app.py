# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import argparse
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core import db
from fluxtuner.web import admin_actions, auth, library, password_changes
from fluxtuner.web import context as web_context
from fluxtuner.web import dashboard as web_dashboard
from fluxtuner.web import guards as web_guards
from fluxtuner.web import setup as web_setup
from fluxtuner.web.admin_users import admin_target_user, revoke_user_sessions
from fluxtuner.web.payloads import (
    admin_password_change_request_payload,
    admin_user_payload,
    public_user_payload,
    station_payload,
)
from fluxtuner.web.security import (
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
    delete_session_cookie,
    session_cookie_max_age,
    set_session_cookie,
)
from fluxtuner.web.validation import (
    is_supported_web_url,
    playlist_name,
    playlist_name_too_long,
    station_stream_url,
    text_too_long,
)

AUTH_ERROR_DETAIL = "Invalid username or password."
RATE_LIMIT_DETAIL = "Too many login attempts. Try again later."
AUTH_REQUIRED_DETAIL = "Authentication required."
ACCOUNT_PENDING_DETAIL = "Account pending approval."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."
SETUP_UNAVAILABLE_DETAIL = "First-run setup is not available."
SETUP_VERIFICATION_ERROR_DETAIL = "Setup verification failed."
SETUP_LOCAL_ONLY_DETAIL = "First-run setup requires local access or FLUXTUNER_WEB_SETUP_TOKEN."
SETUP_INVALID_DETAIL = "Username and password are required."
SETUP_RATE_LIMIT_USERNAME = "__setup__"
REGISTER_RATE_LIMIT_USERNAME = "__register__"
ADMIN_REQUIRED_DETAIL = "Administrator access required."
REGISTER_INVALID_DETAIL = "Username and password are required."
REGISTER_USER_EXISTS_DETAIL = "Username is unavailable."
REGISTER_RECEIVED_MESSAGE = "Account request received. Try signing in later after approval."
INVALID_STATION_URL_DETAIL = "Station URL must be a valid HTTP or HTTPS URL."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
PLAYLIST_REQUIRED_DETAIL = "Playlist name is required."
MAX_USERNAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 120
MAX_SIGNUP_NOTE_LENGTH = 1000
MAX_ACCOUNT_CHANGE_NOTE_LENGTH = 1000
MAX_PLAYLIST_NAME_LENGTH = 120
ACCOUNT_CHANGE_RATE_LIMIT_KEY = password_changes.ACCOUNT_CHANGE_RATE_LIMIT_KEY
ACCOUNT_CHANGE_INVALID_DETAIL = password_changes.ACCOUNT_CHANGE_INVALID_DETAIL
ACCOUNT_CHANGE_RECEIVED_MESSAGE = password_changes.ACCOUNT_CHANGE_RECEIVED_MESSAGE
ACCOUNT_CHANGE_NOT_FOUND_DETAIL = password_changes.ACCOUNT_CHANGE_NOT_FOUND_DETAIL
ACCOUNT_CHANGE_NOT_PENDING_DETAIL = password_changes.ACCOUNT_CHANGE_NOT_PENDING_DETAIL
ACCOUNT_CHANGE_PENDING_DETAIL = password_changes.ACCOUNT_CHANGE_PENDING_DETAIL
ACCOUNT_CHANGE_EXPIRED_DETAIL = password_changes.ACCOUNT_CHANGE_EXPIRED_DETAIL


def _missing_web_dependency_message() -> str:
    return (
        'FluxTuner Web dependencies are not installed. Install them with: pip install -e ".[web]"'
    )


def _read_template(name: str) -> str:
    template_path = resources.files("fluxtuner.web").joinpath("templates").joinpath(name)
    return template_path.read_text(encoding="utf-8")


def _require_station_stream_url(station_data: dict[str, Any]) -> None:
    if not is_supported_web_url(station_stream_url(station_data)):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=INVALID_STATION_URL_DETAIL)


def create_app() -> Any:
    """Create the experimental FluxTuner Web application."""
    try:
        from fastapi import Body, FastAPI, HTTPException, Path, Query, Request, Response
        from fastapi.responses import FileResponse, HTMLResponse
        from fastapi.staticfiles import StaticFiles

        globals()["Request"] = Request
        globals()["Response"] = Response
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    required_body = Body(...)

    def require_csrf(request: Request) -> None:
        web_guards.require_csrf(
            request,
            csrf_error_detail=CSRF_ERROR_DETAIL,
        )

    def require_admin_user(request: Request) -> dict[str, Any]:
        return web_guards.require_admin_user(
            request,
            auth_required_detail=AUTH_REQUIRED_DETAIL,
            admin_required_detail=ADMIN_REQUIRED_DETAIL,
        )

    app = FastAPI(
        title=f"{__app_name__} Web",
        version=__version__,
        description="FluxTuner web/server interface.",
    )

    static_dir = resources.files("fluxtuner.web").joinpath("static")
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    @app.api_route("/apple-touch-icon.png", methods=["GET", "HEAD"], include_in_schema=False)
    def apple_touch_icon() -> FileResponse:
        return FileResponse(str(static_dir.joinpath("icons").joinpath("apple-touch-icon.png")))

    @app.api_route(
        "/apple-touch-icon-precomposed.png",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    def apple_touch_icon_precomposed() -> FileResponse:
        return FileResponse(str(static_dir.joinpath("icons").joinpath("apple-touch-icon.png")))

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _read_template("index.html").replace("__FLUXTUNER_VERSION__", __version__)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return web_dashboard.server_health_payload()

    @app.get("/api/public/stats")
    def public_stats() -> dict[str, Any]:
        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return db.public_activity_stats(conn)

    @app.get("/api/setup/status")
    def setup_status(request: Request) -> dict[str, Any]:
        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            admin_exists = web_setup.configured_admin_exists(conn)

        return {
            "available": not admin_exists,
            "configured_admin_exists": admin_exists,
            "requires_setup_token": web_setup.setup_token_required(),
            "local_request": web_setup.setup_request_is_local(request),
        }

    @app.post("/api/setup/create-admin")
    def setup_create_admin(
        request: Request,
        response: Response,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, Any]:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        setup_token = str(payload.get("setup_token") or "")
        client_key = web_setup.request_client_host(request)

        if not username or not password:
            raise HTTPException(status_code=400, detail=SETUP_INVALID_DETAIL)
        if len(username) > MAX_USERNAME_LENGTH:
            raise HTTPException(status_code=400, detail=FIELD_TOO_LONG_DETAIL)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)

            if auth.is_login_rate_limited(conn, SETUP_RATE_LIMIT_USERNAME, client_key):
                raise HTTPException(status_code=429, detail=RATE_LIMIT_DETAIL)

            if web_setup.configured_admin_exists(conn):
                raise HTTPException(status_code=403, detail=SETUP_UNAVAILABLE_DETAIL)

            if web_setup.setup_token_required() and not web_setup.valid_setup_token(setup_token):
                auth.record_login_attempt(
                    conn,
                    SETUP_RATE_LIMIT_USERNAME,
                    client_key,
                    success=False,
                )
                conn.commit()
                raise HTTPException(status_code=403, detail=SETUP_VERIFICATION_ERROR_DETAIL)

        if not web_setup.setup_token_required() and not web_setup.setup_request_is_local(request):
            raise HTTPException(status_code=403, detail=SETUP_LOCAL_ONLY_DETAIL)

        try:
            password_hash = auth.hash_password(password)
        except auth.PasswordValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)

            if web_setup.configured_admin_exists(conn):
                raise HTTPException(status_code=403, detail=SETUP_UNAVAILABLE_DETAIL)

            clean_username = db.normalize_username(username)
            if not clean_username:
                raise HTTPException(status_code=400, detail=SETUP_INVALID_DETAIL)

            existing_user = db.get_user_by_username(conn, clean_username)
            if existing_user is None:
                user_id = db.get_or_create_user(
                    conn,
                    clean_username,
                    password_hash=password_hash,
                    is_admin=True,
                    is_active=True,
                )
            else:
                user_id = int(existing_user["id"])
                conn.execute(
                    """
                    UPDATE users
                    SET
                        password_hash = ?,
                        is_admin = 1,
                        is_active = 1,
                        approval_status = ?,
                        reviewed_at = ?,
                        reviewed_by_user_id = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (password_hash, db.APPROVAL_APPROVED, db.utc_now(), db.utc_now(), user_id),
                )

            db.ensure_default_profile(conn, user_id=user_id)
            token = auth.create_session(conn, user_id)
            auth.record_login_attempt(
                conn,
                SETUP_RATE_LIMIT_USERNAME,
                client_key,
                success=True,
            )
            conn.commit()

            user = auth.get_session_user(conn, token)

        if user is None:
            raise HTTPException(status_code=500, detail="Could not create setup session.")

        set_session_cookie(response, token)

        return {
            "authenticated": True,
            "setup_complete": True,
            "user": public_user_payload(user),
            "csrf_token": csrf_token_for_session_token(token),
        }

    @app.post("/api/auth/register")
    def register(
        request: Request,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, str]:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        display_name = str(payload.get("display_name") or "").strip() or None
        signup_note = str(payload.get("note") or payload.get("signup_note") or "").strip() or None
        client_key = web_setup.request_client_host(request)

        if not username or not password:
            raise HTTPException(status_code=400, detail=REGISTER_INVALID_DETAIL)
        if (
            len(username) > MAX_USERNAME_LENGTH
            or text_too_long(display_name, MAX_DISPLAY_NAME_LENGTH)
            or text_too_long(signup_note, MAX_SIGNUP_NOTE_LENGTH)
        ):
            raise HTTPException(status_code=400, detail=FIELD_TOO_LONG_DETAIL)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            clean_username = db.normalize_username(username)
            if not clean_username:
                raise HTTPException(status_code=400, detail=REGISTER_INVALID_DETAIL)

            if auth.is_login_rate_limited(conn, REGISTER_RATE_LIMIT_USERNAME, client_key):
                raise HTTPException(status_code=429, detail=RATE_LIMIT_DETAIL)

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

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
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

    @app.post("/api/auth/password-change-requests")
    def request_password_change(
        request: Request,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, str]:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("new_password") or payload.get("password") or "")
        note = str(payload.get("note") or "").strip() or None
        client_key = web_setup.request_client_host(request)

        if not username or not password:
            raise HTTPException(status_code=400, detail=ACCOUNT_CHANGE_INVALID_DETAIL)
        if len(username) > MAX_USERNAME_LENGTH or text_too_long(
            note,
            MAX_ACCOUNT_CHANGE_NOTE_LENGTH,
        ):
            raise HTTPException(status_code=400, detail=FIELD_TOO_LONG_DETAIL)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            clean_username = db.normalize_username(username)
            if not clean_username:
                raise HTTPException(status_code=400, detail=ACCOUNT_CHANGE_INVALID_DETAIL)

            if auth.is_login_rate_limited(
                conn,
                ACCOUNT_CHANGE_RATE_LIMIT_KEY,
                client_key,
            ):
                raise HTTPException(status_code=429, detail=RATE_LIMIT_DETAIL)

        try:
            password_hash = auth.hash_password(password)
        except auth.PasswordValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
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

    @app.post("/api/auth/login")
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

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        require_csrf(request)
        token = request.cookies.get(SESSION_COOKIE_NAME)
        with db.connect() as conn:
            revoked = auth.revoke_session(conn, token)
            conn.commit()

        delete_session_cookie(response)
        return {"status": "ok", "revoked": revoked}

    @app.get("/api/auth/me")
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

    @app.get("/api/dashboard")
    def dashboard(
        request: Request,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        profile_name = web_context.effective_profile_name(profile)
        payload: dict[str, Any] = {
            "user": web_dashboard.dashboard_user_payload(int(user["id"]), profile_name),
            "admin": None,
        }

        if bool(user["is_admin"]):
            with db.connect() as conn:
                web_context.ensure_web_schema(conn)
                payload["admin"] = {
                    **web_dashboard.admin_user_counts(conn),
                    "server": web_dashboard.server_health_payload(),
                }

        return payload

    @app.get("/api/admin/password-change-requests")
    def admin_list_password_change_requests(request: Request) -> dict[str, Any]:
        require_admin_user(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            requests = db.list_password_change_requests(conn)

        return {
            "count": len(requests),
            "requests": [
                admin_password_change_request_payload(request_payload)
                for request_payload in requests
            ],
        }

    @app.post("/api/admin/password-change-requests/{request_id}/approve")
    def admin_approve_password_change_request(
        request: Request,
        request_id: int = Path(..., ge=1),
    ) -> dict[str, Any]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            request_payload = db.get_password_change_request(conn, request_id)
            if request_payload is None:
                raise HTTPException(status_code=404, detail=ACCOUNT_CHANGE_NOT_FOUND_DETAIL)
            if str(request_payload["status"]) != db.ACCOUNT_CHANGE_PENDING:
                raise HTTPException(status_code=409, detail=ACCOUNT_CHANGE_NOT_PENDING_DETAIL)
            if password_changes.password_change_is_expired(request_payload):
                db.set_password_change_request_status(
                    conn,
                    request_id,
                    db.ACCOUNT_CHANGE_EXPIRED,
                    resolved_by_user_id=int(admin_user["id"]),
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
                resolved_by_user_id=int(admin_user["id"]),
            )
            revoke_user_sessions(conn, user_id)
            conn.commit()

            updated_user = admin_target_user(conn, str(request_payload["username"]))

        return {"user": admin_user_payload(updated_user)}

    @app.post("/api/admin/password-change-requests/{request_id}/reject")
    def admin_reject_password_change_request(
        request: Request,
        request_id: int = Path(..., ge=1),
    ) -> dict[str, str]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            request_payload = db.get_password_change_request(conn, request_id)
            if request_payload is None:
                raise HTTPException(status_code=404, detail=ACCOUNT_CHANGE_NOT_FOUND_DETAIL)
            if str(request_payload["status"]) != db.ACCOUNT_CHANGE_PENDING:
                raise HTTPException(status_code=409, detail=ACCOUNT_CHANGE_NOT_PENDING_DETAIL)

            db.set_password_change_request_status(
                conn,
                request_id,
                db.ACCOUNT_CHANGE_REJECTED,
                resolved_by_user_id=int(admin_user["id"]),
            )
            conn.commit()

        return {"status": db.ACCOUNT_CHANGE_REJECTED}

    @app.get("/api/admin/users")
    def admin_list_users(request: Request) -> dict[str, Any]:
        require_admin_user(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.list_users_payload(conn)

    @app.post("/api/admin/users")
    def admin_create_user(
        request: Request,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, Any]:
        require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.create_user_payload(
                conn,
                payload,
                max_username_length=MAX_USERNAME_LENGTH,
                max_display_name_length=MAX_DISPLAY_NAME_LENGTH,
                field_too_long_detail=FIELD_TOO_LONG_DETAIL,
            )

    @app.post("/api/admin/users/{username}/password")
    def admin_set_user_password(
        username: str,
        request: Request,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, Any]:
        require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_password_payload(conn, username, payload)

    @app.post("/api/admin/users/{username}/deactivate")
    def admin_deactivate_user(username: str, request: Request) -> dict[str, Any]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_approval_payload(
                conn,
                username,
                approval_status=db.APPROVAL_DISABLED,
                reviewed_by_user_id=int(admin_user["id"]),
                revoke_sessions=True,
                protect_last_admin=True,
            )

    @app.post("/api/admin/users/{username}/activate")
    def admin_activate_user(username: str, request: Request) -> dict[str, Any]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_approval_payload(
                conn,
                username,
                approval_status=db.APPROVAL_APPROVED,
                reviewed_by_user_id=int(admin_user["id"]),
                revoke_sessions=False,
                protect_last_admin=False,
            )

    @app.delete("/api/admin/users/{username}")
    def admin_delete_user(username: str, request: Request) -> Response:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            admin_actions.delete_user(conn, username, admin_user_id=int(admin_user["id"]))

        return Response(status_code=204)

    @app.post("/api/admin/users/{username}/approve")
    def admin_approve_user(username: str, request: Request) -> dict[str, Any]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_approval_payload(
                conn,
                username,
                approval_status=db.APPROVAL_APPROVED,
                reviewed_by_user_id=int(admin_user["id"]),
                revoke_sessions=False,
                protect_last_admin=False,
            )

    @app.post("/api/admin/users/{username}/reject")
    def admin_reject_user(username: str, request: Request) -> dict[str, Any]:
        admin_user = require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_approval_payload(
                conn,
                username,
                approval_status=db.APPROVAL_REJECTED,
                reviewed_by_user_id=int(admin_user["id"]),
                revoke_sessions=True,
                protect_last_admin=True,
            )

    @app.post("/api/admin/users/{username}/admin")
    def admin_grant_admin(username: str, request: Request) -> dict[str, Any]:
        require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_admin_payload(
                conn,
                username,
                is_admin=True,
                protect_last_admin=False,
            )

    @app.delete("/api/admin/users/{username}/admin")
    def admin_revoke_admin(username: str, request: Request) -> dict[str, Any]:
        require_admin_user(request)
        require_csrf(request)

        with db.connect() as conn:
            web_context.ensure_web_schema(conn)
            return admin_actions.set_user_admin_payload(
                conn,
                username,
                is_admin=False,
                protect_last_admin=True,
            )

    @app.get("/api/search")
    def search(
        request: Request,
        q: str = Query(default="", max_length=120),
        country: str = Query(default="", max_length=80),
        min_bitrate: int = Query(default=0, ge=0, le=1000),
        limit: int = Query(default=25, ge=1, le=50),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return library.search_payload(
            query=q,
            country=country,
            min_bitrate=min_bitrate,
            limit=limit,
        )

    @app.get("/api/history")
    def history(
        request: Request,
        limit: int = Query(default=25, ge=1, le=100),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return library.history_payload(
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
            limit=limit,
        )

    @app.post("/api/history")
    def record_history(
        request: Request,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = station_payload(station)

        _require_station_stream_url(station_data)

        return library.record_history_payload(
            station_data,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.get("/api/favorites")
    def favorites(
        request: Request,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return library.favorites_payload(
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.post("/api/favorites")
    def create_favorite(
        request: Request,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = station_payload(station)

        _require_station_stream_url(station_data)

        return library.create_favorite_payload(
            station_data,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.delete("/api/favorites")
    def delete_favorite(
        request: Request,
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        return library.delete_favorite_payload(
            url,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.get("/api/playlists")
    def playlists(
        request: Request,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return library.playlists_payload(
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.post("/api/playlists")
    def create_web_playlist(
        request: Request,
        payload: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        name = playlist_name(payload)
        if not name:
            raise HTTPException(status_code=400, detail=PLAYLIST_REQUIRED_DETAIL)
        if playlist_name_too_long(name):
            raise HTTPException(status_code=400, detail=FIELD_TOO_LONG_DETAIL)

        return library.create_playlist_payload(
            name,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.delete("/api/playlists/{name}")
    def delete_web_playlist(
        request: Request,
        name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        return library.delete_playlist_payload(
            name,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.get("/api/playlists/{name}/stations")
    def playlist_stations(
        request: Request,
        name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return library.playlist_stations_payload(
            name,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.post("/api/playlists/{name}/stations")
    def add_web_station_to_playlist(
        request: Request,
        name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = station_payload(station)

        _require_station_stream_url(station_data)

        return library.add_station_to_playlist_payload(
            name,
            station_data,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    @app.delete("/api/playlists/{name}/stations")
    def remove_web_station_from_playlist(
        request: Request,
        name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = web_context.authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        return library.remove_station_from_playlist_payload(
            name,
            url,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FluxTuner Web")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on. Defaults to 8080.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload for development.",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    uvicorn.run(
        "fluxtuner.web.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
