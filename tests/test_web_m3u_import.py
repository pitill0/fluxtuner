from __future__ import annotations

import socket

import pytest
from test_web_custom_stations import login

from fluxtuner.core import db, favorites
from fluxtuner.core.m3u_import import MAX_FILE_BYTES
from fluxtuner.core.profiles import get_or_create_profile
from fluxtuner.web import m3u_import as service

pytest_plugins = ["test_web_custom_stations"]

PREVIEW = "/api/stations/import/preview"
IMPORT = "/api/stations/import?playlist=Imported"
DATA = (
    "#EXTM3U\n"
    "#EXTINF:-1,Rádio personal\nhttps://radio.example/live\n"
    "#EXTINF:-1,Duplicate\nhttps://radio.example/live\n"
    "#EXTINF:-1,Other\nhttps://other.example/live\n"
    "file:///tmp/audio.mp3\n"
).encode()


def upload(client, endpoint, *, headers=None, data=DATA):
    return client.post(
        endpoint,
        content=data,
        headers={"Content-Type": "application/octet-stream", **(headers or {})},
    )


def counts():
    with db.connect() as conn:
        return tuple(
            conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("stations", "favorites", "playlists", "playlist_stations")
        )


@pytest.mark.parametrize("endpoint", [PREVIEW, IMPORT])
def test_import_requires_authentication(web_library, endpoint):
    client, _ = web_library
    before = counts()
    assert upload(client, endpoint).status_code == 401
    assert counts() == before


@pytest.mark.parametrize("endpoint", [PREVIEW, IMPORT])
def test_import_requires_csrf(web_library, endpoint):
    client, _ = web_library
    login(client)
    before = counts()
    assert upload(client, endpoint).status_code == 403
    assert counts() == before


def test_preview_is_read_only_and_reports_duplicates_and_issues(web_library):
    client, _ = web_library
    headers = login(client)
    before = counts()
    response = upload(client, PREVIEW, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert [entry["name"] for entry in payload["entries"]] == ["Rádio personal", "Other"]
    assert all(entry["existing"] is False for entry in payload["entries"])
    assert payload["duplicates"] == 1
    assert len(payload["issues"]) == 1
    assert payload["playlists"] == []
    assert counts() == before


def test_import_and_repeat_preserve_existing_favorite(web_library):
    client, users = web_library
    headers = login(client)
    response = upload(client, IMPORT, headers=headers)
    assert response.status_code == 200
    assert response.json()["added_favorites"] == 2
    assert response.json()["added_to_playlist"] == 2
    assert favorites.load_favorites(profile_id=users["bob"][1]) == []

    with db.connect() as conn:
        favorites.update_favorite_record(
            conn,
            "https://radio.example/live",
            custom_name="Keep my name",
            favorite_tags=["Keep"],
            profile_id=users["alice"][1],
        )
        conn.commit()
        before_stations = [tuple(row) for row in conn.execute("SELECT * FROM stations ORDER BY id")]
    preview = upload(client, PREVIEW, headers=headers).json()
    assert all(entry["existing"] for entry in preview["entries"])
    assert preview["playlists"] == ["Imported"]

    response = upload(client, IMPORT + "&existing=true", headers=headers)
    assert response.status_code == 200
    assert response.json()["added_favorites"] == 0
    assert response.json()["added_to_playlist"] == 0
    assert response.json()["already_in_playlist"] == 2
    saved = favorites.load_favorites(profile_id=users["alice"][1])
    station = next(s for s in saved if s["url_resolved"] == "https://radio.example/live")
    assert station["custom_name"] == "Keep my name"
    assert station["favorite_tags"] == ["Keep"]
    with db.connect() as conn:
        assert [
            tuple(row) for row in conn.execute("SELECT * FROM stations ORDER BY id")
        ] == before_stations


def test_new_destination_collision_does_not_modify_library(web_library):
    client, _ = web_library
    headers = login(client)
    assert upload(client, IMPORT, headers=headers).status_code == 200
    before = counts()
    response = upload(client, IMPORT.replace("Imported", "IMPORTED"), headers=headers)
    assert response.status_code == 409
    assert counts() == before


def test_missing_existing_destination_is_not_created(web_library):
    client, _ = web_library
    headers = login(client)
    before = counts()
    assert upload(client, IMPORT + "&existing=true", headers=headers).status_code == 404
    assert counts() == before


@pytest.mark.parametrize("endpoint", [PREVIEW, IMPORT])
def test_foreign_profile_is_unavailable(web_library, endpoint):
    client, users = web_library
    with db.connect() as conn:
        get_or_create_profile(conn, "Bob only", user_id=users["bob"][0])
        conn.commit()
    headers = login(client)
    before = counts()
    separator = "&" if "?" in endpoint else "?"
    response = upload(client, endpoint + separator + "profile=Bob%20only", headers=headers)
    assert response.status_code == 404
    assert counts() == before


def test_explicit_profile_is_owned_by_authenticated_user(web_library):
    client, users = web_library
    with db.connect() as conn:
        alice_work = get_or_create_profile(conn, "Work", user_id=users["alice"][0])
        bob_work = get_or_create_profile(conn, "Work", user_id=users["bob"][0])
        conn.commit()
    response = upload(client, IMPORT + "&profile=Work", headers=login(client))
    assert response.status_code == 200
    assert len(favorites.load_favorites(profile_id=alice_work)) == 2
    assert favorites.load_favorites(profile_id=bob_work) == []
    assert favorites.load_favorites(profile_id=users["alice"][1]) == []


@pytest.mark.parametrize(
    "data",
    [b"", b"\xff", b"#EXTM3U\n#EXT-X-TARGETDURATION:10\nsegment.ts\n"],
)
@pytest.mark.parametrize("endpoint", [PREVIEW, IMPORT])
def test_invalid_file_cannot_write(web_library, endpoint, data):
    client, _ = web_library
    headers = login(client)
    before = counts()
    assert upload(client, endpoint, headers=headers, data=data).status_code == 400
    assert counts() == before


@pytest.mark.parametrize("endpoint", [PREVIEW, IMPORT])
def test_oversized_file_is_rejected(web_library, endpoint):
    client, _ = web_library
    headers = login(client)
    before = counts()
    response = upload(client, endpoint, headers=headers, data=b"x" * (MAX_FILE_BYTES + 1))
    assert response.status_code == 413
    assert counts() == before


def test_import_does_not_contact_streams(web_library, monkeypatch):
    client, _ = web_library
    headers = login(client)

    def unexpected_network(*args, **kwargs):
        pytest.fail("Import must not contact any station URL")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    assert upload(client, PREVIEW, headers=headers).status_code == 200
    assert upload(client, IMPORT, headers=headers).status_code == 200


def test_failed_import_rolls_back_destination_and_favorites(web_library, monkeypatch):
    client, _ = web_library
    headers = login(client)
    before = counts()
    original = service.import_m3u

    def fail_after_import(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("Simulated import failure")

    monkeypatch.setattr(service, "import_m3u", fail_after_import)
    response = upload(client, IMPORT, headers=headers)
    assert response.status_code == 400
    assert counts() == before
