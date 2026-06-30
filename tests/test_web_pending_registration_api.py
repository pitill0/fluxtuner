# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    ACCOUNT_PENDING_DETAIL,
    ADMIN_REQUIRED_DETAIL,
    CSRF_ERROR_DETAIL,
    CSRF_HEADER_NAME,
    FIELD_TOO_LONG_DETAIL,
    RATE_LIMIT_DETAIL,
    REGISTER_RECEIVED_MESSAGE,
    REGISTER_USER_EXISTS_DETAIL,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"
OTHER_PASSWORD = "another correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "pending-registration.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    return TestClient(create_app())


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


def login(client: TestClient, username: str, password: str = VALID_PASSWORD) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def csrf_headers(csrf_token: str) -> dict[str, str]:
    return {CSRF_HEADER_NAME: csrf_token}


def test_public_registration_creates_pending_inactive_user(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "display_name": "Alice",
            "note": "Home server access",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": db.APPROVAL_PENDING,
        "message": REGISTER_RECEIVED_MESSAGE,
    }
    assert "set-cookie" not in response.headers

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is not None
    assert user["display_name"] == "Alice"
    assert user["is_active"] is False
    assert user["approval_status"] == db.APPROVAL_PENDING
    assert user["signup_note"] == "Home server access"
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_public_registration_rejects_oversized_profile_fields(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "display_name": "A" * 121,
            "note": "Home server access",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": FIELD_TOO_LONG_DETAIL}

    note_response = client.post(
        "/api/auth/register",
        json={
            "username": "bob",
            "password": VALID_PASSWORD,
            "note": "N" * 1001,
        },
    )

    assert note_response.status_code == 400
    assert note_response.json() == {"detail": FIELD_TOO_LONG_DETAIL}

    with db.connect() as conn:
        alice = db.get_user_by_username(conn, "alice")
        bob = db.get_user_by_username(conn, "bob")

    assert alice is None
    assert bob is None


def test_pending_user_login_only_discloses_pending_after_correct_password(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    wrong_password = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": OTHER_PASSWORD},
    )
    assert wrong_password.status_code == 401

    correct_password = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert correct_password.status_code == 403
    assert correct_password.json() == {"detail": ACCOUNT_PENDING_DETAIL}


def test_admin_can_approve_pending_user_and_user_can_login(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")
    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    response = client.post(
        "/api/admin/users/alice/approve",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json()["user"]["approval_status"] == db.APPROVAL_APPROVED
    assert response.json()["user"]["is_active"] is True

    client.post("/api/auth/logout", headers=csrf_headers(csrf_token))
    user_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert user_login.status_code == 200


def test_admin_can_reject_pending_user_and_login_stays_blocked(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")
    client.post(
        "/api/auth/register",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    response = client.post(
        "/api/admin/users/alice/reject",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json()["user"]["approval_status"] == db.APPROVAL_REJECTED
    assert response.json()["user"]["is_active"] is False

    client.post("/api/auth/logout", headers=csrf_headers(csrf_token))
    user_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert user_login.status_code == 401


def test_pending_admin_actions_require_admin_and_csrf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    non_admin = client.post(
        "/api/admin/users/alice/approve",
        headers=csrf_headers(csrf_token),
    )
    assert non_admin.status_code == 403
    assert non_admin.json() == {"detail": ADMIN_REQUIRED_DETAIL}

    client.post("/api/auth/logout", headers=csrf_headers(csrf_token))
    create_user("admin", is_admin=True)
    login(client, "admin")
    missing_csrf = client.post("/api/admin/users/alice/approve")
    assert missing_csrf.status_code == 403
    assert missing_csrf.json() == {"detail": CSRF_ERROR_DETAIL}


def test_public_registration_rejects_duplicate_username(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": REGISTER_USER_EXISTS_DETAIL}


def test_public_registration_rate_limits_duplicate_requests(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    for _ in range(auth.MAX_FAILED_LOGIN_ATTEMPTS):
        response = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": VALID_PASSWORD},
        )
        assert response.status_code == 409

    blocked = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": RATE_LIMIT_DETAIL}


def test_duplicate_registration_attempts_do_not_rate_limit_login(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    for _ in range(auth.MAX_FAILED_LOGIN_ATTEMPTS):
        response = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": VALID_PASSWORD},
        )
        assert response.status_code == 409

    login_response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert login_response.status_code == 200


def test_public_registration_rate_limit_is_client_wide(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)

    for index in range(auth.MAX_FAILED_LOGIN_ATTEMPTS):
        response = client.post(
            "/api/auth/register",
            json={
                "username": f"pending-{index}",
                "password": VALID_PASSWORD,
            },
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/auth/register",
        json={"username": "pending-blocked", "password": VALID_PASSWORD},
    )

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": RATE_LIMIT_DETAIL}
