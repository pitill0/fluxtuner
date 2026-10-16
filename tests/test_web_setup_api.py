# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    FIELD_TOO_LONG_DETAIL,
    SETUP_LOCAL_ONLY_DETAIL,
    SETUP_UNAVAILABLE_DETAIL,
    SETUP_VERIFICATION_ERROR_DETAIL,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "setup.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    return TestClient(create_app())


def test_setup_status_is_available_without_configured_admin(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/setup/status")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["configured_admin_exists"] is False


def test_setup_creates_first_admin_and_session(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["setup_complete"] is True
    assert payload["user"]["username"] == "alice"
    assert payload["user"]["is_admin"] is True
    assert payload["csrf_token"]

    recovery_codes = payload["recovery_codes"]
    assert len(recovery_codes) == 8
    assert len(set(recovery_codes)) == 8
    assert all(code.startswith("FT-RCV-") for code in recovery_codes)

    assert "token" not in payload

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is not None
    assert user["is_admin"] is True
    assert user["is_active"] is True
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_setup_rejects_oversized_username(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "u" * 81,
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": FIELD_TOO_LONG_DETAIL}


def test_setup_is_blocked_after_admin_exists(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    first = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/setup/create-admin",
        json={
            "username": "bob",
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )

    assert second.status_code == 403
    assert second.json() == {"detail": SETUP_UNAVAILABLE_DETAIL}


def test_setup_requires_configured_token_when_env_is_set(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "setup_token": "wrong",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": SETUP_VERIFICATION_ERROR_DETAIL}

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        user = db.get_user_by_username(conn, "alice")

    assert user is None


def test_setup_without_env_token_is_local_only(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.delenv("FLUXTUNER_WEB_SETUP_TOKEN", raising=False)
    monkeypatch.setattr("fluxtuner.web.setup.setup_request_is_local", lambda _request: False)

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": SETUP_LOCAL_ONLY_DETAIL}


def test_setup_rejects_weak_password(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": "short",
            "setup_token": "setup-secret",
        },
    )

    assert response.status_code == 400

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        user = db.get_user_by_username(conn, "alice")

    assert user is None


def test_setup_status_unavailable_after_admin_exists(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )
    assert response.status_code == 200

    status = client.get("/api/setup/status")

    assert status.status_code == 200
    assert status.json()["available"] is False
    assert status.json()["configured_admin_exists"] is True


def test_setup_existing_user_invalidates_recovery_codes(tmp_path, monkeypatch) -> None:
    from fluxtuner.core import recovery_codes

    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password("old correct horse battery staple"),
            is_admin=False,
            is_active=True,
        )
        original_codes = recovery_codes.bootstrap_recovery_codes(conn, user_id)
        assert original_codes is not None
        conn.commit()

    response = client.post(
        "/api/setup/create-admin",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "setup_token": "setup-secret",
        },
    )

    assert response.status_code == 200

    replacement_codes = response.json()["recovery_codes"]
    assert len(replacement_codes) == 8
    assert set(replacement_codes).isdisjoint(original_codes)

    with db.connect() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM web_recovery_codes WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

    assert remaining == 8
