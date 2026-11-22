"""Public trending avoids raw counts, URLs, and sparse daily activity."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.public_station_visibility import set_station_publication
from fluxtuner.core.public_trending import public_station_trends
from fluxtuner.web.app import create_app


def _plays(conn, name: str, day, count: int) -> None:
    station_id = db.upsert_station(
        conn,
        {
            "name": name,
            "url": f"https://private.example/{name.lower()}",
            "favicon": "https://private.example/artwork.png",
            "stationuuid": f"public-{name}",
        },
    )
    user_id = db.get_or_create_user(conn, "trend-test-owner", password_hash="test")
    profile_id = db.ensure_default_profile(conn, user_id=user_id)
    db.add_favorite_record(
        conn,
        {"name": name, "url": f"https://private.example/{name.lower()}"},
        profile_id=profile_id,
    )
    set_station_publication(
        conn,
        user_id=user_id,
        profile_id=profile_id,
        station_id=station_id,
        published=True,
    )
    conn.execute(
        """
        INSERT INTO station_daily_plays (station_id, day_utc, play_count)
        VALUES (?, ?, ?)
        """,
        (station_id, day.isoformat(), count),
    )


def test_public_trending_requires_multiple_eligible_stations_and_days(tmp_path) -> None:
    path = tmp_path / "trending.db"
    db.init_db(path)
    final_day = datetime.now(UTC).date() - timedelta(days=1)
    with db.connect(path) as conn:
        for days_ago in (0, 1, 2):
            _plays(conn, "One", final_day - timedelta(days=days_ago), 4)
        assert public_station_trends(conn, as_of=final_day)["stations"] == []

        _plays(conn, "Two", final_day, 12)
        _plays(conn, "Three", final_day, 12)
        assert public_station_trends(conn, as_of=final_day)["stations"] == []

        for name in ("Two", "Three"):
            for days_ago in (1, 2):
                _plays(conn, name, final_day - timedelta(days=days_ago), 1)

        data = public_station_trends(conn, as_of=final_day)
        assert data == {
            "stations": [{"name": "Three"}, {"name": "Two"}, {"name": "One"}],
            "period_end_utc": final_day.isoformat(),
        }


def test_public_trending_api_excludes_today_and_leaks_no_counts_or_urls(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "trending.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)
    final_day = datetime.now(UTC).date() - timedelta(days=1)
    with db.connect(path) as conn:
        for name in ("Alpha", "Beta", "Gamma"):
            for days_ago in (0, 1, 2):
                _plays(conn, name, final_day - timedelta(days=days_ago), 4)
        _plays(conn, "TodayOnly", final_day + timedelta(days=1), 100)
        conn.commit()

    client = TestClient(create_app())
    response = client.get("/api/public/trending")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json() == {
        "stations": [{"name": "Alpha"}, {"name": "Beta"}, {"name": "Gamma"}],
        "period_end_utc": final_day.isoformat(),
    }
    assert "private.example" not in response.text
    assert "play" not in response.text.lower()
    assert "station_id" not in response.text


def test_public_trending_excludes_declining_and_old_activity(tmp_path) -> None:
    path = tmp_path / "trending.db"
    db.init_db(path)
    final_day = datetime.now(UTC).date() - timedelta(days=1)
    with db.connect(path) as conn:
        for name in ("Rising A", "Rising B", "Rising C", "Declining"):
            for days_ago in (0, 1, 2):
                _plays(conn, name, final_day - timedelta(days=days_ago), 4)
        _plays(conn, "Declining", final_day - timedelta(days=7), 20)
        _plays(conn, "Old", final_day - timedelta(days=14), 100)
        names = [item["name"] for item in public_station_trends(conn, as_of=final_day)["stations"]]
        assert names == ["Rising A", "Rising B", "Rising C"]


def test_private_trend_requires_active_owner_publication(tmp_path) -> None:
    path = tmp_path / "trending-consent.db"
    db.init_db(path)
    day = datetime.now(UTC).date() - timedelta(days=1)
    with db.connect(path) as conn:
        user_id = db.get_or_create_user(conn, "trend-owner", password_hash="test")
        profile_id = db.ensure_default_profile(conn, user_id=user_id)
        for name in ("Public A", "Public B"):
            for offset in range(3):
                _plays(conn, name, day - timedelta(days=offset), 4)
        station_id = db.upsert_station(
            conn, {"name": "Private Trend", "url": "https://radio.example/private"}
        )
        for offset in range(3):
            conn.execute(
                "INSERT INTO station_daily_plays (station_id, day_utc, play_count) "
                "VALUES (?, ?, ?)",
                (station_id, (day - timedelta(days=offset)).isoformat(), 4),
            )
        db.add_favorite_record(
            conn,
            {"name": "Private Trend", "url": "https://radio.example/private"},
            profile_id=profile_id,
        )
        assert public_station_trends(conn, as_of=day)["stations"] == []
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=True,
        )
        assert len(public_station_trends(conn, as_of=day)["stations"]) == 3
        set_station_publication(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            station_id=station_id,
            published=False,
        )
        assert public_station_trends(conn, as_of=day)["stations"] == []
