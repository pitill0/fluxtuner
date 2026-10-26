# SPDX-License-Identifier: MIT
"""Exact-snapshot Web subscription refresh service contract."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.remote_subscription_store import (
    create_subscription,
    get_entries,
    get_subscription,
)
from fluxtuner.web.remote_subscription_service import (
    confirm_refresh,
    confirm_stored_refresh,
    create_from_snapshot,
    preview_refresh,
)


def _fixture(tmp_path, monkeypatch):
    path = tmp_path / "web-subscriptions.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db()
    with db.connect() as conn:
        user_id = db.ensure_default_user(conn)
        profile_id = db.ensure_default_profile(conn, user_id=user_id)
        source_id = create_subscription(
            conn,
            profile_id=profile_id,
            catalog_url="https://catalog.example/list.m3u",
            entries=[M3UEntry("Original", "https://stream.example/old")],
        )
        conn.commit()
    return user_id, profile_id, source_id


def _payload(url="https://stream.example/new"):
    return (
        "#EXTM3U\n"
        "#EXTINF:-1,New\n"
        f"{url}\n"
    ).encode()


def test_preview_then_confirm_is_one_use(tmp_path, monkeypatch):
    user, profile, source = _fixture(tmp_path, monkeypatch)
    data = _payload()

    preview = preview_refresh(
        data, user_id=user, profile_name=None,
        source_id=source, session_token="session-a",
    )
    assert preview["revision"] == 1
    assert len(preview["added"]) == 1
    assert len(preview["removed"]) == 1

    arguments = dict(
        user_id=user, profile_name=None, source_id=source,
        revision=preview["revision"],
        receipt=preview["receipt"],
        session_token="session-a",
    )

    with pytest.raises(ValueError):
        confirm_refresh(_payload("https://stream.example/other"), **arguments)

    with pytest.raises(ValueError):
        confirm_refresh(data, **(arguments | {"session_token": "wrong"}))

    result = confirm_refresh(data, **arguments)
    assert result["status"] == "ok"
    assert result["revision"] == 2

    with pytest.raises(ValueError):
        confirm_refresh(data, **arguments)

    with db.connect() as conn:
        names = [
            item.name for item in get_entries(
                conn, profile_id=profile, source_id=source,
            )
        ]
        assert names == ["New"]


def test_foreign_user_cannot_preview(tmp_path, monkeypatch):
    user, _, source = _fixture(tmp_path, monkeypatch)
    with pytest.raises(LookupError):
        preview_refresh(
            _payload(),
            user_id=user + 500,
            profile_name=None,
            source_id=source,
            session_token="session-a",
        )


def test_stale_preview_preserves_committed_catalog(tmp_path, monkeypatch):
    user, profile, source = _fixture(tmp_path, monkeypatch)
    data = _payload()

    first = preview_refresh(
        data, user_id=user, profile_name=None,
        source_id=source, session_token="session-a",
    )
    second = preview_refresh(
        data, user_id=user, profile_name=None,
        source_id=source, session_token="session-a",
    )

    confirm_refresh(
        data, user_id=user, profile_name=None,
        source_id=source, revision=first["revision"],
        receipt=first["receipt"], session_token="session-a",
    )

    with pytest.raises(ValueError, match="Stale"):
        confirm_refresh(
            data, user_id=user, profile_name=None,
            source_id=source, revision=second["revision"],
            receipt=second["receipt"], session_token="session-a",
        )

    with db.connect() as conn:
        assert get_subscription(
            conn, profile_id=profile, source_id=source,
        )["revision"] == 2
        assert [entry.name for entry in get_entries(
            conn, profile_id=profile, source_id=source,
        )] == ["New"]



def test_stored_snapshot_confirmed_without_browser_bytes(
    tmp_path, monkeypatch,
):
    user, profile, source = _fixture(tmp_path, monkeypatch)
    preview = preview_refresh(
        _payload(),
        user_id=user,
        profile_name=None,
        source_id=source,
        session_token="session-a",
    )

    args = dict(
        user_id=user,
        profile_name=None,
        source_id=source,
        revision=preview["revision"],
        receipt=preview["receipt"],
        session_token="session-a",
    )

    with pytest.raises(ValueError):
        confirm_stored_refresh(
            **(args | {"session_token": "other-session"})
        )

    result = confirm_stored_refresh(**args)
    assert result["revision"] == 2

    with pytest.raises(ValueError):
        confirm_stored_refresh(**args)

    with db.connect() as conn:
        assert [
            e.name for e in get_entries(
                conn, profile_id=profile, source_id=source,
            )
        ] == ["New"]


def test_stored_snapshot_rejects_tampered_database_content(
    tmp_path, monkeypatch,
):
    user, profile, source = _fixture(tmp_path, monkeypatch)
    preview = preview_refresh(
        _payload(),
        user_id=user,
        profile_name=None,
        source_id=source,
        session_token="session-a",
    )

    with db.connect() as conn:
        conn.execute(
            """
            UPDATE remote_catalog_refresh_receipts
            SET snapshot_bytes = ?
            WHERE source_id = ?
            """,
            (_payload("https://stream.example/tampered"), source),
        )
        conn.commit()

    with pytest.raises(ValueError, match="receipt"):
        confirm_stored_refresh(
            user_id=user,
            profile_name=None,
            source_id=source,
            revision=preview["revision"],
            receipt=preview["receipt"],
            session_token="session-a",
        )

    with db.connect() as conn:
        assert get_subscription(
            conn, profile_id=profile, source_id=source,
        )["revision"] == 1



def test_create_from_snapshot_is_profile_owned(
    tmp_path, monkeypatch,
):
    path = tmp_path / "create-subscription.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db()

    with db.connect() as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        conn.commit()

    result = create_from_snapshot(
        _payload(),
        user_id=user,
        profile_name=None,
        catalog_url="https://catalog.example/list.m3u",
        display_name="My catalog",
    )
    assert result["revision"] == 1
    assert result["stations"] == 1

    with db.connect() as conn:
        subscription = get_subscription(
            conn,
            profile_id=profile,
            source_id=result["source_id"],
        )
        assert subscription["catalog_url"] == "https://catalog.example/list.m3u"
        assert len(get_entries(
            conn, profile_id=profile, source_id=result["source_id"],
        )) == 1

    with pytest.raises(LookupError):
        create_from_snapshot(
            _payload("https://stream.example/foreign"),
            user_id=user + 100,
            profile_name=None,
            catalog_url="https://catalog.example/foreign.m3u",
        )


def test_create_from_snapshot_invalid_input_is_atomic(
    tmp_path, monkeypatch,
):
    path = tmp_path / "invalid-subscription.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db()

    with db.connect() as conn:
        user = db.ensure_default_user(conn)
        conn.commit()

    invalid = (
        b"#EXTM3U\\n"
        b"#EXTINF:-1,Valid\\n"
        b"https://stream.example/valid\\n"
        b"#EXTINF:-1,Bad\\n"
        b"file:///etc/passwd\\n"
    )

    with pytest.raises(ValueError):
        create_from_snapshot(
            invalid,
            user_id=user,
            profile_name=None,
            catalog_url="https://catalog.example/invalid.m3u",
        )

    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM remote_catalog_subscriptions"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM station_sources"
        ).fetchone()[0] == 0



def test_preview_validators_are_committed_only_with_snapshot(
    tmp_path, monkeypatch,
):
    user, profile, source = _fixture(tmp_path, monkeypatch)

    with db.connect() as conn:
        assert get_subscription(
            conn, profile_id=profile, source_id=source,
        )["etag"] is None

    preview = preview_refresh(
        _payload(),
        user_id=user,
        profile_name=None,
        source_id=source,
        session_token="session-a",
        etag='"candidate-2"',
        last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
    )

    with db.connect() as conn:
        current = get_subscription(
            conn, profile_id=profile, source_id=source,
        )
        assert current["revision"] == 1
        assert current["etag"] is None
        assert current["last_modified"] is None

    confirmed = confirm_stored_refresh(
        user_id=user,
        profile_name=None,
        source_id=source,
        revision=preview["revision"],
        receipt=preview["receipt"],
        session_token="session-a",
    )
    assert confirmed["revision"] == 2

    with db.connect() as conn:
        current = get_subscription(
            conn, profile_id=profile, source_id=source,
        )
        assert current["revision"] == 2
        assert current["etag"] == '"candidate-2"'
        assert current["last_modified"] == "Wed, 21 Oct 2015 07:28:00 GMT"

    with pytest.raises(ValueError):
        confirm_stored_refresh(
            user_id=user,
            profile_name=None,
            source_id=source,
            revision=preview["revision"],
            receipt=preview["receipt"],
            session_token="session-a",
        )
