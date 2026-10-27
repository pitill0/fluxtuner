# SPDX-License-Identifier: MIT
"""Pre-release storage and HTML delivery regressions."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.remote_subscription_store import create_subscription
from fluxtuner.web import maintenance
from fluxtuner.web.app import create_app
from fluxtuner.web.remote_subscription_service import confirm_stored_refresh, preview_refresh


def test_preview_replaces_old_receipts_and_confirm_deletes(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "receipts.db")
    db.init_db()
    with db.connect() as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://example.org/catalog.m3u",
            entries=[M3UEntry("Old", "https://example.org/old")],
        )
        conn.commit()
    payload = b"#EXTM3U\n#EXTINF:-1,New\nhttps://example.org/new\n"
    receipts = [
        preview_refresh(
            payload, user_id=user, profile_name=None, source_id=source, session_token="session"
        )
        for _ in range(30)
    ]
    with db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM remote_catalog_refresh_receipts").fetchone()[0] == 1
        )
    with pytest.raises(ValueError):
        confirm_stored_refresh(
            user_id=user,
            profile_name=None,
            source_id=source,
            revision=1,
            receipt=receipts[0]["receipt"],
            session_token="session",
        )
    confirm_stored_refresh(
        user_id=user,
        profile_name=None,
        source_id=source,
        revision=1,
        receipt=receipts[-1]["receipt"],
        session_token="session",
    )
    with db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM remote_catalog_refresh_receipts").fetchone()[0] == 0
        )


def test_expired_receipt_is_cleaned_by_maintenance(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "maintenance.db")
    db.init_db()
    with db.connect() as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://example.org/catalog.m3u",
            entries=[M3UEntry("Old", "https://example.org/old")],
        )
        conn.commit()
    payload = b"#EXTM3U\n#EXTINF:-1,New\nhttps://example.org/new\n"
    preview_refresh(
        payload, user_id=user, profile_name=None, source_id=source, session_token="session"
    )
    later = datetime.now(UTC) + timedelta(hours=1)
    result = maintenance.run_auth_maintenance(now=later)
    assert result.expired_refresh_receipts == 1
    with db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM remote_catalog_refresh_receipts").fetchone()[0] == 0
        )


def test_index_gzip_and_revalidation():
    client = TestClient(create_app())
    identity = client.get("/", headers={"Accept-Encoding": "identity"})
    zipped = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert identity.status_code == zipped.status_code == 200
    assert identity.content == zipped.content
    assert zipped.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in zipped.headers["vary"]
    assert zipped.headers["etag"] != identity.headers["etag"]
    assert (
        client.get(
            "/",
            headers={
                "Accept-Encoding": "gzip",
                "If-None-Match": zipped.headers["etag"],
            },
        ).status_code
        == 304
    )
    assert (
        client.get(
            "/",
            headers={
                "Accept-Encoding": "identity",
                "If-None-Match": identity.headers["etag"],
            },
        ).status_code
        == 304
    )
    assert (
        "content-encoding"
        not in client.get(
            "/",
            headers={
                "Accept-Encoding": "gzip;q=0",
            },
        ).headers
    )
    assert b"/static/brand-icon.webp" in identity.content
    assert client.get("/static/brand-icon.webp").status_code == 200
