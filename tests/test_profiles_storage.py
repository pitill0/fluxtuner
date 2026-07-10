# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, profiles


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_get_profile_by_name_returns_default_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile = profiles.get_profile_by_name(conn, "default")

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
        profile = profiles.get_profile_by_name(conn, "DEFAULT")

    assert profile is not None
    assert profile["name"] == "default"


def test_get_profile_by_name_returns_none_for_blank_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile = profiles.get_profile_by_name(conn, "   ")

    assert profile is None


def test_get_or_create_profile_creates_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        profile_id = profiles.get_or_create_profile(
            conn,
            "work",
            display_name="Work",
        )
        profile = profiles.get_profile_by_name(conn, "work")

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
        first_profile_id = profiles.get_or_create_profile(
            conn,
            "work",
            display_name="Work",
        )
        second_profile_id = profiles.get_or_create_profile(
            conn,
            "WORK",
            display_name="Ignored",
        )
        profile = profiles.get_profile_by_name(conn, "work")

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
            profiles.get_or_create_profile(conn, "   ")
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
        profiles.get_or_create_profile(conn, "work", display_name="Work")
        profiles.get_or_create_profile(conn, "testing", display_name="Testing")
        loaded = profiles.list_profiles(conn)

    assert [(item["name"], item["display_name"]) for item in loaded] == [
        ("default", "Default"),
        ("work", "Work"),
        ("testing", "Testing"),
    ]


def test_profiles_are_unique_per_user(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        laura_id = db.get_or_create_user(conn, "laura")
        guest_id = db.get_or_create_user(conn, "guest")

        laura_profile_id = profiles.get_or_create_profile(
            conn,
            "work",
            user_id=laura_id,
        )
        guest_profile_id = profiles.get_or_create_profile(
            conn,
            "work",
            user_id=guest_id,
        )
        repeated_laura_profile_id = profiles.get_or_create_profile(
            conn,
            "WORK",
            user_id=laura_id,
        )

        laura_profiles = profiles.list_profiles(conn, user_id=laura_id)
        guest_profiles = profiles.list_profiles(conn, user_id=guest_id)

    assert laura_profile_id != guest_profile_id
    assert repeated_laura_profile_id == laura_profile_id
    assert [profile["name"] for profile in laura_profiles] == ["work"]
    assert [profile["name"] for profile in guest_profiles] == ["work"]
