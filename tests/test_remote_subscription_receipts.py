# SPDX-License-Identifier: MIT
"""Session, profile, revision and payload-bound subscription receipts."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.remote_subscription_store import (
    apply_update,
    create_subscription,
)
from fluxtuner.web import remote_subscription_receipts as receipts


def test_receipt_is_one_use_and_bound_to_exact_context(tmp_path):
    path = tmp_path / "receipts.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        other = db.get_or_create_profile(
            conn,
            "another",
            user_id=user,
        )
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://catalog.example/list.m3u",
            entries=[M3UEntry("A", "https://stream.example/a")],
        )
        conn.commit()

        data = b"#EXTM3U\n#EXTINF:-1,B\nhttps://stream.example/b\n"
        token = receipts.issue(
            conn,
            user_id=user,
            profile_id=profile,
            source_id=source,
            revision=1,
            session_token="session-a",
            data=data,
        )
        conn.commit()

        context = dict(
            token=token,
            user_id=user,
            profile_id=profile,
            source_id=source,
            revision=1,
            session_token="session-a",
            data=data,
        )

        for changed in (
            {"profile_id": other},
            {"source_id": source + 1000},
            {"revision": 2},
            {"session_token": "session-b"},
            {"data": data + b"# extra\n"},
        ):
            with pytest.raises(ValueError):
                receipts.consume(conn, **(context | changed))

        receipts.consume(conn, **context)

        with pytest.raises(ValueError):
            receipts.consume(conn, **context)

        conn.rollback()


def test_stale_revision_cannot_issue_or_reuse_receipt(tmp_path):
    path = tmp_path / "stale.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://catalog.example/list.m3u",
            entries=[M3UEntry("A", "https://stream.example/a")],
        )
        conn.commit()

        data = b"#EXTM3U\nhttps://stream.example/b\n"
        receipts.issue(
            conn,
            user_id=user,
            profile_id=profile,
            source_id=source,
            revision=1,
            session_token="session-a",
            data=data,
        )
        conn.commit()

        apply_update(
            conn,
            profile_id=profile,
            source_id=source,
            expected_revision=1,
            entries=[M3UEntry("B", "https://stream.example/b")],
        )
        conn.commit()

        with pytest.raises(ValueError, match="revision"):
            receipts.issue(
                conn,
                user_id=user,
                profile_id=profile,
                source_id=source,
                revision=1,
                session_token="session-a",
                data=data,
            )

        # The receipt alone never authorizes an update: the store
        # must independently reject obsolete revisions.
        with pytest.raises(ValueError, match="Stale"):
            apply_update(
                conn,
                profile_id=profile,
                source_id=source,
                expected_revision=1,
                entries=[M3UEntry("C", "https://stream.example/c")],
            )
        conn.rollback()


def test_foreign_user_cannot_issue_receipt(tmp_path):
    path = tmp_path / "foreign.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user = db.ensure_default_user(conn)
        profile = db.ensure_default_profile(conn, user_id=user)
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://catalog.example/list.m3u",
            entries=[M3UEntry("A", "https://stream.example/a")],
        )
        conn.commit()

        with pytest.raises(ValueError, match="Profile"):
            receipts.issue(
                conn,
                user_id=user + 1000,
                profile_id=profile,
                source_id=source,
                revision=1,
                session_token="session-a",
                data=b"payload",
            )
