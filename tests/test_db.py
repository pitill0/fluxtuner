from pathlib import Path

from fluxtuner.core import db


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_init_db_creates_database_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_file = patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    assert db_file.exists()


def test_init_db_creates_expected_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    with db.connect() as conn:
        assert db.table_names(conn) == {
            "favorites",
            "history_entries",
            "playlist_stations",
            "playlists",
            "profiles",
            "schema_migrations",
            "stations",
        }


def test_init_db_creates_default_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT name, display_name FROM profiles WHERE name = ?",
            (db.DEFAULT_PROFILE_NAME,),
        ).fetchone()

    assert row is not None
    assert row["name"] == "default"
    assert row["display_name"] == "Default"


def test_get_default_profile_id_is_stable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    first_id = db.get_default_profile_id()
    second_id = db.get_default_profile_id()

    assert first_id == second_id

    with db.connect() as conn:
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    assert profile_count == 1


def test_init_db_is_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()
    db.init_db()

    with db.connect() as conn:
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        migration_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]

    assert profile_count == 1
    assert migration_count == 1


def test_connect_enables_foreign_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    with db.connect() as conn:
        foreign_keys_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert foreign_keys_enabled == 1


def test_init_db_accepts_explicit_database_path(tmp_path: Path) -> None:
    db_file = tmp_path / "custom.db"

    db.init_db(db_file)

    assert db_file.exists()


def test_upsert_station_creates_station(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": "128",
        "tags": "test, radio",
    }

    with db.connect() as conn:
        station_id = db.upsert_station(conn, station)
        loaded = db.get_station_by_key(conn, "https://example.com/resolved")

    assert station_id == 1
    assert loaded is not None
    assert loaded["name"] == "Test Radio"
    assert loaded["url"] == "https://example.com/stream"
    assert loaded["url_resolved"] == "https://example.com/resolved"
    assert loaded["country"] == "Spain"
    assert loaded["codec"] == "MP3"
    assert loaded["bitrate"] == 128
    assert loaded["tags"] == "test, radio"


def test_upsert_station_updates_existing_station(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    original = {
        "name": "Original Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": 128,
    }
    updated = {
        "name": "Updated Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "France",
        "codec": "AAC",
        "bitrate": 192,
    }

    with db.connect() as conn:
        first_id = db.upsert_station(conn, original)
        second_id = db.upsert_station(conn, updated)
        loaded = db.get_station_by_key(conn, "https://example.com/resolved")

    assert first_id == second_id
    assert loaded is not None
    assert loaded["name"] == "Updated Radio"
    assert loaded["country"] == "France"
    assert loaded["codec"] == "AAC"
    assert loaded["bitrate"] == 192


def test_upsert_station_preserves_extra_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Metadata Radio",
        "url": "https://example.com/stream",
        "homepage": "https://example.com",
        "custom_field": "kept",
    }

    with db.connect() as conn:
        db.upsert_station(conn, station)
        loaded = db.get_station_by_key(conn, "https://example.com/stream")

    assert loaded is not None
    assert loaded["custom_field"] == "kept"
    assert loaded["homepage"] == "https://example.com"


def test_upsert_station_rejects_station_without_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        try:
            db.upsert_station(conn, {"name": "No URL Radio"})
        except ValueError as exc:
            assert str(exc) == "Station URL is required."
        else:
            raise AssertionError("Expected ValueError")


def test_favorite_record_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "custom_name": "My Test Radio",
        "favorite_tags": [" radio ", "test", "radio"],
    }

    with db.connect() as conn:
        added = db.add_favorite_record(conn, station)
        favorites = db.list_favorites(conn)

    assert added is True
    assert len(favorites) == 1
    assert favorites[0]["name"] == "Test Radio"
    assert favorites[0]["url"] == "https://example.com/stream"
    assert favorites[0]["url_resolved"] == "https://example.com/resolved"
    assert favorites[0]["custom_name"] == "My Test Radio"
    assert favorites[0]["favorite_tags"] == ["radio", "test"]


def test_add_favorite_record_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        first_added = db.add_favorite_record(conn, station)
        second_added = db.add_favorite_record(conn, station)
        favorites = db.list_favorites(conn)

    assert first_added is True
    assert second_added is False
    assert len(favorites) == 1


def test_remove_favorite_record_accepts_station_key_or_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
    }

    with db.connect() as conn:
        db.add_favorite_record(conn, station)
        removed = db.remove_favorite_record(conn, "https://example.com/resolved")
        favorites = db.list_favorites(conn)

    assert removed is True
    assert favorites == []


def test_update_favorite_record_changes_name_and_tags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        db.add_favorite_record(conn, station)
        changed = db.update_favorite_record(
            conn,
            "https://example.com/stream",
            custom_name="Custom Radio",
            favorite_tags=["news", " morning "],
        )
        favorites = db.list_favorites(conn)

    assert changed is True
    assert favorites[0]["custom_name"] == "Custom Radio"
    assert favorites[0]["favorite_tags"] == ["morning", "news"]


def test_replace_favorites_replaces_existing_favorites(
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
    }

    with db.connect() as conn:
        db.add_favorite_record(conn, original)
        db.replace_favorites(conn, [replacement])
        favorites = db.list_favorites(conn)

    assert len(favorites) == 1
    assert favorites[0]["name"] == "Replacement Radio"
    assert favorites[0]["url"] == "https://example.com/replacement"


def test_replace_favorites_ignores_items_without_station_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.replace_favorites(
            conn,
            [
                {"name": "No URL"},
                {
                    "name": "Valid Radio",
                    "url": "https://example.com/valid",
                },
            ],
        )
        favorites = db.list_favorites(conn)

    assert len(favorites) == 1
    assert favorites[0]["name"] == "Valid Radio"


def test_favorite_tags_to_json_normalizes_tags() -> None:
    assert db.favorite_tags_to_json([" rock ", "jazz", "rock", ""]) == '["jazz", "rock"]'


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
        db.add_history_record(conn, first, played_at="2026-01-01T10:00:00+00:00")
        db.add_history_record(conn, second, played_at="2026-01-01T11:00:00+00:00")
        history = db.list_history(conn)

    assert [item["name"] for item in history] == ["Second Radio", "First Radio"]


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
        db.add_history_record(conn, station, played_at="2026-01-01T10:00:00+00:00")
        db.add_history_record(conn, station, played_at="2026-01-01T11:00:00+00:00")
        history = db.list_history(conn)

    assert len(history) == 1
    assert history[0]["name"] == "History Radio"
    assert history[0]["play_count"] == 2
    assert history[0]["last_played_at"] == "2026-01-01T11:00:00+00:00"


def test_add_history_record_ignores_station_without_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.add_history_record(conn, {"name": "No URL Radio"})
        history = db.list_history(conn)

    assert history == []


def test_list_history_respects_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        for index in range(5):
            db.add_history_record(
                conn,
                {
                    "name": f"Radio {index}",
                    "url": f"https://example.com/{index}",
                },
                played_at=f"2026-01-01T1{index}:00:00+00:00",
            )

        history = db.list_history(conn, limit=2)

    assert len(history) == 2
    assert [item["name"] for item in history] == ["Radio 4", "Radio 3"]


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
        db.add_history_record(conn, original)
        db.replace_history(conn, [replacement])
        history = db.list_history(conn)

    assert len(history) == 1
    assert history[0]["name"] == "Replacement Radio"
    assert history[0]["play_count"] == 7
    assert history[0]["last_played_at"] == "2026-01-01T12:00:00+00:00"


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
        db.replace_history(conn, items, limit=2)
        history = db.list_history(conn)

    assert len(history) == 1
    assert history[0]["name"] == "Radio 1"


def test_clear_history_records_removes_saved_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.add_history_record(
            conn,
            {
                "name": "History Radio",
                "url": "https://example.com/history",
            },
        )
        db.clear_history_records(conn)
        history = db.list_history(conn)

    assert history == []


def test_create_playlist_record_avoids_case_insensitive_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        created = db.create_playlist_record(conn, "Morning")
        duplicated = db.create_playlist_record(conn, "morning")
        playlists = db.list_playlists(conn)

    assert created is True
    assert duplicated is False
    assert playlists == [{"name": "Morning", "station_keys": []}]


def test_add_station_to_playlist_record_creates_playlist_if_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        added = db.add_station_to_playlist_record(conn, "Morning", station)
        playlist = db.get_playlist_record(conn, "morning")

    assert added is True
    assert playlist == {
        "name": "Morning",
        "station_keys": ["https://example.com/stream"],
    }


def test_add_station_to_playlist_record_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        first_added = db.add_station_to_playlist_record(conn, "Morning", station)
        second_added = db.add_station_to_playlist_record(conn, "Morning", station)
        playlist = db.get_playlist_record(conn, "Morning")

    assert first_added is True
    assert second_added is False
    assert playlist == {
        "name": "Morning",
        "station_keys": ["https://example.com/stream"],
    }


def test_remove_station_from_playlist_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        db.add_station_to_playlist_record(conn, "Morning", station)
        removed = db.remove_station_from_playlist_record(conn, "Morning", station)
        playlist = db.get_playlist_record(conn, "Morning")

    assert removed is True
    assert playlist == {"name": "Morning", "station_keys": []}


def test_delete_playlist_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.create_playlist_record(conn, "Morning")
        deleted = db.delete_playlist_record(conn, "morning")
        playlists = db.list_playlists(conn)

    assert deleted is True
    assert playlists == []


def test_replace_playlists_replaces_existing_playlists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.create_playlist_record(conn, "Old")
        db.replace_playlists(
            conn,
            [
                {
                    "name": "Morning",
                    "station_keys": [
                        "https://example.com/a",
                        "https://example.com/b",
                    ],
                }
            ],
        )
        playlists = db.list_playlists(conn)

    assert playlists == [
        {
            "name": "Morning",
            "station_keys": [
                "https://example.com/a",
                "https://example.com/b",
            ],
        }
    ]


def test_replace_playlists_ignores_invalid_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.replace_playlists(
            conn,
            [
                {"name": ""},
                {
                    "name": "Valid",
                    "station_keys": "https://example.com/not-a-list",
                },
                {
                    "name": "Also Valid",
                    "station_keys": [
                        "",
                        "https://example.com/valid",
                    ],
                },
            ],
        )
        playlists = db.list_playlists(conn)

    assert playlists == [
        {"name": "Valid", "station_keys": []},
        {"name": "Also Valid", "station_keys": ["https://example.com/valid"]},
    ]


def test_playlist_station_order_is_preserved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "A", "url": "https://example.com/a"},
        )
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "B", "url": "https://example.com/b"},
        )
        playlist = db.get_playlist_record(conn, "Morning")

    assert playlist == {
        "name": "Morning",
        "station_keys": [
            "https://example.com/a",
            "https://example.com/b",
        ],
    }


def test_get_profile_by_name_returns_default_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile = db.get_profile_by_name(conn, "default")

    assert profile is not None
    assert profile["name"] == "default"
    assert profile["display_name"] == "Default"


def test_get_profile_by_name_is_case_insensitive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile = db.get_profile_by_name(conn, "DEFAULT")

    assert profile is not None
    assert profile["name"] == "default"


def test_get_profile_by_name_returns_none_for_blank_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile = db.get_profile_by_name(conn, "   ")

    assert profile is None


def test_get_or_create_profile_creates_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile_id = db.get_or_create_profile(conn, "work", display_name="Work")
        profile = db.get_profile_by_name(conn, "work")

    assert profile is not None
    assert profile["id"] == profile_id
    assert profile["name"] == "work"
    assert profile["display_name"] == "Work"


def test_get_or_create_profile_reuses_existing_profile_case_insensitive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        first_profile_id = db.get_or_create_profile(conn, "work", display_name="Work")
        second_profile_id = db.get_or_create_profile(conn, "WORK", display_name="Ignored")
        profile = db.get_profile_by_name(conn, "work")

    assert second_profile_id == first_profile_id
    assert profile is not None
    assert profile["display_name"] == "Work"


def test_get_or_create_profile_requires_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        try:
            db.get_or_create_profile(conn, "   ")
        except ValueError as exc:
            assert str(exc) == "Profile name is required."
        else:
            raise AssertionError("Expected ValueError")


def test_list_profiles_returns_profiles_in_creation_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        db.get_or_create_profile(conn, "work", display_name="Work")
        db.get_or_create_profile(conn, "testing", display_name="Testing")
        profiles = db.list_profiles(conn)

    assert [(item["name"], item["display_name"]) for item in profiles] == [
        ("default", "Default"),
        ("work", "Work"),
        ("testing", "Testing"),
    ]
