from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.app import create_app

VALID_PASSWORD = "correct horse battery staple"


PRIVATE_ENDPOINTS = [
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


def login(client: TestClient, username: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": VALID_PASSWORD},
    )
    assert response.status_code == 200


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
    login(client, "alice")

    station = station_payload("Alice Radio", "https://example.com/alice")

    assert client.post("/api/history", json=station).status_code == 200
    history = client.get("/api/history").json()
    assert history["count"] == 1
    assert history["stations"][0]["name"] == "Alice Radio"

    favorite_response = client.post("/api/favorites", json=station)
    assert favorite_response.status_code == 200
    favorites = client.get("/api/favorites").json()
    assert favorites["count"] == 1
    assert favorites["stations"][0]["name"] == "Alice Radio"

    playlist_response = client.post("/api/playlists", json={"name": "Morning"})
    assert playlist_response.status_code == 200
    add_response = client.post("/api/playlists/Morning/stations", json=station)
    assert add_response.status_code == 200

    playlists = client.get("/api/playlists").json()
    assert playlists["count"] == 1
    assert playlists["playlists"][0] == {"name": "Morning", "count": 1}

    stations = client.get("/api/playlists/Morning/stations").json()
    assert stations["count"] == 1
    assert stations["stations"][0]["name"] == "Alice Radio"


def test_private_data_is_isolated_between_authenticated_users(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    create_user("bob")

    login(client, "alice")
    station = station_payload("Alice Radio", "https://example.com/alice")

    assert client.post("/api/history", json=station).status_code == 200
    assert client.post("/api/favorites", json=station).status_code == 200
    assert client.post("/api/playlists", json={"name": "Morning"}).status_code == 200
    assert client.post("/api/playlists/Morning/stations", json=station).status_code == 200

    assert client.post("/api/auth/logout").status_code == 200
    login(client, "bob")

    assert client.get("/api/history").json() == {"count": 0, "stations": []}
    assert client.get("/api/favorites").json() == {"count": 0, "stations": []}
    assert client.get("/api/playlists").json() == {"count": 0, "playlists": []}
    assert client.get("/api/playlists/Morning/stations").json() == {
        "name": "Morning",
        "count": 0,
        "stations": [],
    }
