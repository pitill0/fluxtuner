# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import pytest
from fastapi import HTTPException

from fluxtuner.core import db
from fluxtuner.web import auth, registration_actions

VALID_PASSWORD = "correct horse battery staple"


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "registration-actions.db")
    db.init_db()
    conn = db.connect()
    return conn


def test_register_payload_creates_pending_user(tmp_path, monkeypatch) -> None:
    conn = setup_db(tmp_path, monkeypatch)
    try:
        payload = registration_actions.register_payload(
            conn,
            {
                "username": "Alice",
                "password": VALID_PASSWORD,
                "display_name": "Alice",
                "note": "Home access",
            },
            client_key="127.0.0.1",
            max_username_length=80,
            max_display_name_length=120,
            max_signup_note_length=1000,
            field_too_long_detail="too long",
            rate_limit_detail="rate limited",
        )

        user = db.get_user_by_username(conn, "Alice")
    finally:
        conn.close()

    assert payload == {
        "status": db.APPROVAL_PENDING,
        "message": registration_actions.REGISTER_RECEIVED_MESSAGE,
    }
    assert user is not None
    assert user["approval_status"] == db.APPROVAL_PENDING
    assert user["is_active"] is False
    assert user["display_name"] == "Alice"
    assert user["signup_note"] == "Home access"
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_register_payload_rejects_duplicate_user(tmp_path, monkeypatch) -> None:
    conn = setup_db(tmp_path, monkeypatch)
    try:
        db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password(VALID_PASSWORD),
        )
        conn.commit()

        with pytest.raises(HTTPException) as exc_info:
            registration_actions.register_payload(
                conn,
                {"username": "alice", "password": VALID_PASSWORD},
                client_key="127.0.0.1",
                max_username_length=80,
                max_display_name_length=120,
                max_signup_note_length=1000,
                field_too_long_detail="too long",
                rate_limit_detail="rate limited",
            )
    finally:
        conn.close()

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == registration_actions.REGISTER_USER_EXISTS_DETAIL


def test_register_payload_rejects_invalid_or_oversized_payload(tmp_path, monkeypatch) -> None:
    conn = setup_db(tmp_path, monkeypatch)
    try:
        with pytest.raises(HTTPException) as missing_exc:
            registration_actions.register_payload(
                conn,
                {"username": "", "password": ""},
                client_key="127.0.0.1",
                max_username_length=80,
                max_display_name_length=120,
                max_signup_note_length=1000,
                field_too_long_detail="too long",
                rate_limit_detail="rate limited",
            )

        with pytest.raises(HTTPException) as long_exc:
            registration_actions.register_payload(
                conn,
                {"username": "alice", "password": VALID_PASSWORD, "display_name": "A" * 121},
                client_key="127.0.0.1",
                max_username_length=80,
                max_display_name_length=120,
                max_signup_note_length=1000,
                field_too_long_detail="too long",
                rate_limit_detail="rate limited",
            )
    finally:
        conn.close()

    assert missing_exc.value.status_code == 400
    assert missing_exc.value.detail == registration_actions.REGISTER_INVALID_DETAIL
    assert long_exc.value.status_code == 400
    assert long_exc.value.detail == "too long"


def test_register_payload_respects_rate_limit(tmp_path, monkeypatch) -> None:
    conn = setup_db(tmp_path, monkeypatch)
    client_key = "127.0.0.1"
    try:
        for _ in range(auth.MAX_FAILED_LOGIN_ATTEMPTS):
            auth.record_login_attempt(
                conn,
                registration_actions.REGISTER_RATE_LIMIT_USERNAME,
                client_key,
                success=False,
            )
        conn.commit()

        with pytest.raises(HTTPException) as exc_info:
            registration_actions.register_payload(
                conn,
                {"username": "alice", "password": VALID_PASSWORD},
                client_key=client_key,
                max_username_length=80,
                max_display_name_length=120,
                max_signup_note_length=1000,
                field_too_long_detail="too long",
                rate_limit_detail="rate limited",
            )
    finally:
        conn.close()

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "rate limited"
