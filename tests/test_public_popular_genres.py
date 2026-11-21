"""Public genres use only recognized station tags and anonymous daily counts."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.public_genres import public_popular_genres
from fluxtuner.web.app import create_app


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "genres.db"
    db.init_db(path)
    with db.connect(path) as conn:
        yield conn


def _plays(conn, *, index: int, tags: str, day: date, count: int) -> None:
    station_id = db.upsert_station(
        conn,
        {
            "name": f"Private Station {index}",
            "url": f"https://secret.example/{index}",
            "tags": tags,
        },
    )
    conn.execute(
        """
        INSERT INTO station_daily_plays (station_id, day_utc, play_count)
        VALUES (?, ?, ?)
        ON CONFLICT(station_id, day_utc) DO UPDATE SET play_count = excluded.play_count
        """,
        (station_id, day.isoformat(), count),
    )


def test_genres_normalize_aliases_and_never_expose_station_details(database):
    end = date(2026, 11, 20)
    for index, tags in enumerate(("Rock, ROCK, personal-name", "rock", "RoCk"), start=1):
        for offset in (0, 1, 2):
            _plays(database, index=index, tags=tags, day=end - timedelta(days=offset), count=3)
    result = public_popular_genres(database, as_of=end)
    assert result == {"genres": [{"name": "Rock"}], "period_end_utc": "2026-11-20"}
    assert "secret" not in str(result)
    assert "personal-name" not in str(result)
    assert "27" not in str(result)


def test_genres_suppress_sparse_or_single_station_activity(database):
    end = date(2026, 11, 20)
    for offset in (0, 1, 2):
        _plays(database, index=1, tags="Jazz", day=end - timedelta(days=offset), count=100)
    for index in (2, 3, 4):
        _plays(database, index=index, tags="Pop", day=end, count=20)
    assert public_popular_genres(database, as_of=end)["genres"] == []


def test_genres_ignore_current_and_old_days_and_break_ties_by_name(database):
    end = date(2026, 11, 20)
    for index in (1, 2, 3):
        for offset in (0, 2, 6):
            _plays(
                database, index=index, tags="Soul, Jazz", day=end - timedelta(days=offset), count=3
            )
        _plays(database, index=index, tags="Soul, Jazz", day=end + timedelta(days=1), count=500)
        _plays(database, index=index, tags="Soul, Jazz", day=end - timedelta(days=7), count=500)
    assert public_popular_genres(database, as_of=end)["genres"] == [
        {"name": "Jazz"},
        {"name": "Soul"},
    ]


def test_genres_reject_invalid_date(database):
    with pytest.raises(TypeError):
        public_popular_genres(database, as_of="2026-11-20")


def test_public_genres_limit_to_five_names(database):
    end = date(2026, 11, 20)
    for index in (1, 2, 3):
        for offset in (0, 1, 2):
            _plays(
                database,
                index=index,
                tags="Ambient, Blues, Country, Dance, Funk, House",
                day=end - timedelta(days=offset),
                count=3,
            )
    assert [item["name"] for item in public_popular_genres(database, as_of=end)["genres"]] == [
        "Ambient",
        "Blues",
        "Country",
        "Dance",
        "Funk",
    ]


def test_public_genres_endpoint_is_name_only_and_cacheable(tmp_path, monkeypatch):
    path = tmp_path / "public-genres.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)
    response = TestClient(create_app()).get("/api/public/genres")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.json()["genres"] == []
    assert "period_end_utc" in response.json()
    assert "station_id" not in response.text
    assert "play_count" not in response.text
