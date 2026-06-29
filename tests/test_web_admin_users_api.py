# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    ADMIN_LAST_ADMIN_DETAIL,
    ADMIN_REQUIRED_DETAIL,
    ADMIN_USER_EXISTS_DETAIL,
    ADMIN_USER_NOT_FOUND_DETAIL,
    CSRF_ERROR_DETAIL,
    CSRF_HEADER_NAME,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"
OTHER_PASSWORD = "another correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "admin-users.db")
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


def test_admin_can_list_users_without_hashes(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")
    csrf_token = login(client, "admin")

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 2
    usernames = {user["username"] for user in payload["users"]}
    assert {"admin", "alice"} <= usernames
    assert all("password_hash" not in user for user in payload["users"])

    create_response = client.post(
        "/api/admin/users",
        json={"username": "bob", "password": VALID_PASSWORD},
        headers=csrf_headers(csrf_token),
    )
    assert create_response.status_code == 200


def test_non_admin_cannot_access_admin_users(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    response = client.get("/api/admin/users")
    assert response.status_code == 403
    assert response.json() == {"detail": ADMIN_REQUIRED_DETAIL}

    response = client.post(
        "/api/admin/users",
        json={"username": "bob", "password": VALID_PASSWORD},
        headers=csrf_headers(csrf_token),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": ADMIN_REQUIRED_DETAIL}


def test_admin_mutations_require_csrf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    login(client, "admin")

    response = client.post(
        "/api/admin/users",
        json={"username": "bob", "password": VALID_PASSWORD},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_ERROR_DETAIL}


def test_admin_can_create_user_and_reject_duplicates(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")

    response = client.post(
        "/api/admin/users",
        json={
            "username": "alice",
            "password": VALID_PASSWORD,
            "display_name": "Alice",
            "is_admin": False,
            "is_active": True,
        },
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "alice"
    assert response.json()["user"]["display_name"] == "Alice"
    assert response.json()["user"]["is_admin"] is False
    assert "password_hash" not in response.json()["user"]

    duplicate = client.post(
        "/api/admin/users",
        json={"username": "alice", "password": VALID_PASSWORD},
        headers=csrf_headers(csrf_token),
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": ADMIN_USER_EXISTS_DETAIL}


def test_admin_can_set_password_and_revoke_sessions(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    alice_id = create_user("alice")
    csrf_token = login(client, "admin")

    with db.connect() as conn:
        old_token = auth.create_session(conn, alice_id)
        conn.commit()

    response = client.post(
        "/api/admin/users/alice/password",
        json={"password": OTHER_PASSWORD},
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        assert auth.verify_password(OTHER_PASSWORD, str(user["password_hash"])) is True
        assert auth.get_session(conn, old_token) is None


def test_admin_can_deactivate_and_activate_user(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    alice_id = create_user("alice")
    csrf_token = login(client, "admin")

    with db.connect() as conn:
        old_token = auth.create_session(conn, alice_id)
        conn.commit()

    deactivate = client.post(
        "/api/admin/users/alice/deactivate",
        headers=csrf_headers(csrf_token),
    )

    assert deactivate.status_code == 200
    assert deactivate.json()["user"]["is_active"] is False

    with db.connect() as conn:
        assert auth.get_session(conn, old_token) is None

    activate = client.post(
        "/api/admin/users/alice/activate",
        headers=csrf_headers(csrf_token),
    )

    assert activate.status_code == 200
    assert activate.json()["user"]["is_active"] is True


def test_admin_can_grant_and_revoke_admin_role(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")
    csrf_token = login(client, "admin")

    grant = client.post(
        "/api/admin/users/alice/admin",
        headers=csrf_headers(csrf_token),
    )
    assert grant.status_code == 200
    assert grant.json()["user"]["is_admin"] is True

    revoke = client.delete(
        "/api/admin/users/alice/admin",
        headers=csrf_headers(csrf_token),
    )
    assert revoke.status_code == 200
    assert revoke.json()["user"]["is_admin"] is False


def test_last_active_admin_cannot_be_deactivated_or_demoted(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")

    deactivate = client.post(
        "/api/admin/users/admin/deactivate",
        headers=csrf_headers(csrf_token),
    )
    assert deactivate.status_code == 409
    assert deactivate.json() == {"detail": ADMIN_LAST_ADMIN_DETAIL}

    demote = client.delete(
        "/api/admin/users/admin/admin",
        headers=csrf_headers(csrf_token),
    )
    assert demote.status_code == 409
    assert demote.json() == {"detail": ADMIN_LAST_ADMIN_DETAIL}


def test_admin_user_missing_returns_404(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")

    response = client.post(
        "/api/admin/users/missing/deactivate",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": ADMIN_USER_NOT_FOUND_DETAIL}


def test_admin_resetting_own_password_revokes_current_session(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    csrf_token = login(client, "admin")

    response = client.post(
        "/api/admin/users/admin/password",
        json={"password": OTHER_PASSWORD},
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_admin_deactivating_self_revokes_current_session_when_another_admin_exists(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("backup", is_admin=True)
    csrf_token = login(client, "admin")

    response = client.post(
        "/api/admin/users/admin/deactivate",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is False

    me = client.get("/api/auth/me")
    assert me.status_code == 401
