"""Public featured station must not expose private station or stream identities."""

from datetime import date

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.public_featured import public_featured_station
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
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json()["station"] == {"name": "Public catalog"}
    assert "radio.example" not in response.text
    assert "uuid-safe" not in response.text
    assert "station_id" not in response.text
