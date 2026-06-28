import sys

import pytest

from fluxtuner import __main__
from fluxtuner.core import db
from fluxtuner.web import auth

VALID_PASSWORD = "correct horse battery staple"


def run_command(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    passwords: list[str],
) -> None:
    password_iter = iter(passwords)

    monkeypatch.setattr(sys, "argv", ["fluxtuner", *args])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(password_iter))

    __main__.main()


def test_create_admin_creates_active_admin_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")

    run_command(
        monkeypatch,
        ["web", "users", "create-admin", "alice"],
        [VALID_PASSWORD, VALID_PASSWORD],
    )

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is not None
    assert user["username"] == "alice"
    assert user["is_admin"] is True
    assert user["is_active"] is True
    assert user["password_hash"] is not None
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_create_admin_updates_existing_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash=None,
            is_admin=False,
            is_active=False,
        )
        conn.commit()

    run_command(
        monkeypatch,
        ["web", "users", "create-admin", "alice"],
        [VALID_PASSWORD, VALID_PASSWORD],
    )

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is not None
    assert user["id"] == user_id
    assert user["is_admin"] is True
    assert user["is_active"] is True
    assert auth.verify_password(VALID_PASSWORD, str(user["password_hash"])) is True


def test_create_admin_rejects_password_mismatch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")

    with pytest.raises(SystemExit) as exc:
        run_command(
            monkeypatch,
            ["web", "users", "create-admin", "alice"],
            [VALID_PASSWORD, "different horse battery staple"],
        )

    assert exc.value.code == 1

    db.init_db()
    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is None


def test_create_admin_rejects_weak_password(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")

    with pytest.raises(SystemExit) as exc:
        run_command(
            monkeypatch,
            ["web", "users", "create-admin", "alice"],
            ["short", "short"],
        )

    assert exc.value.code == 1

    db.init_db()
    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")

    assert user is None


def test_web_users_unknown_command_exits(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "web", "users", "unknown"])

    with pytest.raises(SystemExit) as exc:
        __main__.main()

    assert exc.value.code == 1
