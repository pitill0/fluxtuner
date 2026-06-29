# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.app import CSRF_HEADER_NAME, create_app

VALID_PASSWORD = "correct horse battery staple"


def make_client(tmp_path, monkeypatch) -> TestClient:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    return TestClient(create_app())


def create_user(username: str, *, is_admin: bool = False) -> int:
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=auth.hash_password(VALID_PASSWORD),
            is_admin=is_admin,
        )
        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()
        return user_id


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def csrf_headers(csrf_token: str) -> dict[str, str]:
    return {CSRF_HEADER_NAME: csrf_token}


def station_payload(name: str, url: str) -> dict[str, str]:
    return {"name": name, "url": url}


def test_dashboard_requires_authentication(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/dashboard")

    assert response.status_code == 401


def test_dashboard_returns_user_metrics_and_recent_items(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    station = station_payload("Alice Radio", "https://example.com/alice")
    assert (
        client.post("/api/favorites", json=station, headers=csrf_headers(csrf_token)).status_code
        == 200
    )
    assert (
        client.post("/api/history", json=station, headers=csrf_headers(csrf_token)).status_code
        == 200
    )
    assert (
        client.post(
            "/api/playlists",
            json={"name": "Morning"},
            headers=csrf_headers(csrf_token),
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/playlists/Morning/stations",
            json=station,
            headers=csrf_headers(csrf_token),
        ).status_code
        == 200
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["admin"] is None
    assert payload["user"]["favorites_count"] == 1
    assert payload["user"]["playlists_count"] == 1
    assert payload["user"]["playlist_stations_count"] == 1
    assert payload["user"]["history_count"] == 1
    assert payload["user"]["recent_history"][0]["name"] == "Alice Radio"
    assert payload["user"]["favorite_highlights"][0]["name"] == "Alice Radio"


def test_dashboard_keeps_user_metrics_private(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    create_user("bob")
    csrf_token = login(client, "alice")
    station = station_payload("Alice Radio", "https://example.com/alice")
    client.post("/api/favorites", json=station, headers=csrf_headers(csrf_token))
    client.post("/api/auth/logout")
    login(client, "bob")

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["user"]["favorites_count"] == 0
    assert response.json()["user"]["history_count"] == 0


def test_admin_dashboard_includes_global_admin_metrics(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("admin", is_admin=True)
    create_user("alice")
    login(client, "admin")
    client.post(
        "/api/auth/register",
        json={"username": "pending", "password": VALID_PASSWORD},
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    admin = response.json()["admin"]
    assert admin["users_count"] >= 3
    assert admin["pending_users_count"] == 1
    assert admin["server"]["status"] == "ok"
    assert admin["server"]["mode"] == "web"
