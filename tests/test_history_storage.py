# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, history


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_history_record_adds_station_newest_first(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    first = {
        "name": "First Radio",
        "url": "https://example.com/first",
    }
    second = {
        "name": "Second Radio",
        "url": "https://example.com/second",
    }

    with db.connect() as conn:
        history.add_history_record(
            conn,
            first,
            played_at="2026-01-01T10:00:00+00:00",
        )
        history.add_history_record(
            conn,
            second,
            played_at="2026-01-01T11:00:00+00:00",
        )
        loaded = history.list_history(conn)

    assert [item["name"] for item in loaded] == [
        "Second Radio",
        "First Radio",
    ]


def test_history_record_updates_existing_station_play_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "History Radio",
        "url": "https://example.com/history",
    }

    with db.connect() as conn:
        history.add_history_record(
            conn,
            station,
            played_at="2026-01-01T10:00:00+00:00",
        )
        history.add_history_record(
            conn,
            station,
            played_at="2026-01-01T11:00:00+00:00",
        )
        loaded = history.list_history(conn)

    assert len(loaded) == 1
    assert loaded[0]["name"] == "History Radio"
    assert loaded[0]["play_count"] == 2
    assert loaded[0]["last_played_at"] == "2026-01-01T11:00:00+00:00"


def test_add_history_record_ignores_station_without_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        history.add_history_record(conn, {"name": "No URL Radio"})
        loaded = history.list_history(conn)

    assert loaded == []


def test_list_history_respects_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        for index in range(5):
            history.add_history_record(
                conn,
                {
                    "name": f"Radio {index}",
                    "url": f"https://example.com/{index}",
                },
                played_at=f"2026-01-01T1{index}:00:00+00:00",
            )

        loaded = history.list_history(conn, limit=2)

    assert len(loaded) == 2
    assert [item["name"] for item in loaded] == ["Radio 4", "Radio 3"]


def test_replace_history_replaces_existing_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    original = {
        "name": "Original Radio",
        "url": "https://example.com/original",
    }
    replacement = {
        "name": "Replacement Radio",
        "url": "https://example.com/replacement",
        "last_played_at": "2026-01-01T12:00:00+00:00",
        "play_count": 7,
    }

    with db.connect() as conn:
        history.add_history_record(conn, original)
        history.replace_history(conn, [replacement])
        loaded = history.list_history(conn)

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Replacement Radio"
    assert loaded[0]["play_count"] == 7
    assert loaded[0]["last_played_at"] == "2026-01-01T12:00:00+00:00"


def test_replace_history_respects_limit_and_ignores_invalid_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    items = [
        {"name": "No URL"},
        {
            "name": "Radio 1",
            "url": "https://example.com/1",
            "last_played_at": "2026-01-01T10:00:00+00:00",
        },
        {
            "name": "Radio 2",
            "url": "https://example.com/2",
            "last_played_at": "2026-01-01T11:00:00+00:00",
        },
    ]

    with db.connect() as conn:
        history.replace_history(conn, items, limit=2)
        loaded = history.list_history(conn)

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Radio 1"


def test_clear_history_records_removes_saved_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        history.add_history_record(
            conn,
            {
                "name": "History Radio",
                "url": "https://example.com/history",
            },
        )
        history.clear_history_records(conn)
        loaded = history.list_history(conn)

    assert loaded == []
