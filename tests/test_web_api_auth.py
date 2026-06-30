# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    AUTH_ERROR_DETAIL,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"


def create_user(username: str, password: str = VALID_PASSWORD, *, is_active: bool = True) -> int:
    password_hash = auth.hash_password(password)
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=password_hash,
            is_active=is_active,
        )
        conn.commit()
    return user_id


def make_client(tmp_path, monkeypatch) -> TestClient:
    db_file = tmp_path / "web-auth.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    return TestClient(create_app())


def test_login_sets_http_only_session_cookie_and_me_returns_user(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    user_id = create_user("alice")

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"] == {
        "id": user_id,
        "username": "alice",
        "display_name": "alice",
        "is_admin": False,
    }
    assert payload["csrf_token"]
    assert "token" not in payload

    set_cookie = response.headers["set-cookie"]
    assert SESSION_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"
    assert me.json()["csrf_token"] == payload["csrf_token"]


def test_login_rejects_wrong_password_with_generic_error(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrong horse battery staple"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTH_ERROR_DETAIL}
    assert SESSION_COOKIE_NAME not in response.cookies


def test_login_rejects_missing_user_with_same_generic_error(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={"username": "missing", "password": VALID_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTH_ERROR_DETAIL}


def test_login_rejects_inactive_user(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice", is_active=False)

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTH_ERROR_DETAIL}


def test_logout_requires_csrf_token(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 403


def test_logout_revokes_session_with_csrf_token(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    csrf_token = str(login.json()["csrf_token"])

    logout = client.post(
        "/api/auth/logout",
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    assert logout.status_code == 200
    assert logout.json()["status"] == "ok"

    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_me_requires_authentication(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_login_rate_limit_blocks_repeated_failures(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    for _ in range(auth.MAX_FAILED_LOGIN_ATTEMPTS):
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "wrong horse battery staple"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many login attempts. Try again later."}


def test_secure_cookie_is_enabled_by_default(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "web-auth.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.delenv("FLUXTUNER_WEB_SECURE_COOKIES", raising=False)
    db.init_db()
    create_user("alice")

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_logout_accepts_csrf_header(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    csrf_token = str(login.json()["csrf_token"])

    logout = client.post(
        "/api/auth/logout",
        headers={CSRF_HEADER_NAME: csrf_token},
    )

    assert logout.status_code == 200
