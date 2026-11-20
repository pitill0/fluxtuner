"""Owner-scoped portable favorites downloads."""

import pytest

from fluxtuner.core import db
from fluxtuner.core.m3u_import import parse_m3u, parse_pls


@pytest.mark.parametrize(("format_name", "parser"), [("m3u", parse_m3u), ("pls", parse_pls)])
def test_favorites_download_requires_login_and_is_profile_scoped(web_library, format_name, parser):
    client, users = web_library
    endpoint = f"/api/favorites/export/{format_name}"
    assert client.get(endpoint).status_code == 401
    with db.connect() as conn:
        db.add_favorite_record(
            conn,
            {"name": "Owned radio", "url": "https://radio.example/live"},
            profile_id=users["alice"][1],
        )
        conn.commit()
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    response = client.get(endpoint)
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="fluxtuner-favorites.{format_name}"'
    )
    entries = parser(response.content).entries
    assert [(entry.name, entry.url) for entry in entries] == [
        ("Owned radio", "https://radio.example/live")
    ]
    assert client.get(endpoint, params={"profile": "NotFound"}).status_code == 404

    client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "correct horse battery staple"},
    )
    assert client.get(endpoint).status_code == 404


def test_individual_station_download_is_private(web_library):
    client, users = web_library
    with db.connect() as conn:
        station_id = db.upsert_station(
            conn, {"name": "One station", "url": "https://radio.example/one"}
        )
        db.add_favorite_record(
            conn,
            {"name": "One station", "url": "https://radio.example/one"},
            profile_id=users["alice"][1],
        )
        conn.commit()
    endpoint = f"/api/favorites/stations/{station_id}/export/m3u"
    assert client.get(endpoint).status_code == 401
    client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    response = client.get(endpoint)
    assert response.status_code == 200
    assert [entry.name for entry in parse_m3u(response.content).entries] == ["One station"]
    assert response.headers["content-disposition"] == (
        'attachment; filename="fluxtuner-station.m3u"'
    )
    client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "correct horse battery staple"},
    )
    assert client.get(endpoint).status_code == 404
    assert client.get("/api/favorites/stations/999999/export/m3u").status_code == 404
