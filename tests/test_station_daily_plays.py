"""Anonymous daily play aggregates never retain profile or user identifiers."""

from datetime import UTC, datetime, timedelta

from fluxtuner.core import db, history


def test_daily_plays_count_recordings_without_user_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    now = datetime.now(UTC)
    station = {"name": "Daily Radio", "url": "https://radio.example/daily"}

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "daily-alice")
        alice = db.ensure_default_profile(conn, user_id=user_id)
        other_id = db.get_or_create_user(conn, "daily-bob")
        bob = db.ensure_default_profile(conn, user_id=other_id)
        for profile_id in (alice, bob):
            history.add_history_record(
                conn, station, profile_id=profile_id, played_at=now.isoformat()
            )
        rows = conn.execute("SELECT * FROM station_daily_plays").fetchall()
        assert len(rows) == 1
        assert rows[0]["day_utc"] == now.date().isoformat()
        assert rows[0]["play_count"] == 2
        assert set(rows[0].keys()) == {"station_id", "day_utc", "play_count"}

        history.replace_history(conn, [{**station, "play_count": 90}], profile_id=alice)
        assert conn.execute("SELECT play_count FROM station_daily_plays").fetchone()[0] == 2


def test_daily_plays_use_utc_and_prune_expired_days(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    today = datetime.now(UTC)
    station = {"name": "Timezone Radio", "url": "https://radio.example/timezone"}
    with db.connect() as conn:
        history.add_history_record(conn, station, played_at=today.isoformat())
        row = conn.execute("SELECT station_id FROM station_daily_plays LIMIT 1").fetchone()
        assert row is not None
        conn.execute(
            "INSERT OR REPLACE INTO station_daily_plays VALUES (?, ?, 4)",
            (row["station_id"], (today - timedelta(days=80)).date().isoformat()),
        )
        history.add_history_record(conn, station, played_at=today.isoformat())
        rows = conn.execute("SELECT day_utc, play_count FROM station_daily_plays").fetchall()
        assert [(r["day_utc"], r["play_count"]) for r in rows] == [(today.date().isoformat(), 2)]


def test_migration_from_v6_creates_empty_daily_aggregate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    station = {"name": "Legacy Radio", "url": "https://radio.example/legacy"}
    with db.connect() as conn:
        history.add_history_record(conn, station)
        conn.execute("DROP TABLE station_daily_plays")
        conn.execute("PRAGMA user_version = 6")
        conn.commit()

    db.init_db()
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM station_daily_plays").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM history_entries").fetchone()[0] == 1
