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


def test_web_users_list_prints_users_without_password_hash(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    password_hash = auth.hash_password(VALID_PASSWORD)
    with db.connect() as conn:
        db.get_or_create_user(
            conn,
            "alice",
            password_hash=password_hash,
            is_admin=True,
            is_active=True,
        )
        conn.commit()

    monkeypatch.setattr(sys, "argv", ["fluxtuner", "web", "users", "list"])

    __main__.main()

    output = capsys.readouterr().out
    assert "alice" in output
    assert "Argon2" not in output
    assert "$argon2id$" not in output


def test_set_password_updates_existing_user_and_revokes_sessions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    old_password = "old correct horse battery staple"
    new_password = "new correct horse battery staple"

    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password(old_password),
            is_admin=True,
            is_active=True,
        )
        token = auth.create_session(conn, user_id)
        conn.commit()

    run_command(
        monkeypatch,
        ["web", "users", "set-password", "alice"],
        [new_password, new_password],
    )

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        assert auth.verify_password(old_password, str(user["password_hash"])) is False
        assert auth.verify_password(new_password, str(user["password_hash"])) is True
        assert auth.get_session(conn, token) is None


def test_set_password_rejects_missing_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    with pytest.raises(SystemExit) as exc:
        run_command(
            monkeypatch,
            ["web", "users", "set-password", "missing"],
            [VALID_PASSWORD, VALID_PASSWORD],
        )

    assert exc.value.code == 1


def test_deactivate_user_marks_inactive_and_revokes_sessions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password(VALID_PASSWORD),
            is_admin=True,
            is_active=True,
        )
        token = auth.create_session(conn, user_id)
        conn.commit()

    monkeypatch.setattr(sys, "argv", ["fluxtuner", "web", "users", "deactivate", "alice"])

    __main__.main()

    with db.connect() as conn:
        user = db.get_user_by_username(conn, "alice")
        assert user is not None
        assert user["is_active"] is False
        assert auth.get_session(conn, token) is None


def test_deactivate_rejects_missing_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()

    monkeypatch.setattr(sys, "argv", ["fluxtuner", "web", "users", "deactivate", "missing"])

    with pytest.raises(SystemExit) as exc:
        __main__.main()

    assert exc.value.code == 1
