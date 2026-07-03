# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.context import ensure_web_schema
from fluxtuner.web.guards import require_admin_user, require_authenticated_user, require_csrf
from fluxtuner.web.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
)

AUTH_REQUIRED_DETAIL = "Authentication required."
ADMIN_REQUIRED_DETAIL = "Administrator access required."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."


def _request(*, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None):
    return SimpleNamespace(cookies=cookies or {}, headers=headers or {})


def test_require_csrf_accepts_matching_session_token() -> None:
    token = "session-token"
    request = _request(
        cookies={SESSION_COOKIE_NAME: token},
        headers={CSRF_HEADER_NAME: csrf_token_for_session_token(token)},
    )

    require_csrf(request, csrf_error_detail=CSRF_ERROR_DETAIL)


def test_require_csrf_rejects_missing_header() -> None:
    request = _request(cookies={SESSION_COOKIE_NAME: "session-token"})

    with pytest.raises(HTTPException) as exc_info:
        require_csrf(request, csrf_error_detail=CSRF_ERROR_DETAIL)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == CSRF_ERROR_DETAIL


def test_require_authenticated_user_returns_session_user(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    with db.connect() as conn:
        ensure_web_schema(conn)
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash="hash",
            is_active=True,
        )
        token = auth.create_session(conn, user_id)

    request = _request(cookies={SESSION_COOKIE_NAME: token})

    user = require_authenticated_user(request, auth_required_detail=AUTH_REQUIRED_DETAIL)

    assert user["username"] == "alice"


def test_require_authenticated_user_rejects_missing_session() -> None:
    request = _request()

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_user(request, auth_required_detail=AUTH_REQUIRED_DETAIL)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == AUTH_REQUIRED_DETAIL


def test_require_admin_user_returns_admin_session_user(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    with db.connect() as conn:
        ensure_web_schema(conn)
        user_id = db.get_or_create_user(
            conn,
            "admin",
            password_hash="hash",
            is_admin=True,
            is_active=True,
        )
        token = auth.create_session(conn, user_id)

    request = _request(cookies={SESSION_COOKIE_NAME: token})

    user = require_admin_user(
        request,
        auth_required_detail=AUTH_REQUIRED_DETAIL,
        admin_required_detail=ADMIN_REQUIRED_DETAIL,
    )

    assert user["username"] == "admin"
    assert bool(user["is_admin"])


def test_require_admin_user_rejects_non_admin_session_user(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    with db.connect() as conn:
        ensure_web_schema(conn)
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash="hash",
            is_active=True,
        )
        token = auth.create_session(conn, user_id)

    request = _request(cookies={SESSION_COOKIE_NAME: token})

    with pytest.raises(HTTPException) as exc_info:
        require_admin_user(
            request,
            auth_required_detail=AUTH_REQUIRED_DETAIL,
            admin_required_detail=ADMIN_REQUIRED_DETAIL,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ADMIN_REQUIRED_DETAIL
