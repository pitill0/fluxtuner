# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, users


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_get_or_create_user_is_case_insensitive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        first_id = users.get_or_create_user(
            conn,
            "Laura",
            display_name="Laura",
        )
        second_id = users.get_or_create_user(
            conn,
            "laura",
            display_name="Other",
        )

    assert first_id == second_id


def test_get_or_create_user_creates_user_with_expected_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        user_id = users.get_or_create_user(
            conn,
            "Laura",
            display_name="Laura C.",
            password_hash="hashed-password",
            is_admin=True,
        )
        user = users.get_user_by_username(conn, "laura")

    assert user is not None
    assert user["id"] == user_id
    assert user["username"] == "Laura"
    assert user["display_name"] == "Laura C."
    assert user["password_hash"] == "hashed-password"
    assert user["is_admin"] is True
    assert user["is_active"] is True
    assert user["approval_status"] == users.APPROVAL_APPROVED


def test_get_or_create_user_requires_username(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        try:
            users.get_or_create_user(conn, "   ")
        except ValueError as exc:
            assert str(exc) == "Username is required."
        else:
            raise AssertionError("Expected ValueError")


def test_get_user_by_username_returns_none_for_blank_username(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        user = users.get_user_by_username(conn, "   ")

    assert user is None


def test_list_users_returns_users_in_creation_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        users.get_or_create_user(conn, "laura", display_name="Laura")
        users.get_or_create_user(conn, "guest", display_name="Guest")
        loaded = users.list_users(conn)

    assert [(item["username"], item["display_name"]) for item in loaded] == [
        ("default", "Default"),
        ("laura", "Laura"),
        ("guest", "Guest"),
    ]


def test_delete_user_removes_user(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        user_id = users.get_or_create_user(conn, "laura")
        deleted = users.delete_user(conn, user_id)
        loaded = users.get_user_by_username(conn, "laura")

    assert deleted is True
    assert loaded is None
