# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from types import SimpleNamespace

from fluxtuner.core import db
from fluxtuner.web import setup


def test_setup_token_helpers(monkeypatch) -> None:
    monkeypatch.delenv(setup.SETUP_TOKEN_ENV, raising=False)

    assert setup.setup_token() == ""
    assert setup.setup_token_required() is False
    assert setup.valid_setup_token("anything") is True

    monkeypatch.setenv(setup.SETUP_TOKEN_ENV, " setup-secret ")

    assert setup.setup_token() == "setup-secret"
    assert setup.setup_token_required() is True
    assert setup.valid_setup_token("setup-secret") is True
    assert setup.valid_setup_token("wrong") is False


def test_request_client_host_normalizes_missing_client() -> None:
    assert setup.request_client_host(SimpleNamespace(client=None)) == "unknown"


def test_request_client_host_uses_request_client_host() -> None:
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    assert setup.request_client_host(request) == "127.0.0.1"


def test_setup_request_is_local_hosts() -> None:
    for host in ("127.0.0.1", "::1", "localhost", "testclient", " LOCALHOST "):
        request = SimpleNamespace(client=SimpleNamespace(host=host))
        assert setup.setup_request_is_local(request) is True

    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.10"))
    assert setup.setup_request_is_local(request) is False


def test_configured_admin_exists_requires_real_active_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "setup.db")

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_user_approval_schema(conn)
        assert setup.configured_admin_exists(conn) is False

        inactive_id = db.get_or_create_user(
            conn,
            "inactive",
            password_hash="hash",
            is_admin=True,
            is_active=False,
        )
        conn.execute(
            "UPDATE users SET approval_status = ? WHERE id = ?",
            (db.APPROVAL_APPROVED, inactive_id),
        )
        assert setup.configured_admin_exists(conn) is False

        no_password_id = db.get_or_create_user(
            conn,
            "no-password",
            password_hash="",
            is_admin=True,
            is_active=True,
        )
        conn.execute(
            "UPDATE users SET approval_status = ? WHERE id = ?",
            (db.APPROVAL_APPROVED, no_password_id),
        )
        assert setup.configured_admin_exists(conn) is False

        db.get_or_create_user(
            conn,
            "admin",
            password_hash="hash",
            is_admin=True,
            is_active=True,
        )
        assert setup.configured_admin_exists(conn) is True
