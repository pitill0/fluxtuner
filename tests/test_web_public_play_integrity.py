"""SEC-02/SEC-04: bounded, account-scoped public listening statistics."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db, history
from fluxtuner.core.public_stats import public_activity_stats
from fluxtuner.web import maintenance

STATION = {
    "name": "Integrity Radio",
    "url": "https://stream.example.com/integrity",
}


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    path = history._db_path()
    db.init_db(path)
    return path


def _user(path, name):
    with db.connect(path) as conn:
        user_id = db.get_or_create_user(conn, name, password_hash="fixture")
        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()
    return user_id


def _count(path, user_id=None):
    with db.connect(path) as conn:
        if user_id is None:
            return conn.execute(
                "SELECT COALESCE(SUM(play_count), 0) FROM web_public_play_contributions"
            ).fetchone()[0]
        return conn.execute(
            "SELECT COALESCE(SUM(play_count), 0) "
            "FROM web_public_play_contributions WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]


def _play(user_id, *, profile_name=None):
    history.add_history(
        STATION,
        user_id=user_id,
        profile_name=profile_name,
        count_web_public_play=True,
    )


def test_burst_is_bounded_but_personal_history_remains_intact(database):
    alice = _user(database, "alice")
    for _ in range(40):
        _play(alice)

    assert _count(database, alice) == 1
    with db.connect(database) as conn:
        count = conn.execute(
            "SELECT play_count FROM history_entries AS h "
            "JOIN profiles AS p ON p.id = h.profile_id "
            "WHERE p.user_id = ?",
            (alice,),
        ).fetchone()[0]
    assert count == 40

    # Untrusted Web requests must not inflate legacy CLI/GTK trends.
    with db.connect(database) as conn:
        legacy_count = conn.execute(
            "SELECT COALESCE(SUM(play_count), 0) FROM station_daily_plays"
        ).fetchone()[0]
    assert legacy_count == 0


def test_multiple_profiles_do_not_create_multiple_listeners(database):
    alice = _user(database, "alice")
    with db.connect(database) as conn:
        db.get_or_create_profile(conn, "work", user_id=alice)
        conn.commit()

    _play(alice)
    _play(alice, profile_name="work")

    assert _count(database, alice) == 1
    with db.connect(database) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM web_public_play_contributions"
            ).fetchone()[0]
            == 1
        )
        assert conn.execute("SELECT COUNT(*) FROM history_entries").fetchone()[0] == 2


def test_hourly_limit_and_daily_cap(database, monkeypatch):
    alice = _user(database, "alice")
    start = datetime(2026, 11, 22, 0, 0, tzinfo=UTC)

    class Clock(datetime):
        current = start

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(history, "datetime", Clock)

    for hour in range(14):
        Clock.current = start + timedelta(hours=hour)
        _play(alice)
        _play(alice)

    assert _count(database, alice) == 12

    Clock.current = start + timedelta(days=1)
    _play(alice)
    assert _count(database, alice) == 13


def test_retention_removes_old_user_station_contributions(database, monkeypatch):
    alice = _user(database, "alice")
    start = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

    class Clock(datetime):
        current = start

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(history, "datetime", Clock)

    _play(alice)
    assert _count(database, alice) == 1

    Clock.current = start + timedelta(days=40)
    _play(alice)
    assert _count(database, alice) == 1

    with db.connect(database) as conn:
        rows = conn.execute("SELECT day_utc FROM web_public_play_contributions").fetchall()
    assert len(rows) == 1
    assert rows[0]["day_utc"] == Clock.current.date().isoformat()


def test_concurrent_requests_cannot_inflate_public_count(database):
    alice = _user(database, "alice")

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: _play(alice), range(4)))

    assert results == [None] * 4
    assert _count(database, alice) == 1


def test_public_totals_exclude_disabled_accounts(database):
    alice = _user(database, "alice")
    bob = _user(database, "bob")

    _play(alice)
    _play(bob)

    with db.connect(database) as conn:
        assert public_activity_stats(conn)["totals"]["plays"] == 2
        db.set_user_approval_status(conn, bob, db.APPROVAL_DISABLED)
        conn.commit()
        assert public_activity_stats(conn)["totals"]["plays"] == 1


def test_distinct_station_cap_preserves_personal_history(database):
    alice = _user(database, "alice")

    for index in range(110):
        history.add_history(
            {
                "name": f"Station {index}",
                "url": f"https://stream.example.com/{index}",
            },
            user_id=alice,
            count_web_public_play=True,
        )

    with db.connect(database) as conn:
        public_stations = conn.execute(
            "SELECT COUNT(*) FROM web_public_play_contributions WHERE user_id = ?",
            (alice,),
        ).fetchone()[0]
        personal_stations = conn.execute(
            "SELECT COUNT(*) FROM history_entries AS h "
            "JOIN profiles AS p ON p.id = h.profile_id "
            "WHERE p.user_id = ?",
            (alice,),
        ).fetchone()[0]

    assert public_stations == history.PUBLIC_PLAY_MAX_STATIONS_PER_DAY == 100
    assert personal_stations == 110


def test_periodic_maintenance_purges_old_contributions_without_new_plays(database, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", database)
    alice = _user(database, "alice")
    current = datetime(2026, 11, 22, 12, tzinfo=UTC)

    with db.connect(database) as conn:
        station_id = db.upsert_station(conn, STATION)
        for day in (
            current.date() - timedelta(days=35),
            current.date() - timedelta(days=34),
            current.date(),
        ):
            conn.execute(
                "INSERT INTO web_public_play_contributions "
                "(user_id, station_id, day_utc, play_count, last_counted_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (alice, station_id, day.isoformat(), current.isoformat()),
            )
        conn.commit()

    result = maintenance.run_auth_maintenance(now=current)
    assert result.purged_public_play_contributions == 1

    with db.connect(database) as conn:
        days = [
            row["day_utc"]
            for row in conn.execute(
                "SELECT day_utc FROM web_public_play_contributions ORDER BY day_utc"
            )
        ]

    assert days == [
        (current.date() - timedelta(days=34)).isoformat(),
        current.date().isoformat(),
    ]
