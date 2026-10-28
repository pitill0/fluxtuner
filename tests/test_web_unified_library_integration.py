# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""UX-03 authenticated library integration and isolation."""

from __future__ import annotations

from fluxtuner.core import db
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.profiles import get_or_create_profile
from fluxtuner.core.remote_subscription_store import create_subscription
from fluxtuner.web.security import CSRF_HEADER_NAME

PASSWORD = "correct horse battery staple"
CUSTOM = "/api/stations/custom"
CATALOGS = "/api/stations/subscriptions"


def login(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {CSRF_HEADER_NAME: response.json()["csrf_token"]}


def test_manual_stations_are_owned_and_distinct_from_favorites(web_library):
    client, users = web_library
    headers = login(client, "alice")

    response = client.post(
        CUSTOM,
        json={"name": "My radio", "url": "https://radio.example/manual"},
        headers=headers,
    )
    assert response.status_code == 200

    response = client.post(
        "/api/favorites",
        json={"name": "Saved radio", "url": "https://radio.example/saved"},
        headers=headers,
    )
    assert response.status_code == 200

    listed = client.get(CUSTOM)
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["count"] == 1
    assert [station["name"] for station in payload["stations"]] == ["My radio"]

    assert client.get("/api/favorites").json()["count"] == 2

    login(client, "bob")
    assert client.get(CUSTOM).json() == {"count": 0, "stations": []}

    assert users["alice"][1] != users["bob"][1]


def test_manual_stations_respect_profile_and_favorite_removal(web_library):
    client, users = web_library
    with db.connect() as conn:
        get_or_create_profile(conn, "Work", user_id=users["alice"][0])
        conn.commit()

    headers = login(client, "alice")
    station_url = "https://radio.example/work"

    created = client.post(
        CUSTOM,
        params={"profile": "Work"},
        json={"name": "Work radio", "url": station_url},
        headers=headers,
    )
    assert created.status_code == 200

    assert client.get(CUSTOM).json()["count"] == 0
    work = client.get(CUSTOM, params={"profile": "Work"})
    assert work.status_code == 200
    assert work.json()["count"] == 1

    removed = client.delete(
        "/api/favorites",
        params={"profile": "Work", "url": station_url},
        headers=headers,
    )
    assert removed.status_code == 200

    remaining = client.get(CUSTOM, params={"profile": "Work"})
    assert remaining.status_code == 200
    assert remaining.json()["stations"] == []


def test_catalog_snapshot_is_profile_owned_and_offline(web_library, monkeypatch):
    client, users = web_library

    with db.connect() as conn:
        alice_profile = users["alice"][1]
        bob_profile = users["bob"][1]
        work_profile = get_or_create_profile(conn, "Work", user_id=users["alice"][0])

        source_id = create_subscription(
            conn,
            profile_id=alice_profile,
            catalog_url="https://catalog.example/stations.m3u",
            entries=[M3UEntry("Catalog radio", "https://radio.example/catalog")],
        )
        conn.commit()

    def no_network(*args, **kwargs):
        raise AssertionError("Catalog reading must not use the network.")

    monkeypatch.setattr(
        "fluxtuner.web.routes.subscriptions._download_catalog",
        no_network,
    )

    endpoint = f"{CATALOGS}/{source_id}/stations"

    assert client.get(endpoint).status_code == 401

    login(client, "alice")
    own = client.get(endpoint)
    assert own.status_code == 200
    payload = own.json()
    assert payload["source_id"] == source_id
    assert payload["count"] == 1
    assert payload["stations"][0]["name"] == "Catalog radio"
    assert payload["stations"][0]["url"] == "https://radio.example/catalog"
    assert "catalog_url" not in own.text

    assert client.get(endpoint, params={"profile": "Work"}).status_code == 404

    login(client, "bob")
    assert client.get(endpoint).status_code == 404

    assert len({alice_profile, work_profile, bob_profile}) == 3


def test_unknown_profile_is_not_created_by_read_routes(web_library):
    client, _ = web_library
    login(client, "alice")

    with db.connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    assert client.get(CUSTOM, params={"profile": "Nonexistent"}).status_code == 404

    with db.connect() as conn:
        after = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    assert before == after
