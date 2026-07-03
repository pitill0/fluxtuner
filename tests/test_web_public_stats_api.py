# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

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


def create_user(username: str) -> int:
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=auth.hash_password(VALID_PASSWORD),
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
    return {
        "name": name,
        "url": url,
        "url_resolved": url,
        "homepage": "https://homepage.example.com",
    }


def test_public_stats_are_available_without_authentication(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/public/stats")

    assert response.status_code == 200
    assert response.json() == {
        "top_stations": [],
        "totals": {
            "plays": 0,
            "favorites": 0,
            "playlists": 0,
            "users": 0,
        },
    }


def test_public_stats_return_only_anonymous_aggregates(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    station = station_payload("Public Radio", "https://stream.example.com/private")
    assert (
        client.post("/api/history", json=station, headers=csrf_headers(csrf_token)).status_code
        == 200
    )
    assert (
        client.post("/api/history", json=station, headers=csrf_headers(csrf_token)).status_code
        == 200
    )
    assert (
        client.post("/api/favorites", json=station, headers=csrf_headers(csrf_token)).status_code
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

    response = client.get("/api/public/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_stations"] == [{"name": "Public Radio", "play_count": 2}]
    assert payload["totals"] == {
        "plays": 2,
        "favorites": 1,
        "playlists": 1,
        "users": 1,
    }

    serialized = str(payload)
    assert "stream.example.com" not in serialized
    assert "homepage.example.com" not in serialized
    assert "url" not in serialized.lower()


def test_public_stats_limit_top_stations_to_three(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    for index in range(4):
        station = station_payload(f"Radio {index}", f"https://stream.example.com/{index}")
        for _ in range(index + 1):
            assert (
                client.post(
                    "/api/history",
                    json=station,
                    headers=csrf_headers(csrf_token),
                ).status_code
                == 200
            )

    response = client.get("/api/public/stats")

    assert response.status_code == 200
    payload = response.json()
    assert [station["name"] for station in payload["top_stations"]] == [
        "Radio 3",
        "Radio 2",
        "Radio 1",
    ]
    assert payload["totals"]["plays"] == 10
    assert payload["totals"]["users"] == 1


def test_public_stats_count_only_active_approved_users(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")

    with db.connect() as conn:
        db.create_pending_user(
            conn,
            "pending",
            password_hash=auth.hash_password(VALID_PASSWORD),
        )
        disabled_id = db.get_or_create_user(
            conn,
            "disabled",
            password_hash=auth.hash_password(VALID_PASSWORD),
        )
        db.set_user_approval_status(conn, disabled_id, db.APPROVAL_DISABLED)
        db.get_or_create_user(conn, "legacy-no-password")
        conn.commit()

    response = client.get("/api/public/stats")

    assert response.status_code == 200
    assert response.json()["totals"]["users"] == 1
