# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from fluxtuner.core import db, favorites, history, manual_playlists, recovery_codes
from fluxtuner.web import auth, maintenance
from fluxtuner.web.app import create_app
from fluxtuner.web.context import authenticated_user, effective_profile_name
from fluxtuner.web.security import SESSION_COOKIE_NAME


def test_effective_profile_name_delegates_profile_resolution() -> None:
    assert effective_profile_name(None) is None
    assert effective_profile_name("") == ""
    assert effective_profile_name(" main ") == "main"


def test_authenticated_user_returns_session_user(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "admin", password_hash="hash", is_admin=True)
        token = auth.create_session(conn, user_id)

    request = SimpleNamespace(cookies={SESSION_COOKIE_NAME: token})

    user = authenticated_user(request)

    assert user is not None
    assert user["username"] == "admin"
    assert user["is_admin"] == 1


def test_authenticated_user_returns_none_without_session(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setenv("FLUXTUNER_DB", str(db_path))

    request = SimpleNamespace(cookies={})

    assert authenticated_user(request) is None


def test_web_lifespan_initializes_database_once_off_request_path(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    init_calls = 0
    original_init_db = db.init_db

    def counted_init_db(path=None):
        nonlocal init_calls
        init_calls += 1
        return original_init_db(path)

    monkeypatch.setattr(db, "init_db", counted_init_db)

    with TestClient(create_app()) as client:
        response = client.get("/api/setup/status")

    assert response.status_code == 200
    assert init_calls == 1

    with db.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert version == db.CURRENT_SCHEMA_VERSION


def test_web_request_does_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    with TestClient(create_app()) as client:
        migration_calls = 0
        response = client.get("/api/setup/status")

    assert response.status_code == 200
    assert migration_calls == 0


def test_authenticated_session_resolution_runs_off_event_loop(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")
        token = auth.create_session(conn, user_id)
        conn.commit()

    offloaded_calls = 0

    import asyncio

    original_to_thread = asyncio.to_thread

    async def counted_to_thread(func, /, *args, **kwargs):
        nonlocal offloaded_calls
        offloaded_calls += 1
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(
        "fluxtuner.web.app.asyncio.to_thread",
        counted_to_thread,
    )

    with TestClient(create_app()) as client:
        # Ignore the expected startup db.init_db() offload. We specifically
        # want to observe work caused by the authenticated request below.
        offloaded_calls = 0

        client.cookies.set(SESSION_COOKIE_NAME, token)
        response = client.get("/api/health")

    assert response.status_code == 200
    assert offloaded_calls >= 1


def test_setup_and_admin_dashboard_do_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(
        manual_playlists,
        "PLAYLISTS_FILE",
        tmp_path / "playlists.json",
    )
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    with TestClient(create_app()) as client:
        migration_calls = 0
        setup_response = client.post(
            "/api/setup/create-admin",
            json={
                "username": "alice",
                "password": "correct horse battery staple",
                "setup_token": "setup-secret",
            },
        )

        assert setup_response.status_code == 200

        dashboard_response = client.get("/api/dashboard")

    assert dashboard_response.status_code == 200
    assert migration_calls == 0


def test_public_stats_does_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    with TestClient(create_app()) as client:
        migration_calls = 0
        response = client.get("/api/public/stats")

    assert response.status_code == 200
    assert migration_calls == 0


def test_login_does_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    with TestClient(create_app()) as client:
        migration_calls = 0
        response = client.post(
            "/api/auth/login",
            json={
                "username": "missing-user",
                "password": "correct horse battery staple",
            },
        )

    assert response.status_code == 401
    assert migration_calls == 0


def test_admin_list_users_does_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            "admin",
            password_hash=auth.hash_password("correct horse battery staple"),
            is_admin=True,
            is_active=True,
        )
        conn.execute(
            """
            UPDATE users
            SET approval_status = ?
            WHERE id = ?
            """,
            (db.APPROVAL_APPROVED, user_id),
        )
        token = auth.create_session(conn, user_id)
        conn.commit()

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    with TestClient(create_app()) as client:
        migration_calls = 0
        client.cookies.set(SESSION_COOKIE_NAME, token)
        response = client.get("/api/admin/users")

    assert response.status_code == 200
    assert migration_calls == 0


def test_authenticated_user_fallback_does_not_run_schema_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(
            conn,
            "fallback-user",
            password_hash=auth.hash_password("correct horse battery staple"),
            is_active=True,
        )
        conn.execute(
            """
            UPDATE users
            SET approval_status = ?
            WHERE id = ?
            """,
            (db.APPROVAL_APPROVED, user_id),
        )
        token = auth.create_session(conn, user_id)
        conn.commit()

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    request = type(
        "Request",
        (),
        {
            "state": object(),
            "cookies": {SESSION_COOKIE_NAME: token},
        },
    )()

    user = authenticated_user(request)

    assert user is not None
    assert user["username"] == "fallback-user"
    assert migration_calls == 0


def test_dashboard_does_not_reinitialize_database(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(
        manual_playlists,
        "PLAYLISTS_FILE",
        tmp_path / "playlists.json",
    )
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    monkeypatch.setenv("FLUXTUNER_WEB_SETUP_TOKEN", "setup-secret")

    init_calls = 0
    original_init_db = db.init_db

    def counted_init_db(db_path=None):
        nonlocal init_calls
        init_calls += 1
        return original_init_db(db_path)

    monkeypatch.setattr(db, "init_db", counted_init_db)

    with TestClient(create_app()) as client:
        setup_response = client.post(
            "/api/setup/create-admin",
            json={
                "username": "alice",
                "password": "correct horse battery staple",
                "setup_token": "setup-secret",
            },
        )
        assert setup_response.status_code == 200

        # Ignore legitimate startup/setup initialization. Measure only
        # normal dashboard access against the already-prepared database.
        init_calls = 0

        dashboard_response = client.get("/api/dashboard")

    assert dashboard_response.status_code == 200
    assert init_calls == 0


def test_web_lifespan_runs_auth_maintenance_after_database_init_off_event_loop(
    monkeypatch,
) -> None:
    events: list[str] = []
    offloaded_functions: list[object] = []

    def fake_init_db() -> None:
        events.append("init_db")

    def fake_auth_maintenance_if_due() -> bool:
        events.append("auth_maintenance")
        return True

    async def counted_to_thread(func, /, *args, **kwargs):
        offloaded_functions.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(db, "init_db", fake_init_db)
    monkeypatch.setattr(
        maintenance,
        "run_auth_maintenance_if_due",
        fake_auth_maintenance_if_due,
    )
    monkeypatch.setattr(
        "fluxtuner.web.app.asyncio.to_thread",
        counted_to_thread,
    )

    with TestClient(create_app()):
        pass

    assert events == [
        "init_db",
        "auth_maintenance",
    ]
    assert offloaded_functions == [
        fake_init_db,
        fake_auth_maintenance_if_due,
    ]


def test_auth_entry_points_trigger_throttled_maintenance(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    maintenance_calls = 0

    def fake_maintenance_if_due() -> bool:
        nonlocal maintenance_calls
        maintenance_calls += 1
        return True

    monkeypatch.setattr(
        maintenance,
        "run_auth_maintenance_if_due",
        fake_maintenance_if_due,
    )

    with TestClient(create_app()) as client:
        # Ignore the expected startup maintenance call.
        maintenance_calls = 0

        register_response = client.post("/api/auth/register", json={})
        recovery_response = client.post("/api/auth/recover-password", json={})
        login_response = client.post("/api/auth/login", json={})
        setup_response = client.post("/api/setup/create-admin", json={})

    assert register_response.status_code == 400
    assert recovery_response.status_code == 401
    assert login_response.status_code == 401
    assert setup_response.status_code == 400
    assert maintenance_calls == 4


def test_recovery_route_does_not_purge_attempts_directly(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    with TestClient(create_app()) as client:

        def forbidden_direct_purge(*_args, **_kwargs):
            raise AssertionError("recovery endpoint ran purge_old_recovery_attempts directly")

        monkeypatch.setattr(
            recovery_codes,
            "purge_old_recovery_attempts",
            forbidden_direct_purge,
        )

        response = client.post(
            "/api/auth/recover-password",
            json={
                "username": "missing-user",
                "recovery_code": "not-a-real-code",
                "new_password": "correct horse battery staple",
            },
        )

    assert response.status_code == 401


def test_failed_auth_request_does_not_rollback_opportunistic_cleanup(
    tmp_path,
    monkeypatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    db_path = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)

    db.init_db()

    now = datetime.now(UTC)

    with db.connect() as conn:
        auth.record_login_attempt(
            conn,
            "stale-user",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=25),
        )
        conn.commit()

    monkeypatch.setattr(
        maintenance,
        "_last_auth_maintenance_monotonic",
        None,
    )

    with TestClient(create_app()) as client:
        # Startup has already consumed the throttle window. Reset it so this
        # request itself must perform opportunistic maintenance.
        monkeypatch.setattr(
            maintenance,
            "_last_auth_maintenance_monotonic",
            None,
        )

        response = client.post(
            "/api/auth/login",
            json={
                "username": "missing-user",
                "password": "wrong-password",
            },
        )

    assert response.status_code == 401

    with db.connect() as conn:
        stale_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM web_login_attempts
            WHERE normalized_username = 'stale-user'
            """
        ).fetchone()[0]

    assert stale_count == 0
