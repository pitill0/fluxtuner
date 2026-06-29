# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.web import auth

VALID_PASSWORD = "correct horse battery staple"


def test_hash_password_returns_argon2id_hash() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != VALID_PASSWORD
    assert VALID_PASSWORD not in password_hash


def test_hash_password_uses_random_salt() -> None:
    first_hash = auth.hash_password(VALID_PASSWORD)
    second_hash = auth.hash_password(VALID_PASSWORD)

    assert first_hash != second_hash
    assert auth.verify_password(VALID_PASSWORD, first_hash) is True
    assert auth.verify_password(VALID_PASSWORD, second_hash) is True


def test_verify_password_accepts_correct_password() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.verify_password(VALID_PASSWORD, password_hash) is True


def test_verify_password_rejects_wrong_password() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.verify_password("wrong horse battery staple", password_hash) is False


def test_verify_password_rejects_invalid_hash() -> None:
    assert auth.verify_password(VALID_PASSWORD, "not-a-valid-hash") is False
    assert auth.verify_password(VALID_PASSWORD, None) is False
    assert auth.verify_password("", "not-a-valid-hash") is False


def test_password_needs_rehash_is_false_for_current_hash() -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)

    assert auth.password_needs_rehash(password_hash) is False


def test_password_needs_rehash_is_true_for_invalid_hash() -> None:
    assert auth.password_needs_rehash("not-a-valid-hash") is True
    assert auth.password_needs_rehash(None) is True


def test_validate_password_rejects_weak_passwords() -> None:
    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("short")

    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("               ")

    with pytest.raises(auth.PasswordValidationError):
        auth.validate_password("a" * (auth.MAX_PASSWORD_BYTES + 1))


def test_password_hash_parameters_are_explicit() -> None:
    parameters = auth.password_hash_parameters()

    assert parameters == {
        "algorithm": "argon2id",
        "memory_cost_kib": 65536,
        "time_cost": 3,
        "parallelism": 4,
        "hash_len": 32,
        "salt_len": 16,
        "min_password_length": 15,
        "max_password_bytes": 1024,
    }


def test_create_session_stores_only_token_hash(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")
        token = auth.create_session(conn, user_id)
        row = conn.execute("SELECT token_hash FROM web_sessions").fetchone()
        conn.commit()

    assert row is not None
    assert row["token_hash"] != token
    assert row["token_hash"] == auth.hash_session_token(token)


def test_get_session_user_returns_active_user(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice", display_name="Alice")
        token = auth.create_session(conn, user_id)
        conn.commit()

    with db.connect() as conn:
        user = auth.get_session_user(conn, token)

    assert user is not None
    assert user["id"] == user_id
    assert user["username"] == "alice"


def test_get_session_rejects_revoked_session(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")
        token = auth.create_session(conn, user_id)
        assert auth.revoke_session(conn, token) is True
        conn.commit()

    with db.connect() as conn:
        assert auth.get_session(conn, token) is None
        assert auth.get_session_user(conn, token) is None


def test_get_session_rejects_expired_session(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    now = datetime(2026, 1, 1, tzinfo=UTC)

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")
        token = auth.create_session(conn, user_id, max_age_seconds=10, now=now)
        conn.commit()

    with db.connect() as conn:
        assert auth.get_session(conn, token, now=now + timedelta(seconds=9)) is not None
        assert auth.get_session(conn, token, now=now + timedelta(seconds=10)) is None
        assert auth.get_session_user(conn, token, now=now + timedelta(seconds=11)) is None


def test_invalid_session_tokens_are_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    with db.connect() as conn:
        assert auth.get_session(conn, None) is None
        assert auth.get_session(conn, "") is None
        assert auth.get_session(conn, "not-a-real-session") is None
        assert auth.revoke_session(conn, None) is False
        assert auth.revoke_session(conn, "not-a-real-session") is False


def test_purge_expired_sessions(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "sessions.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()

    now = datetime(2026, 1, 1, tzinfo=UTC)

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")
        expired_token = auth.create_session(conn, user_id, max_age_seconds=10, now=now)
        active_token = auth.create_session(conn, user_id, max_age_seconds=100, now=now)
        assert expired_token != active_token
        deleted = auth.purge_expired_sessions(conn, now=now + timedelta(seconds=11))
        remaining_count = conn.execute("SELECT COUNT(*) FROM web_sessions").fetchone()[0]
        conn.commit()

    assert deleted == 1
    assert remaining_count == 1
