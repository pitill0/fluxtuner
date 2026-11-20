"""Public featured station must not expose private station or stream identities."""

from datetime import date

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.public_featured import public_featured_station
from fluxtuner.core.public_station_visibility import set_station_publication
from fluxtuner.web.app import create_app


def _station(conn, name: str, url: str, uuid: str = "") -> None:
    db.upsert_station(
        conn,
        {"name": name, "url": url, "url_resolved": url, "stationuuid": uuid},
    )


def test_featured_never_publishes_custom_or_secret_urls(tmp_path) -> None:
    path = tmp_path / "featured.db"
    db.init_db(path)
    day = date(2026, 11, 20)
    with db.connect(path) as conn:
        _station(conn, "Private custom", "https://example.test/private")
        _station(conn, "Token", "https://example.test/play?token=secret", "uuid-token")
        _station(conn, "Credentials", "https://user:pass@example.test/play", "uuid-user")
        assert public_featured_station(conn, as_of=day) == {
            "station": None,
            "date_utc": "2026-11-20",
        }
        _station(conn, "Safe directory station", "https://radio.example.test/live", "uuid-safe")
        expected = {"station": {"name": "Safe directory station"}, "date_utc": "2026-11-20"}
        assert public_featured_station(conn, as_of=day) == expected
        assert public_featured_station(conn, as_of=day) == expected


def test_featured_endpoint_returns_only_name_and_date(tmp_path, monkeypatch) -> None:
    path = tmp_path / "featured.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)
    with db.connect(path) as conn:
        _station(conn, "Public catalog", "https://radio.example.test/live", "uuid-safe")
        conn.commit()
    response = TestClient(create_app()).get("/api/public/featured")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["station"] == {"name": "Public catalog"}
    assert "radio.example" not in response.text
    assert "uuid-safe" not in response.text
    assert "station_id" not in response.text


def test_custom_station_requires_live_owner_opt_in(tmp_path) -> None:
    path = tmp_path / "featured-consent.db"
    db.init_db(path)
    day = date(2026, 11, 20)
    empty = {"station": None, "date_utc": day.isoformat()}
    with db.connect(path) as conn:
        now = db.utc_now()
        cursor = conn.execute(
            """
            INSERT INTO users
                (username, password_hash, is_active, approval_status, created_at, updated_at)
            VALUES ('featured-owner', 'test-hash', 1, 'approved', ?, ?)
            """,
            (now, now),
        )
        user_id = int(cursor.lastrowid)
        profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
        station_id = db.upsert_station(
            conn, {"name": "Opted-in custom", "url": "https://radio.example.test/custom"}
        )
        conn.execute(
            """
            INSERT INTO favorites (profile_id, station_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (profile_id, station_id, now, now),
        )
        assert public_featured_station(conn, as_of=day) == empty

        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=True,
        )
        visible = {"station": {"name": "Opted-in custom"}, "date_utc": day.isoformat()}
        assert public_featured_station(conn, as_of=day) == visible
        assert public_featured_station(conn, as_of=day) == visible

        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        assert public_featured_station(conn, as_of=day) == empty
        conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))
        conn.execute("UPDATE users SET approval_status = 'pending' WHERE id = ?", (user_id,))
        assert public_featured_station(conn, as_of=day) == empty
        conn.execute("UPDATE users SET approval_status = 'approved' WHERE id = ?", (user_id,))
        assert public_featured_station(conn, as_of=day) == visible

        conn.execute(
            "UPDATE stations SET url_resolved = ? WHERE id = ?",
            ("https://radio.example.test/custom?token=secret", station_id),
        )
        assert public_featured_station(conn, as_of=day) == empty
        conn.execute("UPDATE stations SET url_resolved = url WHERE id = ?", (station_id,))
        assert public_featured_station(conn, as_of=day) == visible

        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=False,
        )
        assert public_featured_station(conn, as_of=day) == empty
