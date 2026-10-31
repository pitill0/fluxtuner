# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""HTTP session resolution and response cache policy for the Web application."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request, Response

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web import context as web_context
from fluxtuner.web.security import (
    SESSION_COOKIE_NAME,
    session_absolute_max_age,
    session_cookie_max_age,
    session_renewal_interval,
    set_session_cookie,
)

SESSION_COOKIE_MUTATION_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/setup/create-admin",
    }
)


def _resolve_and_renew_session_sync(
    token: str,
    request_path: str,
) -> tuple[Any | None, int | None]:
    with db.connect() as conn:
        session = auth.get_session(
            conn,
            token,
            absolute_max_age_seconds=session_absolute_max_age(),
        )
        user = auth.get_user_for_session(conn, session) if session is not None else None
        renewed_cookie_max_age: int | None = None

        if (
            session is not None
            and user is not None
            and request_path not in SESSION_COOKIE_MUTATION_PATHS
        ):
            max_age = session_cookie_max_age()
            renewed_cookie_max_age = auth.renew_session(
                conn,
                session,
                max_age_seconds=max_age,
                absolute_max_age_seconds=session_absolute_max_age(),
                renewal_interval_seconds=session_renewal_interval(max_age),
            )
            if renewed_cookie_max_age is not None:
                conn.commit()

    return user, renewed_cookie_max_age


async def resolve_and_renew_session(request: Request, call_next: Any) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    renewed_cookie_max_age: int | None = None

    if token and request.url.path.startswith("/api/"):
        user, renewed_cookie_max_age = await asyncio.to_thread(
            _resolve_and_renew_session_sync,
            token,
            request.url.path,
        )
        setattr(
            request.state,
            web_context.AUTHENTICATED_USER_STATE_KEY,
            user,
        )

    response = await call_next(request)
    if token and renewed_cookie_max_age is not None:
        set_session_cookie(response, token, max_age=renewed_cookie_max_age)
    return response


async def add_static_cache_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and not (path == "/api/health" or path.startswith("/api/public/")):
        response.headers["Cache-Control"] = "no-store"
    if (
        path.startswith("/static/")
        and not path.startswith("/static/build/")
        and path.endswith((".js", ".css", ".webmanifest"))
    ):
        response.headers["Cache-Control"] = "no-cache"
    return response


def register_http_middleware(app: FastAPI) -> None:
    """Keep cache policy outside session resolution in the request stack."""
    app.middleware("http")(resolve_and_renew_session)
    app.middleware("http")(add_static_cache_headers)
