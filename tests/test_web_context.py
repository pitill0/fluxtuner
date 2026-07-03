# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from types import SimpleNamespace

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.context import authenticated_user, effective_profile_name, ensure_web_schema
from fluxtuner.web.security import SESSION_COOKIE_NAME


def test_effective_profile_name_delegates_profile_resolution() -> None:
    assert effective_profile_name(None) is None
    assert effective_profile_name("") == ""
    assert effective_profile_name(" main ") == "main"


def test_ensure_web_schema_creates_web_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    with db.connect() as conn:
        ensure_web_schema(conn)
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "users" in tables
    assert "web_sessions" in tables
    assert "web_password_change_requests" in tables


def test_authenticated_user_returns_session_user(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    with db.connect() as conn:
        ensure_web_schema(conn)
        user_id = db.get_or_create_user(conn, "admin", password_hash="hash", is_admin=True)
        token = auth.create_session(conn, user_id)

    request = SimpleNamespace(cookies={SESSION_COOKIE_NAME: token})

    user = authenticated_user(request)

    assert user is not None
    assert user["username"] == "admin"
    assert user["is_admin"] == 1


def test_authenticated_user_returns_none_without_session(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    request = SimpleNamespace(cookies={})

    assert authenticated_user(request) is None
