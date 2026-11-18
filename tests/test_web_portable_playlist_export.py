# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Authenticated portable playlist download integration tests."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core.m3u_import import parse_m3u, parse_pls
from fluxtuner.core.profiles import get_or_create_profile

PASSWORD = "correct horse battery staple"
ENDPOINT = "/api/playlists/Morning/export"


def login(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200


@pytest.fixture
def exported_library(web_library):
    client, users = web_library
    with db.connect() as conn:
        alice_profile = users["alice"][1]
        db.create_playlist_record(conn, "Morning", profile_id=alice_profile)
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "Jazz", "url": "https://radio.example/jazz"},
            profile_id=alice_profile,
        )
        get_or_create_profile(conn, "Work", user_id=users["alice"][0])
        conn.commit()
    return client, users


@pytest.mark.parametrize(
    ("format_name", "parser", "content_type"),
    [
        ("m3u", parse_m3u, "audio/x-mpegurl"),
        ("pls", parse_pls, "audio/x-scpls"),
    ],
)
def test_download_is_compatible_and_private(exported_library, format_name, parser, content_type):
    client, _ = exported_library
    assert client.get(f"{ENDPOINT}/{format_name}").status_code == 401

    login(client, "alice")
    response = client.get(f"{ENDPOINT}/{format_name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert "no-store" in response.headers["cache-control"].lower()
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="fluxtuner-playlist.{format_name}"'
    )

    preview = parser(response.content)
    assert [(entry.name, entry.url) for entry in preview.entries] == [
        ("Jazz", "https://radio.example/jazz")
    ]
    assert not preview.issues


def test_export_is_isolated_between_users_and_profiles(exported_library):
    client, _ = exported_library
    login(client, "alice")

    own = client.get(f"{ENDPOINT}/m3u")
    assert own.status_code == 200

    unknown = client.get(f"{ENDPOINT}/m3u", params={"profile": "Missing"})
    wrong_profile = client.get(f"{ENDPOINT}/m3u", params={"profile": "Work"})
    assert unknown.status_code == 404
    assert wrong_profile.status_code == 404
    assert unknown.json() == wrong_profile.json()

    login(client, "bob")
    foreign = client.get(f"{ENDPOINT}/m3u")
    missing = client.get("/api/playlists/Unknown/export/m3u")
    assert foreign.status_code == 404
    assert missing.status_code == 404
    assert foreign.json() == missing.json()


def test_invalid_format_and_playlist_name_are_rejected(exported_library):
    client, _ = exported_library
    login(client, "alice")

    assert client.get(f"{ENDPOINT}/txt").status_code == 422
    oversized = "x" * 121
    assert client.get(f"/api/playlists/{oversized}/export/m3u").status_code == 422


def test_empty_playlist_has_no_download(exported_library):
    client, users = exported_library
    with db.connect() as conn:
        db.create_playlist_record(
            conn,
            "Empty",
            profile_id=users["alice"][1],
        )
        conn.commit()

    login(client, "alice")
    response = client.get("/api/playlists/Empty/export/m3u")

    assert response.status_code == 400
    assert response.json()["detail"] == "Playlist cannot be exported."
    assert "content-disposition" not in response.headers


def test_invalid_station_cannot_leak_into_download(exported_library, monkeypatch):
    from fluxtuner.core.m3u_import import M3UEntry
    from fluxtuner.web.routes import library as library_routes

    client, _ = exported_library
    login(client, "alice")

    monkeypatch.setattr(
        library_routes,
        "resolve_playlist_entries",
        lambda *args, **kwargs: (M3UEntry("Private station", "javascript:alert(1)"),),
    )

    response = client.get(f"{ENDPOINT}/m3u")

    assert response.status_code == 400
    assert response.json()["detail"] == "Playlist cannot be exported."
    assert "javascript:" not in response.text
    assert "content-disposition" not in response.headers


def test_sqlite_error_has_controlled_response(exported_library, monkeypatch):
    import sqlite3

    from fluxtuner.web.routes import library as library_routes

    client, _ = exported_library
    login(client, "alice")

    def fail_profile_lookup(*args, **kwargs):
        raise sqlite3.OperationalError("private database detail")

    monkeypatch.setattr(library_routes, "_profile_id", fail_profile_lookup)

    response = client.get(f"{ENDPOINT}/pls")

    assert response.status_code == 503
    assert response.json()["detail"] == "Playlist export is unavailable."
    assert "private database detail" not in response.text
    assert "content-disposition" not in response.headers


def test_export_never_creates_profiles(exported_library):
    client, _ = exported_library
    login(client, "alice")

    with db.connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    response = client.get(f"{ENDPOINT}/pls", params={"profile": "NotCreated"})
    assert response.status_code == 404

    with db.connect() as conn:
        after = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    assert before == after
