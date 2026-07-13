# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import asynccontextmanager
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core import db
from fluxtuner.web import (
    auth,
    password_change_actions,
    registration_actions,
)
from fluxtuner.web import context as web_context
from fluxtuner.web import dashboard as web_dashboard
from fluxtuner.web import guards as web_guards
from fluxtuner.web import setup as web_setup
from fluxtuner.web.metadata import MetadataCoordinator, SystemStreamTargetResolver
from fluxtuner.web.payloads import public_user_payload
from fluxtuner.web.security import (
    csrf_token_for_session_token,
    set_session_cookie,
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
REGISTER_RATE_LIMIT_USERNAME = registration_actions.REGISTER_RATE_LIMIT_USERNAME
ADMIN_REQUIRED_DETAIL = "Administrator access required."
REGISTER_INVALID_DETAIL = registration_actions.REGISTER_INVALID_DETAIL
REGISTER_USER_EXISTS_DETAIL = registration_actions.REGISTER_USER_EXISTS_DETAIL
REGISTER_RECEIVED_MESSAGE = registration_actions.REGISTER_RECEIVED_MESSAGE
INVALID_STATION_URL_DETAIL = "Station URL must be a valid HTTP or HTTPS URL."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
PLAYLIST_REQUIRED_DETAIL = "Playlist name is required."
MAX_USERNAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 120
MAX_SIGNUP_NOTE_LENGTH = 1000
MAX_ACCOUNT_CHANGE_NOTE_LENGTH = 1000
MAX_PLAYLIST_NAME_LENGTH = 120
ACCOUNT_CHANGE_RATE_LIMIT_KEY = password_change_actions.ACCOUNT_CHANGE_RATE_LIMIT_KEY
ACCOUNT_CHANGE_INVALID_DETAIL = password_change_actions.ACCOUNT_CHANGE_INVALID_DETAIL
ACCOUNT_CHANGE_RECEIVED_MESSAGE = password_change_actions.ACCOUNT_CHANGE_RECEIVED_MESSAGE
ACCOUNT_CHANGE_NOT_FOUND_DETAIL = password_change_actions.ACCOUNT_CHANGE_NOT_FOUND_DETAIL
ACCOUNT_CHANGE_NOT_PENDING_DETAIL = password_change_actions.ACCOUNT_CHANGE_NOT_PENDING_DETAIL
ACCOUNT_CHANGE_PENDING_DETAIL = password_change_actions.ACCOUNT_CHANGE_PENDING_DETAIL
ACCOUNT_CHANGE_EXPIRED_DETAIL = password_change_actions.ACCOUNT_CHANGE_EXPIRED_DETAIL


def _missing_web_dependency_message() -> str:
    return (
        'FluxTuner Web dependencies are not installed. Install them with: pip install -e ".[web]"'
    )


def _read_template(name: str) -> str:
    template_path = resources.files("fluxtuner.web").joinpath("templates").joinpath(name)
    return template_path.read_text(encoding="utf-8")


def create_app(
    metadata_coordinator_factory: Callable[[], MetadataCoordinator] | None = None,
) -> Any:
    """Create the experimental FluxTuner Web application."""
    try:
        from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
        from fastapi.responses import FileResponse, HTMLResponse
        from fastapi.staticfiles import StaticFiles

        from fluxtuner.web.routes import admin as admin_routes
        from fluxtuner.web.routes import auth as auth_routes
        from fluxtuner.web.routes import library as library_routes
        from fluxtuner.web.routes import metadata as metadata_routes
        from fluxtuner.web.routes import public as public_routes

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

    coordinator_factory = metadata_coordinator_factory or (
        lambda: MetadataCoordinator(SystemStreamTargetResolver())
    )

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        coordinator = coordinator_factory()
        app_instance.state.metadata_coordinator = coordinator
        try:
            yield
        finally:
            coordinator.close(wait=True)
            del app_instance.state.metadata_coordinator

    app = FastAPI(
        title=f"{__app_name__} Web",
        version=__version__,
        description="FluxTuner web/server interface.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def add_static_cache_headers(request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/") and path.endswith((".js", ".webmanifest")):
            response.headers["Cache-Control"] = "no-cache"
        return response

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

    app.include_router(public_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(library_routes.router)
    app.include_router(metadata_routes.router)
    app.include_router(admin_routes.router)

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
