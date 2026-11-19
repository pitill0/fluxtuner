"""Internal momentum ranking uses only anonymous daily station counts."""

from datetime import date, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.core.trending import seven_day_station_trends


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "trends.db"
    db.init_db(path)
    with db.connect(path) as conn:
        yield conn


def _add_plays(conn, name: str, day: date, plays: int) -> None:
    station_id = db.upsert_station(
        conn, {"name": name, "url": f"https://stream.example/{name.lower()}"}
    )
    conn.execute(
        """
        INSERT INTO station_daily_plays (station_id, day_utc, play_count)
        VALUES (?, ?, ?)
        ON CONFLICT(station_id, day_utc) DO UPDATE SET
            play_count = excluded.play_count
        """,
        (station_id, day.isoformat(), plays),
    )


def test_trends_compare_equal_seven_day_windows_and_ignore_other_dates(database) -> None:
    today = date(2026, 11, 19)
    _add_plays(database, "Rising", today, 7)
    _add_plays(database, "Rising", today - timedelta(days=6), 4)
    _add_plays(database, "Rising", today - timedelta(days=7), 2)
    _add_plays(database, "Rising", today - timedelta(days=13), 3)
    _add_plays(database, "Rising", today - timedelta(days=14), 100)
    _add_plays(database, "Rising", today + timedelta(days=1), 100)

    assert seven_day_station_trends(database, as_of=today) == [
        {
            "station_id": database.execute(
                "SELECT id FROM stations WHERE name = 'Rising'"
            ).fetchone()[0],
            "name": "Rising",
            "recent_plays": 11,
            "previous_plays": 5,
            "growth": 6,
        }
    ]


def test_trends_rank_growth_then_volume_then_name_and_exclude_declines(database) -> None:
    today = date(2026, 11, 19)
    for name, recent, previous in (
        ("Zed", 9, 4),
        ("alpha", 9, 4),
        ("Big", 30, 24),
        ("New", 5, 0),
        ("Flat", 3, 3),
        ("Down", 1, 8),
    ):
        _add_plays(database, name, today, recent)
        if previous:
            _add_plays(database, name, today - timedelta(days=7), previous)

    trends = seven_day_station_trends(database, as_of=today)
    assert [item["name"] for item in trends] == ["Big", "alpha", "Zed", "New"]
    assert [item["growth"] for item in trends] == [6, 5, 5, 5]
    assert [item["name"] for item in seven_day_station_trends(database, as_of=today, limit=2)] == [
        "Big",
        "alpha",
    ]


def test_trends_empty_and_zero_limit(database) -> None:
    assert seven_day_station_trends(database, as_of=date(2026, 11, 19)) == []
    assert seven_day_station_trends(database, limit=0) == []
    with pytest.raises(ValueError, match="limit"):
        seven_day_station_trends(database, limit=True)
    with pytest.raises(TypeError, match="as_of"):
        seven_day_station_trends(database, as_of="2026-11-19")
