# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

import pytest
from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import admin_actions, auth
from fluxtuner.web.payloads import admin_user_payload

VALID_PASSWORD = "correct horse battery staple"


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "admin-actions.db")
    db.init_db()


def create_user(username: str, *, is_admin: bool = False, is_active: bool = True) -> int:
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=auth.hash_password(VALID_PASSWORD),
            is_admin=is_admin,
            is_active=is_active,
        )
        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()
        return user_id


def test_list_users_payload_counts_users(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")

    with db.connect() as conn:
        payload = admin_actions.list_users_payload(conn)

    assert payload["count"] >= 2
    usernames = {user["username"] for user in payload["users"]}
    assert {"admin", "alice"} <= usernames


def test_create_user_payload_creates_default_profile(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)

    with db.connect() as conn:
        payload = admin_actions.create_user_payload(
            conn,
            {"username": "alice", "password": VALID_PASSWORD},
            max_username_length=80,
            max_display_name_length=120,
            field_too_long_detail="too long",
        )

    assert payload["user"]["username"] == "alice"
    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        profiles = db.list_profiles(conn, user_id=int(user["id"]))
        assert any(profile["name"] == db.DEFAULT_PROFILE_NAME for profile in profiles)


def test_create_user_payload_rejects_duplicate_user(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    create_user("alice")

    with db.connect() as conn, pytest.raises(HTTPException) as exc_info:
        admin_actions.create_user_payload(
            conn,
            {"username": "alice", "password": VALID_PASSWORD},
            max_username_length=80,
            max_display_name_length=120,
            field_too_long_detail="too long",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == admin_actions.ADMIN_USER_EXISTS_DETAIL


def test_set_user_password_payload_revokes_sessions(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    user_id = create_user("alice")

    with db.connect() as conn:
        token = auth.create_session(conn, user_id)
        conn.commit()

    with db.connect() as conn:
        payload = admin_actions.set_user_password_payload(
            conn,
            "alice",
            {"password": "another correct horse battery staple"},
        )

    assert payload["user"]["username"] == "alice"
    with db.connect() as conn:
        assert auth.get_session_user(conn, token) is None


def test_delete_user_blocks_self_delete(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    admin_id = create_user("admin", is_admin=True)

    with db.connect() as conn, pytest.raises(HTTPException) as exc_info:
        admin_actions.delete_user(conn, "admin", admin_user_id=admin_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == admin_actions.ADMIN_SELF_DELETE_DETAIL


def test_set_user_approval_payload_updates_user(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    admin_id = create_user("admin", is_admin=True)
    create_user("alice")

    with db.connect() as conn:
        payload = admin_actions.set_user_approval_payload(
            conn,
            "alice",
            approval_status=db.APPROVAL_DISABLED,
            reviewed_by_user_id=admin_id,
            revoke_sessions=True,
            protect_last_admin=False,
        )

    assert payload["user"]["approval_status"] == db.APPROVAL_DISABLED


def test_set_user_admin_payload_promotes_user(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    create_user("alice")

    with db.connect() as conn:
        payload = admin_actions.set_user_admin_payload(
            conn,
            "alice",
            is_admin=True,
            protect_last_admin=False,
        )

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
    assert user is not None
    assert payload["user"] == admin_user_payload(user)
    assert payload["user"]["is_admin"] is True
