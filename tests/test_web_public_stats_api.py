# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.core.public_station_visibility import set_station_publication
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.routes import public as public_routes
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


def mark_catalog_stations() -> None:
    """The public ranking tests must use genuine catalog-eligible stations."""
    with db.connect() as conn:
        conn.execute("UPDATE stations SET stationuuid = 'catalog-' || id")
        conn.commit()


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

    mark_catalog_stations()

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

    mark_catalog_stations()

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


def test_public_top_artwork_is_cached_only_and_scoped(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")
    fetched: list[str] = []

    class StubCache:
        def get(self, url: str) -> tuple[bytes, str] | None:
            fetched.append(url)
            if url == "https://art.example.com/top.jpg":
                return b"cached-image", "image/jpeg"
            return None

    monkeypatch.setattr(public_routes, "ArtworkCache", StubCache)
    for index in range(4):
        station = station_payload(f"Radio {index}", f"https://stream.example.com/{index}")
        station["favicon"] = f"https://art.example.com/{'top' if index == 3 else index}.jpg"
        for _ in range(index + 1):
            assert (
                client.post(
                    "/api/history", json=station, headers=csrf_headers(csrf_token)
                ).status_code
                == 200
            )

    mark_catalog_stations()

    payload = client.get("/api/public/stats").json()
    assert len(payload["top_stations"]) == 3
    assert all("artwork_url" in item for item in payload["top_stations"])
    assert "art.example.com" not in str(payload)

    top_url = payload["top_stations"][0]["artwork_url"]
    image = client.get(top_url)
    assert image.status_code == 200
    assert image.content == b"cached-image"
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "no-store"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert fetched == ["https://art.example.com/top.jpg"]

    missing = client.get(payload["top_stations"][1]["artwork_url"])
    assert missing.status_code == 404
    assert client.get("/api/public/stations/99999/artwork").status_code == 404
    assert client.get("/api/public/stations/-1/artwork").status_code == 404
    assert len(fetched) == 2


def test_public_artwork_does_not_publish_stations_outside_top_three(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")
    for index in range(4):
        station = station_payload(f"Radio {index}", f"https://stream.example.com/{index}")
        station["favicon"] = f"https://art.example.com/{index}.jpg"
        for _ in range(index + 1):
            assert (
                client.post(
                    "/api/history", json=station, headers=csrf_headers(csrf_token)
                ).status_code
                == 200
            )
    mark_catalog_stations()
    with db.connect() as conn:
        excluded_id = conn.execute("SELECT id FROM stations WHERE name = 'Radio 0'").fetchone()[
            "id"
        ]

    class ForbiddenCache:
        def get(self, url: str) -> None:
            raise AssertionError(f"Must not fetch non-public artwork: {url}")

    monkeypatch.setattr(public_routes, "ArtworkCache", ForbiddenCache)
    assert client.get(f"/api/public/stations/{excluded_id}/artwork").status_code == 404


def test_private_top_is_hidden_until_publication_and_revoked_immediately(
    tmp_path, monkeypatch
) -> None:
    client = make_client(tmp_path, monkeypatch)
    user_id = create_user("alice")
    token = login(client, "alice")
    station = station_payload("Private Journal Radio", "https://stream.example.com/private")
    station["favicon"] = "https://art.example.com/private.jpg"
    assert client.post("/api/history", json=station, headers=csrf_headers(token)).status_code == 200
    assert (
        client.post("/api/favorites", json=station, headers=csrf_headers(token)).status_code == 200
    )
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM stations WHERE name = ?", (station["name"],)).fetchone()
        assert row is not None
        station_id = int(row["id"])
        profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
        conn.commit()

    assert client.get("/api/public/stats").json()["top_stations"] == []
    assert client.get(f"/api/public/stations/{station_id}/artwork").status_code == 404

    with db.connect() as conn:
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=True,
        )
        conn.commit()
    assert client.get("/api/public/stats").json()["top_stations"][0]["name"] == station["name"]

    with db.connect() as conn:
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=False,
        )
        conn.commit()
    assert client.get("/api/public/stats").json()["top_stations"] == []
    assert client.get(f"/api/public/stations/{station_id}/artwork").status_code == 404
