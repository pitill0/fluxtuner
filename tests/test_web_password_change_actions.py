# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth, password_change_actions, password_changes

VALID_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another correct horse battery staple"
OTHER_PASSWORD = "yet another correct horse battery staple"


def setup_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "password-change-actions.db")
    db.init_db()


def create_user(
    username: str,
    *,
    password: str = VALID_PASSWORD,
    is_admin: bool = False,
    is_active: bool = True,
) -> int:
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=auth.hash_password(password),
            is_admin=is_admin,
            is_active=is_active,
        )
        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()
        return user_id


def request_payload(
    username: str = "alice",
    *,
    password: str = NEW_PASSWORD,
    note: str = "Forgot it",
) -> dict[str, str]:
    return {"username": username, "new_password": password, "note": note}


def submit_password_change(conn, payload: dict[str, str] | None = None):
    return password_change_actions.request_password_change_payload(
        conn,
        payload or request_payload(),
        client_key="testclient",
        max_username_length=80,
        max_note_length=1000,
        field_too_long_detail="too long",
        rate_limit_detail="rate limited",
    )


def test_request_password_change_records_known_non_admin_user(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    user_id = create_user("alice")

    with db.connect() as conn:
        response = submit_password_change(conn)

    assert response == {"message": password_change_actions.ACCOUNT_CHANGE_RECEIVED_MESSAGE}
    with db.connect() as conn:
        requests = db.list_password_change_requests(conn)

    assert len(requests) == 1
    assert int(requests[0]["user_id"]) == user_id
    assert str(requests[0]["status"]) == db.ACCOUNT_CHANGE_PENDING
    assert auth.verify_password(NEW_PASSWORD, str(requests[0]["password_hash"])) is True


def test_request_password_change_is_generic_for_unknown_user(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)

    with db.connect() as conn:
        response = submit_password_change(conn, request_payload("missing"))

    assert response == {"message": password_change_actions.ACCOUNT_CHANGE_RECEIVED_MESSAGE}
    with db.connect() as conn:
        assert db.list_password_change_requests(conn) == []


def test_request_password_change_rejects_invalid_payload(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)

    with db.connect() as conn, pytest.raises(HTTPException) as exc_info:
        submit_password_change(conn, {"username": "alice", "new_password": ""})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == password_change_actions.ACCOUNT_CHANGE_INVALID_DETAIL


def test_list_password_change_requests_payload(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    create_user("alice")

    with db.connect() as conn:
        submit_password_change(conn)
        response = password_change_actions.list_password_change_requests_payload(conn)

    assert response["count"] == 1
    assert response["requests"][0]["username"] == "alice"


def test_approve_password_change_request_updates_password_and_revokes_sessions(
    tmp_path,
    monkeypatch,
) -> None:
    setup_db(tmp_path, monkeypatch)
    admin_id = create_user("admin", is_admin=True)
    alice_id = create_user("alice")

    with db.connect() as conn:
        old_token = auth.create_session(conn, alice_id)
        submit_password_change(conn)
        request_id = int(db.list_password_change_requests(conn)[0]["id"])

        response = password_change_actions.approve_password_change_request_payload(
            conn,
            request_id,
            resolved_by_user_id=admin_id,
        )

    assert response["user"]["username"] == "alice"
    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        assert auth.verify_password(NEW_PASSWORD, str(user["password_hash"])) is True
        assert auth.get_session(conn, old_token) is None
        requests = db.list_password_change_requests(conn, status=None)
        assert str(requests[0]["status"]) == db.ACCOUNT_CHANGE_APPROVED


def test_reject_password_change_request_marks_rejected(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    admin_id = create_user("admin", is_admin=True)
    create_user("alice")

    with db.connect() as conn:
        submit_password_change(conn)
        request_id = int(db.list_password_change_requests(conn)[0]["id"])

        response = password_change_actions.reject_password_change_request_payload(
            conn,
            request_id,
            resolved_by_user_id=admin_id,
        )

    assert response == {"status": db.ACCOUNT_CHANGE_REJECTED}
    with db.connect() as conn:
        requests = db.list_password_change_requests(conn, status=None)
        assert str(requests[0]["status"]) == db.ACCOUNT_CHANGE_REJECTED


def test_approve_expired_password_change_marks_expired(tmp_path, monkeypatch) -> None:
    setup_db(tmp_path, monkeypatch)
    admin_id = create_user("admin", is_admin=True)
    alice_id = create_user("alice")
    expired_at = auth.encode_datetime(auth.utc_now() - timedelta(seconds=1))

    with db.connect() as conn:
        db.upsert_pending_password_change_request(
            conn,
            alice_id,
            password_hash=auth.hash_password(OTHER_PASSWORD),
            note=None,
            expires_at=expired_at,
        )
        request_id = int(db.list_password_change_requests(conn)[0]["id"])

        with pytest.raises(HTTPException) as exc_info:
            password_change_actions.approve_password_change_request_payload(
                conn,
                request_id,
                resolved_by_user_id=admin_id,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == password_changes.ACCOUNT_CHANGE_EXPIRED_DETAIL
    with db.connect() as conn:
        requests = db.list_password_change_requests(conn, status=None)
        assert str(requests[0]["status"]) == db.ACCOUNT_CHANGE_EXPIRED
