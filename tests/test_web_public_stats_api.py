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


def _seed_public_listener_diversity(
    conn,
    station_id: int,
    *,
    count: int = 1,
) -> None:
    """Give a published station three independent listeners in test data."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    day = now.date().isoformat()
    for index in range(3):
        user_id = db.get_or_create_user(
            conn,
            f"public-fixture-listener-{index}",
            password_hash="fixture",
        )
        conn.execute(
            """
            INSERT INTO web_public_play_contributions (
                user_id, station_id, day_utc, play_count, last_counted_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, station_id, day_utc) DO UPDATE SET
                play_count = excluded.play_count,
                last_counted_at = excluded.last_counted_at
            """,
            (user_id, station_id, day, min(12, max(1, count)), now.isoformat()),
        )


def mark_catalog_stations() -> None:
    """Publish test stations through an approved owner's favorites."""
    with db.connect() as conn:
        user = conn.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()
        assert user is not None
        user_id = int(user["id"])
        profile_id = db.ensure_default_profile(conn, user_id=user_id)
        stations = conn.execute("SELECT id, name, url FROM stations").fetchall()
        for station in stations:
            now = db.utc_now()
            conn.execute(
                """
                INSERT OR IGNORE INTO favorites (
                    profile_id, station_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (profile_id, int(station["id"]), now, now),
            )
            set_station_publication(
                conn,
                user_id=user_id,
                profile_id=profile_id,
                station_id=int(station["id"]),
                published=True,
            )
            row = conn.execute(
                "SELECT COALESCE(SUM(play_count), 0) AS plays "
                "FROM history_entries WHERE station_id = ?",
                (int(station["id"]),),
            ).fetchone()
            _seed_public_listener_diversity(
                conn,
                int(station["id"]),
                count=int(row["plays"]),
            )
        conn.commit()


def test_untrusted_stationuuid_never_grants_public_visibility(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("bob")
    csrf = login(client, "bob")

    station = {
        "name": "Forged directory station",
        "url": "https://forged.example/live",
        "stationuuid": "invented-directory-id",
    }

    for _ in range(12):
        response = client.post(
            "/api/history",
            json=station,
            headers=csrf_headers(csrf),
        )
        assert response.status_code == 200

    with db.connect() as conn:
        row = conn.execute(
            "SELECT stationuuid FROM stations WHERE station_key = ?",
            (station["url"],),
        ).fetchone()
        assert row is not None
        assert not row["stationuuid"]

    assert client.get("/api/public/stats").json()["top_stations"] == []


def test_other_user_cannot_rewrite_shared_station_metadata(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    create_user("bob")

    alice_csrf = login(client, "alice")
    url = "https://shared.example/live"

    original = {
        "name": "Alice Radio",
        "url": url,
        "favicon": "https://art.example/original.png",
        "tags": "jazz",
    }
    assert (
        client.post(
            "/api/favorites",
            json=original,
            headers=csrf_headers(alice_csrf),
        ).status_code
        == 200
    )

    assert (
        client.post(
            "/api/auth/logout",
            headers=csrf_headers(alice_csrf),
        ).status_code
        == 200
    )

    bob_csrf = login(client, "bob")
    malicious = {
        "name": "Attacker Radio",
        "url": url,
        "favicon": "https://attacker.example/pixel.png",
        "tags": "spam",
        "stationuuid": "fake-id",
    }

    assert (
        client.post(
            "/api/history",
            json=malicious,
            headers=csrf_headers(bob_csrf),
        ).status_code
        == 200
    )

    assert (
        client.post(
            "/api/favorites",
            json=malicious,
            headers=csrf_headers(bob_csrf),
        ).status_code
        == 200
    )

    assert (
        client.post(
            "/api/playlists/Malicious/stations",
            json=malicious,
            headers=csrf_headers(bob_csrf),
        ).status_code
        == 200
    )

    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT name, favicon, tags, stationuuid
            FROM stations WHERE station_key = ?
            """,
            (url,),
        ).fetchone()

    assert row is not None
    assert row["name"] == "Alice Radio"
    assert row["favicon"] == "https://art.example/original.png"
    assert row["tags"] == "jazz"
    assert not row["stationuuid"]


def test_other_user_cannot_publish_private_station_by_forging_uuid(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("alice")
    create_user("bob")

    url = "https://alice.example/private-radio"

    alice_csrf = login(client, "alice")
    station = {
        "name": "Alice Private Radio",
        "url": url,
    }

    assert (
        client.post(
            "/api/favorites",
            json=station,
            headers=csrf_headers(alice_csrf),
        ).status_code
        == 200
    )

    for _ in range(5):
        assert (
            client.post(
                "/api/history",
                json=station,
                headers=csrf_headers(alice_csrf),
            ).status_code
            == 200
        )

    assert client.get("/api/public/stats").json()["top_stations"] == []

    assert (
        client.post(
            "/api/auth/logout",
            headers=csrf_headers(alice_csrf),
        ).status_code
        == 200
    )

    bob_csrf = login(client, "bob")
    assert (
        client.post(
            "/api/history",
            json={
                "name": "Forged public directory station",
                "url": url,
                "stationuuid": "forged",
            },
            headers=csrf_headers(bob_csrf),
        ).status_code
        == 200
    )

    with db.connect() as conn:
        row = conn.execute(
            "SELECT name, stationuuid FROM stations WHERE station_key = ?",
            (url,),
        ).fetchone()

    assert row is not None
    assert row["name"] == "Alice Private Radio"
    assert not row["stationuuid"]

    assert client.get("/api/public/stats").json()["top_stations"] == []


def test_oversized_web_station_metadata_is_rejected(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    create_user("bob")
    csrf = login(client, "bob")

    response = client.post(
        "/api/favorites",
        json={
            "name": "A" * 2_000_000,
            "url": "https://oversized.example/live",
        },
        headers=csrf_headers(csrf),
    )

    assert response.status_code == 422

    with db.connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM stations WHERE station_key = ?",
            ("https://oversized.example/live",),
        ).fetchone()[0]

    assert count == 0


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
    assert payload["top_stations"] == [{"name": "Public Radio", "play_count": 7}]
    assert payload["totals"] == {
        "plays": 7,
        "favorites": 1,
        "playlists": 1,
        "users": 4,
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
    assert payload["totals"]["plays"] == 34
    assert payload["totals"]["users"] == 4


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

    with db.connect() as conn:
        _seed_public_listener_diversity(conn, station_id)
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


def test_public_artwork_preflight_skips_ranking_for_private_or_unsafe_station(
    tmp_path, monkeypatch
) -> None:
    client = make_client(tmp_path, monkeypatch)
    user_id = create_user("alice")
    csrf = login(client, "alice")
    station = station_payload("Preflight Radio", "https://stream.example.com/preflight")
    station["favicon"] = "https://art.example.com/preflight.jpg"

    assert (
        client.post("/api/favorites", json=station, headers=csrf_headers(csrf)).status_code == 200
    )

    with db.connect() as conn:
        row = conn.execute("SELECT id FROM stations WHERE name = ?", (station["name"],)).fetchone()
        assert row is not None
        station_id = int(row["id"])
        profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
        conn.commit()

    ranking_calls = 0

    def counted_ranking(conn):
        nonlocal ranking_calls
        ranking_calls += 1
        return []

    monkeypatch.setattr(public_routes, "public_top_station_rows", counted_ranking)
    url = f"/api/public/stations/{station_id}/artwork"

    # Private stations must fail before the expensive ranking query.
    assert client.get(url).status_code == 404
    assert ranking_calls == 0

    with db.connect() as conn:
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=True,
        )
        conn.commit()

    # Publication is necessary, but not sufficient: Top-3 membership
    # is still checked on every eligible request.
    assert client.get(url).status_code == 404
    assert ranking_calls == 1

    with db.connect() as conn:
        conn.execute(
            "UPDATE stations SET url_resolved = ? WHERE id = ?",
            ("https://stream.example.com/live?token=secret", station_id),
        )
        conn.commit()

    assert client.get(url).status_code == 404
    assert ranking_calls == 1

    with db.connect() as conn:
        conn.execute(
            "UPDATE stations SET url_resolved = url WHERE id = ?",
            (station_id,),
        )
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=False,
        )
        conn.commit()

    # Revocation must take effect without a cache delay.
    assert client.get(url).status_code == 404
    assert ranking_calls == 1


def test_public_stats_cache_reuses_reads_but_invalidates_on_commit(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    original = db.public_activity_stats
    calls = 0

    def counted_stats(conn):
        nonlocal calls
        calls += 1
        return original(conn)

    monkeypatch.setattr(db, "public_activity_stats", counted_stats)

    first = client.get("/api/public/stats")
    second = client.get("/api/public/stats")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert calls == 1
    assert first.headers["cache-control"] == "public, max-age=0, must-revalidate"

    # Commit on another connection must invalidate immediately.
    create_user("cache-invalidation-user")
    third = client.get("/api/public/stats")
    assert third.status_code == 200
    assert calls == 2
    assert third.json()["totals"]["users"] == (first.json()["totals"]["users"] + 1)


def test_public_trending_and_genres_cache_invalidate_after_write(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    original_trending = public_routes.public_station_trends
    original_genres = public_routes.public_popular_genres
    calls = {"trending": 0, "genres": 0}

    def counted_trending(conn):
        calls["trending"] += 1
        return original_trending(conn)

    def counted_genres(conn):
        calls["genres"] += 1
        return original_genres(conn)

    monkeypatch.setattr(public_routes, "public_station_trends", counted_trending)
    monkeypatch.setattr(public_routes, "public_popular_genres", counted_genres)

    for endpoint in ("/api/public/trending", "/api/public/genres"):
        first = client.get(endpoint)
        second = client.get(endpoint)
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert first.headers["cache-control"] == ("public, max-age=0, must-revalidate")

    assert calls == {"trending": 1, "genres": 1}

    create_user("cached-aggregate-user")

    assert client.get("/api/public/trending").status_code == 200
    assert client.get("/api/public/genres").status_code == 200
    assert calls == {"trending": 2, "genres": 2}


def test_public_artwork_reuses_top_ranking_until_database_changes(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    user_id = create_user("artwork-cache-owner")
    csrf = login(client, "artwork-cache-owner")
    station = station_payload("Artwork Cache Radio", "https://radio.example.test/artwork-cache")
    station["favicon"] = "https://art.example.test/cache.jpg"
    assert (
        client.post("/api/favorites", json=station, headers=csrf_headers(csrf)).status_code == 200
    )

    with db.connect() as conn:
        station_id = int(
            conn.execute("SELECT id FROM stations WHERE name = ?", (station["name"],)).fetchone()[
                "id"
            ]
        )
        profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=True,
        )
        conn.commit()

    calls = 0

    def counted_ranking(conn):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(public_routes, "public_top_station_rows", counted_ranking)
    url = f"/api/public/stations/{station_id}/artwork"

    assert client.get(url).status_code == 404
    assert client.get(url).status_code == 404
    assert calls == 1

    create_user("artwork-cache-write")
    assert client.get(url).status_code == 404
    assert calls == 2

    with db.connect() as conn:
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=False,
        )
        conn.commit()

    assert client.get(url).status_code == 404
    assert calls == 2


def test_public_response_cache_has_bounded_entries(tmp_path, monkeypatch) -> None:
    from fluxtuner.web.public_cache import (
        MAX_ENTRIES,
        PublicResponseCache,
    )

    make_client(tmp_path, monkeypatch)
    cache = PublicResponseCache()

    for index in range(MAX_ENTRIES + 12):
        result = cache.get(
            f"test-key-{index}",
            lambda conn: {"value": 1},
        )
        assert result == {"value": 1}

    assert len(cache._entries) == MAX_ENTRIES
