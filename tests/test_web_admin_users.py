# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import pytest
from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.admin_users import (
    ADMIN_LAST_ADMIN_DETAIL,
    ADMIN_USER_NOT_FOUND_DETAIL,
    active_admin_count,
    admin_target_user,
    ensure_not_last_active_admin,
    revoke_user_sessions,
)

VALID_PASSWORD = "correct horse battery staple"


def create_user(
    conn,
    username: str,
    *,
    is_admin: bool = False,
    is_active: bool = True,
    password_hash: str | None = None,
) -> int:
    return db.get_or_create_user(
        conn,
        username,
        password_hash=password_hash
        if password_hash is not None
        else auth.hash_password(VALID_PASSWORD),
        is_admin=is_admin,
        is_active=is_active,
    )


def test_active_admin_count_requires_active_admin_with_password(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "admin-users.db")
    db.init_db()

    with db.connect() as conn:
        create_user(conn, "admin", is_admin=True)
        create_user(conn, "inactive-admin", is_admin=True, is_active=False)
        create_user(conn, "normal-user")
        create_user(conn, "legacy-admin", is_admin=True, password_hash="")
        conn.commit()

        assert active_admin_count(conn) == 1


def test_admin_target_user_returns_user_or_raises_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "admin-target.db")
    db.init_db()

    with db.connect() as conn:
        create_user(conn, "alice")
        conn.commit()

        assert admin_target_user(conn, "alice")["username"] == "alice"
        with pytest.raises(HTTPException) as exc_info:
            admin_target_user(conn, "missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == ADMIN_USER_NOT_FOUND_DETAIL


def test_ensure_not_last_active_admin_blocks_last_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "last-admin.db")
    db.init_db()

    with db.connect() as conn:
        create_user(conn, "admin", is_admin=True)
        create_user(conn, "alice")
        conn.commit()

        admin = admin_target_user(conn, "admin")
        user = admin_target_user(conn, "alice")

        with pytest.raises(HTTPException) as exc_info:
            ensure_not_last_active_admin(conn, admin)
        ensure_not_last_active_admin(conn, user)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == ADMIN_LAST_ADMIN_DETAIL


def test_ensure_not_last_active_admin_allows_when_another_admin_exists(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "two-admins.db")
    db.init_db()

    with db.connect() as conn:
        create_user(conn, "admin", is_admin=True)
        create_user(conn, "other-admin", is_admin=True)
        conn.commit()

        ensure_not_last_active_admin(conn, admin_target_user(conn, "admin"))


def test_revoke_user_sessions_only_revokes_active_sessions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "sessions.db")
    db.init_db()

    with db.connect() as conn:
        user_id = create_user(conn, "alice")
        active_token = auth.create_session(conn, user_id)
        old_token = auth.create_session(conn, user_id)
        conn.execute(
            """
            UPDATE web_sessions
            SET revoked_at = ?
            WHERE token_hash = ?
            """,
            (db.utc_now(), auth.hash_session_token(old_token)),
        )
        conn.commit()

        revoke_user_sessions(conn, user_id)
        active_row = conn.execute(
            "SELECT revoked_at FROM web_sessions WHERE token_hash = ?",
            (auth.hash_session_token(active_token),),
        ).fetchone()
        old_row = conn.execute(
            "SELECT revoked_at FROM web_sessions WHERE token_hash = ?",
            (auth.hash_session_token(old_token),),
        ).fetchone()

    assert active_row["revoked_at"] is not None
    assert old_row["revoked_at"] is not None
