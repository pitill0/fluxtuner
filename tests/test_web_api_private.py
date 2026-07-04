# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.app import CSRF_ERROR_DETAIL, create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

VALID_PASSWORD = "correct horse battery staple"


PRIVATE_ENDPOINTS = [
    ("get", "/api/search?q=rock"),
    ("get", "/api/history"),
    ("post", "/api/history"),
    ("get", "/api/favorites"),
    ("post", "/api/favorites"),
    ("delete", "/api/favorites?url=https%3A%2F%2Fexample.com%2Fa"),
    ("get", "/api/playlists"),
    ("post", "/api/playlists"),
    ("delete", "/api/playlists/Morning"),
    ("get", "/api/playlists/Morning/stations"),
    ("post", "/api/playlists/Morning/stations"),
    ("delete", "/api/playlists/Morning/stations?url=https%3A%2F%2Fexample.com%2Fa"),
]


def make_client(tmp_path, monkeypatch) -> TestClient:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    return TestClient(create_app())


def create_user(username: str, password: str = VALID_PASSWORD) -> int:
    password_hash = auth.hash_password(password)
    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            username,
            password_hash=password_hash,
        )
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
    }


def test_private_data_routes_require_authentication(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    for method, url in PRIVATE_ENDPOINTS:
        body = {"name": "Morning"}
        if url.endswith("/history") or url.endswith("/favorites") or url.endswith("/stations"):
            body = station_payload("Station", "https://example.com/a")

        response = client.request(method.upper(), url, json=body)

        assert response.status_code == 401, f"{method.upper()} {url}"


def test_authenticated_user_can_read_and_write_private_data(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    station = station_payload("Alice Radio", "https://example.com/alice")

    assert (
        client.post("/api/history", json=station, headers=csrf_headers(csrf_token)).status_code
        == 200
    )
    history = client.get("/api/history").json()
    assert history["count"] == 1
    assert history["stations"][0]["name"] == "Alice Radio"

    favorite_response = client.post(
        "/api/favorites", json=station, headers=csrf_headers(csrf_token)
    )
    assert favorite_response.status_code == 200
    favorites = client.get("/api/favorites").json()
    assert favorites["count"] == 1
    assert favorites["stations"][0]["name"] == "Alice Radio"

    playlist_response = client.post(
        "/api/playlists", json={"name": "Morning"}, headers=csrf_headers(csrf_token)
    )
    assert playlist_response.status_code == 200
    add_response = client.post(
        "/api/playlists/Morning/stations", json=station, headers=csrf_headers(csrf_token)
    )
    assert add_response.status_code == 200

    playlists = client.get("/api/playlists").json()
    assert playlists["count"] == 1
    assert playlists["playlists"][0] == {"name": "Morning", "count": 1}

    stations = client.get("/api/playlists/Morning/stations").json()
    assert stations["count"] == 1
    assert stations["stations"][0]["name"] == "Alice Radio"


def test_private_mutations_require_valid_csrf_token(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")

    response = client.post(
        "/api/favorites",
        json=station_payload("Station", "https://example.com/a"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_ERROR_DETAIL}

    response = client.delete(
        "/api/favorites?url=https%3A%2F%2Fexample.com%2Fa",
        headers={CSRF_HEADER_NAME: "invalid"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_ERROR_DETAIL}


def test_private_data_is_isolated_between_authenticated_users(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    create_user("bob")

    csrf_token = login(client, "alice")
    station = station_payload("Alice Radio", "https://example.com/alice")

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
            "/api/playlists", json={"name": "Morning"}, headers=csrf_headers(csrf_token)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/playlists/Morning/stations", json=station, headers=csrf_headers(csrf_token)
        ).status_code
        == 200
    )

    assert client.post("/api/auth/logout", headers=csrf_headers(csrf_token)).status_code == 200
    csrf_token = login(client, "bob")

    assert client.get("/api/history").json() == {"count": 0, "stations": []}
    assert client.get("/api/favorites").json() == {"count": 0, "stations": []}
    assert client.get("/api/playlists").json() == {"count": 0, "playlists": []}
    assert client.get("/api/playlists/Morning/stations").json() == {
        "name": "Morning",
        "count": 0,
        "stations": [],
    }


def test_authenticated_user_can_delete_favorite_by_url(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    station = station_payload("Alice Radio", "https://example.com/alice?ref=smoke")
    add_response = client.post(
        "/api/favorites",
        json=station,
        headers=csrf_headers(csrf_token),
    )
    assert add_response.status_code == 200

    delete_response = client.delete(
        "/api/favorites?url=https%3A%2F%2Fexample.com%2Falice%3Fref%3Dsmoke",
        headers=csrf_headers(csrf_token),
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["removed"] is True
    assert client.get("/api/favorites").json()["count"] == 0


def test_private_station_mutations_reject_unsupported_stream_urls(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")
    headers = csrf_headers(csrf_token)

    bad_station = station_payload("Bad Radio", "javascript:alert(1)")

    history_response = client.post("/api/history", json=bad_station, headers=headers)
    favorite_response = client.post("/api/favorites", json=bad_station, headers=headers)

    client.post("/api/playlists", json={"name": "Morning"}, headers=headers)
    playlist_response = client.post(
        "/api/playlists/Morning/stations",
        json=bad_station,
        headers=headers,
    )

    assert history_response.status_code == 400
    assert favorite_response.status_code == 400
    assert playlist_response.status_code == 400
    assert history_response.json()["detail"] == "Station URL must be a valid HTTP or HTTPS URL."


def test_private_station_mutations_accept_resolved_http_stream_url(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    station = {
        "name": "Resolved Radio",
        "url": "",
        "url_resolved": "https://example.com/resolved",
    }

    response = client.post("/api/history", json=station, headers=csrf_headers(csrf_token))

    assert response.status_code == 200


def test_authenticated_user_can_search_stations(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")

    def fake_search_stations_filtered(**_kwargs):
        return [
            {
                "name": "Alice Radio",
                "url": "https://example.com/alice",
                "country": "Spain",
                "codec": "MP3",
                "bitrate": 128,
            }
        ]

    monkeypatch.setattr(
        "fluxtuner.web.library.search_stations_filtered",
        fake_search_stations_filtered,
    )

    response = client.get("/api/search?q=alice")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "alice"
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Alice Radio"


def test_authenticated_user_can_search_by_min_bitrate_only(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")
    seen: dict[str, object] = {}

    def fake_search_stations_filtered(**kwargs):
        seen.update(kwargs)
        return [
            {
                "name": "High Bitrate Radio",
                "url": "https://example.com/high",
                "bitrate": 320,
            }
        ]

    monkeypatch.setattr(
        "fluxtuner.web.library.search_stations_filtered",
        fake_search_stations_filtered,
    )

    response = client.get("/api/search?min_bitrate=256")

    assert response.status_code == 200
    assert seen == {"query": "", "country": None, "min_bitrate": 256, "limit": 25}
    payload = response.json()
    assert payload["query"] == ""
    assert payload["country"] == ""
    assert payload["min_bitrate"] == 256
    assert payload["stations"][0]["name"] == "High Bitrate Radio"


def test_authenticated_user_can_request_up_to_100_search_results(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")
    seen: dict[str, object] = {}

    def fake_search_stations_filtered(**kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(
        "fluxtuner.web.library.search_stations_filtered",
        fake_search_stations_filtered,
    )

    response = client.get("/api/search?q=alice&limit=100")

    assert response.status_code == 200
    assert seen["limit"] == 100
    assert response.json()["limit"] == 100


def test_search_rejects_oversized_limit(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")

    response = client.get("/api/search?q=alice&limit=101")

    assert response.status_code == 422


def test_authenticated_user_can_request_search_debug_metadata(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    login(client, "alice")

    def fake_search_stations_filtered_debug(**_kwargs):
        return (
            [
                {
                    "name": "Rock Tag",
                    "url": "https://example.com/rock-tag",
                    "tags": "rock",
                }
            ],
            {
                "query": "rock",
                "name_results": 0,
                "tag_results": 1,
                "returned_results": 1,
            },
        )

    monkeypatch.setattr(
        "fluxtuner.web.library.search_stations_filtered_debug",
        fake_search_stations_filtered_debug,
    )

    response = client.get("/api/search?q=rock&debug=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Rock Tag"
    assert payload["debug"] == {
        "query": "rock",
        "name_results": 0,
        "tag_results": 1,
        "returned_results": 1,
    }


def test_web_playlist_create_rejects_oversized_name(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    response = client.post(
        "/api/playlists",
        json={"name": "x" * 121},
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "One or more fields exceed the maximum allowed length."


def test_web_playlist_path_rejects_oversized_name(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    csrf_token = login(client, "alice")

    response = client.post(
        f"/api/playlists/{'x' * 121}/stations",
        json=station_payload("Alice Radio", "https://example.com/alice"),
        headers=csrf_headers(csrf_token),
    )

    assert response.status_code == 422
