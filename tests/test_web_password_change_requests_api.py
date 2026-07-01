# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import (
    ACCOUNT_CHANGE_EXPIRED_DETAIL,
    ACCOUNT_CHANGE_RECEIVED_MESSAGE,
    ADMIN_REQUIRED_DETAIL,
    CSRF_ERROR_DETAIL,
    CSRF_HEADER_NAME,
    create_app,
)

VALID_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another correct horse battery staple"
OTHER_PASSWORD = "yet another correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "password-change-requests.db")
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


def request_password_change(
    client: TestClient,
    username: str,
    *,
    password: str = NEW_PASSWORD,
    note: str = "Forgot it on the family phone",
):
    return client.post(
        "/api/auth/password-change-requests",
        json={"username": username, "new_password": password, "note": note},
    )


def test_public_password_change_request_returns_generic_message_for_known_user(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    user_id = create_user("alice")

    response = request_password_change(client, "alice")

    assert response.status_code == 200
    assert response.json() == {"message": ACCOUNT_CHANGE_RECEIVED_MESSAGE}

    with db.connect() as conn:
        requests = db.list_password_change_requests(conn)

    assert len(requests) == 1
    assert requests[0]["user_id"] == user_id
    assert requests[0]["username"] == "alice"
    assert requests[0]["note"] == "Forgot it on the family phone"
    assert requests[0]["status"] == db.ACCOUNT_CHANGE_PENDING
    assert auth.verify_password(NEW_PASSWORD, str(requests[0]["password_hash"])) is True


def test_public_password_change_request_is_generic_for_unknown_user(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = request_password_change(client, "missing")

    assert response.status_code == 200
    assert response.json() == {"message": ACCOUNT_CHANGE_RECEIVED_MESSAGE}

    with db.connect() as conn:
        requests = db.list_password_change_requests(conn)

    assert requests == []


def test_public_password_change_request_replaces_existing_pending_request(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    first = request_password_change(client, "alice", password=NEW_PASSWORD)
    second = request_password_change(client, "alice", password=OTHER_PASSWORD, note="new note")

    assert first.status_code == 200
    assert second.status_code == 200

    with db.connect() as conn:
        requests = db.list_password_change_requests(conn)

    assert len(requests) == 1
    assert requests[0]["note"] == "new note"
    assert auth.verify_password(OTHER_PASSWORD, str(requests[0]["password_hash"])) is True


def test_non_admin_cannot_list_password_change_requests(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")

    response = client.get("/api/admin/password-change-requests")

    assert response.status_code == 403
    assert response.json() == {"detail": ADMIN_REQUIRED_DETAIL}


def test_admin_password_change_request_mutations_require_csrf(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")
    login(client, "admin")
    request_password_change(client, "alice")

    with db.connect() as conn:
        request_id = db.list_password_change_requests(conn)[0]["id"]

    response = client.post(f"/api/admin/password-change-requests/{request_id}/approve")

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_ERROR_DETAIL}


def test_admin_can_approve_password_change_request_and_revoke_sessions(
    tmp_path,
    monkeypatch,
) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    alice_id = create_user("alice")
    csrf_token = login(client, "admin")

    with db.connect() as conn:
        old_token = auth.create_session(conn, alice_id)
        conn.commit()

    request_password_change(client, "alice")
    with db.connect() as conn:
        request_id = db.list_password_change_requests(conn)[0]["id"]

    response = client.post(
        f"/api/admin/password-change-requests/{request_id}/approve",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "alice"

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        assert auth.verify_password(NEW_PASSWORD, str(user["password_hash"])) is True
        assert auth.get_session(conn, old_token) is None
        resolved = db.get_password_change_request(conn, request_id)

    assert resolved is not None
    assert resolved["status"] == db.ACCOUNT_CHANGE_APPROVED

    user_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": NEW_PASSWORD},
    )
    assert user_login.status_code == 200


def test_admin_can_reject_password_change_request(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")
    csrf_token = login(client, "admin")
    request_password_change(client, "alice")

    with db.connect() as conn:
        request_id = db.list_password_change_requests(conn)[0]["id"]

    response = client.post(
        f"/api/admin/password-change-requests/{request_id}/reject",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 200
    assert response.json() == {"status": db.ACCOUNT_CHANGE_REJECTED}

    with db.connect() as conn:
        resolved = db.get_password_change_request(conn, request_id)
        user = db.get_user_by_username(conn, "alice")

    assert resolved is not None
    assert resolved["status"] == db.ACCOUNT_CHANGE_REJECTED
    assert user is not None
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_admin_cannot_approve_expired_password_change_request(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    alice_id = create_user("alice")
    csrf_token = login(client, "admin")

    with db.connect() as conn:
        request_id = db.upsert_pending_password_change_request(
            conn,
            alice_id,
            password_hash=auth.hash_password(NEW_PASSWORD),
            expires_at="2000-01-01T00:00:00+00:00",
        )
        conn.commit()

    response = client.post(
        f"/api/admin/password-change-requests/{request_id}/approve",
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": ACCOUNT_CHANGE_EXPIRED_DETAIL}

    with db.connect() as conn:
        resolved = db.get_password_change_request(conn, request_id)

    assert resolved is not None
    assert resolved["status"] == db.ACCOUNT_CHANGE_EXPIRED
