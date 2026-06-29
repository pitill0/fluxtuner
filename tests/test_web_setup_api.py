# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    SETUP_LOCAL_ONLY_DETAIL,
    SETUP_UNAVAILABLE_DETAIL,
    SETUP_VERIFICATION_ERROR_DETAIL,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "setup.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
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
    monkeypatch.setattr("fluxtuner.web.app._setup_request_is_local", lambda _request: False)

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
