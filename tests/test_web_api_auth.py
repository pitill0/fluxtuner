# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    AUTH_ERROR_DETAIL,
    create_app,
)
from fluxtuner.web.security import CSRF_HEADER_NAME, SESSION_COOKIE_NAME

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


def test_active_session_is_renewed_without_changing_csrf_token(tmp_path, monkeypatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    monkeypatch.setattr(auth, "utc_now", lambda: clock["now"])
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "1000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_ABSOLUTE_MAX_AGE_SECONDS", "2000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_RENEWAL_INTERVAL_SECONDS", "100")
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    csrf_token = login.json()["csrf_token"]
    clock["now"] = now + timedelta(seconds=100)

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["csrf_token"] == csrf_token
    assert "Max-Age=1000" in me.headers["set-cookie"]
    with db.connect() as conn:
        session_row = conn.execute("SELECT last_seen_at, expires_at FROM web_sessions").fetchone()
    assert session_row is not None
    assert auth.parse_datetime(session_row["last_seen_at"]) == clock["now"]
    assert auth.parse_datetime(session_row["expires_at"]) == now + timedelta(seconds=1100)


def test_active_session_is_not_written_before_renewal_interval(tmp_path, monkeypatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    monkeypatch.setattr(auth, "utc_now", lambda: clock["now"])
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "1000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_ABSOLUTE_MAX_AGE_SECONDS", "2000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_RENEWAL_INTERVAL_SECONDS", "100")
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    clock["now"] = now + timedelta(seconds=99)

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert "set-cookie" not in me.headers
    with db.connect() as conn:
        last_seen_at = conn.execute("SELECT last_seen_at FROM web_sessions").fetchone()[0]
    assert auth.parse_datetime(last_seen_at) == now


def test_session_is_rejected_at_absolute_lifetime(tmp_path, monkeypatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    monkeypatch.setattr(auth, "utc_now", lambda: clock["now"])
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "1000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_ABSOLUTE_MAX_AGE_SECONDS", "200")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_RENEWAL_INTERVAL_SECONDS", "50")
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    clock["now"] = now + timedelta(seconds=200)

    me = client.get("/api/auth/me")

    assert me.status_code == 401


def test_login_cookie_and_database_expiry_are_capped_by_absolute_lifetime(
    tmp_path, monkeypatch
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "1000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_ABSOLUTE_MAX_AGE_SECONDS", "200")
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert login.status_code == 200
    assert "Max-Age=200" in login.headers["set-cookie"]
    with db.connect() as conn:
        expires_at = conn.execute("SELECT expires_at FROM web_sessions").fetchone()[0]
    assert auth.parse_datetime(expires_at) == now + timedelta(seconds=200)


def test_login_does_not_renew_or_restore_previous_session_cookie(tmp_path, monkeypatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    monkeypatch.setattr(auth, "utc_now", lambda: clock["now"])
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "1000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_ABSOLUTE_MAX_AGE_SECONDS", "2000")
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_RENEWAL_INTERVAL_SECONDS", "100")
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    first_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    first_cookie = first_login.cookies[SESSION_COOKIE_NAME]
    clock["now"] = now + timedelta(seconds=100)

    second_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert second_login.status_code == 200
    assert second_login.cookies[SESSION_COOKIE_NAME] != first_cookie
    assert client.cookies[SESSION_COOKIE_NAME] == second_login.cookies[SESSION_COOKIE_NAME]
    with db.connect() as conn:
        previous_last_seen = conn.execute(
            "SELECT last_seen_at FROM web_sessions ORDER BY id LIMIT 1"
        ).fetchone()[0]
    assert auth.parse_datetime(previous_last_seen) == now


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
