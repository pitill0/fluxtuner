# SPDX-License-Identifier: MIT
"""Persisted Web remote import receipts: integrity, isolation and one-time use."""

import pytest

from fluxtuner.core import db
from fluxtuner.core.profiles import get_or_create_profile
from fluxtuner.core.station_provenance import list_sources
from fluxtuner.web import m3u_import
from fluxtuner.web import remote_import_receipts as receipts

DATA = b"#EXTM3U\n#EXTINF:-1,Radio\nhttps://radio.example/live\n"


@pytest.fixture
def library(web_library):
    _client, users = web_library
    alice_id, first = users["alice"]
    bob_id, _bob_profile = users["bob"]
    with db.connect() as conn:
        second = get_or_create_profile(conn, "Second", user_id=alice_id)
        conn.commit()
    return first, second, alice_id, bob_id


def _import(token, *, user, profile=None, session="session-one", data=DATA):
    return m3u_import.import_payload(
        data,
        user_id=user,
        profile_name=profile,
        playlist_name="Imported",
        existing=False,
        remote_receipt=token,
        session_token=session,
    )


def test_valid_receipt_creates_remote_source_once(library):
    first, _, alice, _ = library
    token = receipts.issue_for_default_profile(
        user_id=alice, session_token="session-one", data=DATA
    )
    result = _import(token, user=alice)
    assert result["added_to_playlist"] == 1
    with db.connect() as conn:
        sources = list_sources(conn, profile_id=first)
        assert len(sources) == 1
        assert sources[0]["kind"] == "remote_collection"
        assert sources[0]["display_name"] is None
        stored = conn.execute(
            "SELECT token_hash, session_hash, payload_hash FROM remote_import_receipts"
        ).fetchone()
        assert token not in str(tuple(stored))
        assert "session-one" not in str(tuple(stored))
    with pytest.raises(ValueError, match="receipt"):
        m3u_import.import_payload(
            DATA,
            user_id=alice,
            profile_name=None,
            playlist_name="Replay attempt",
            existing=False,
            remote_receipt=token,
            session_token="session-one",
        )


@pytest.mark.parametrize("change", ["payload", "session", "profile", "user", "forged"])
def test_attestation_cannot_be_reassigned(library, change):
    first, _, alice, bob = library
    token = receipts.issue_for_default_profile(
        user_id=alice, session_token="session-one", data=DATA
    )
    args = {"user": alice}
    if change == "payload":
        args["data"] = DATA.replace(b"Radio", b"Altered")
    elif change == "session":
        args["session"] = "other-session"
    elif change == "profile":
        args["profile"] = "Second"
    elif change == "user":
        args["user"] = bob
    else:
        token = "fabricated-receipt"
    with pytest.raises(ValueError, match="receipt"):
        _import(token, **args)
    with db.connect() as conn:
        assert list_sources(conn, profile_id=first) == []
        assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0


def test_failure_after_claim_restores_unconsumed_receipt(library, monkeypatch):
    _, _, alice, _ = library
    token = receipts.issue_for_default_profile(
        user_id=alice, session_token="session-one", data=DATA
    )

    def fail(*args, **kwargs):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(m3u_import, "import_m3u_with_new_source", fail)
    with pytest.raises(RuntimeError, match="injected"):
        _import(token, user=alice)
    with db.connect() as conn:
        assert conn.execute("SELECT consumed_at FROM remote_import_receipts").fetchone()[0] is None


def test_explicit_profile_receipt_imports_only_into_selected_profile(library):
    first, second, alice, _ = library
    token = receipts.issue_for_profile(
        user_id=alice, profile_name="Second", session_token="session-one", data=DATA
    )
    result = m3u_import.import_payload(
        DATA,
        user_id=alice,
        profile_name="Second",
        playlist_name="Second import",
        existing=False,
        remote_receipt=token,
        session_token="session-one",
    )
    assert result["added_to_playlist"] == 1
    with db.connect() as conn:
        assert list_sources(conn, profile_id=first) == []
        assert [s["kind"] for s in list_sources(conn, profile_id=second)] == ["remote_collection"]


def test_explicit_profile_receipt_rejects_default_profile(library):
    first, second, alice, _ = library
    token = receipts.issue_for_profile(
        user_id=alice, profile_name="Second", session_token="session-one", data=DATA
    )
    with pytest.raises(ValueError, match="receipt"):
        _import(token, user=alice)
    with db.connect() as conn:
        assert list_sources(conn, profile_id=first) == []
        assert list_sources(conn, profile_id=second) == []


def test_explicit_profile_receipt_rejects_other_user(library):
    _first, second, alice, bob = library
    token = receipts.issue_for_profile(
        user_id=alice, profile_name="Second", session_token="session-one", data=DATA
    )
    with pytest.raises((ValueError, LookupError)):
        _import(token, user=bob, profile="Second")
    with db.connect() as conn:
        assert list_sources(conn, profile_id=second) == []


def test_receipt_expiration_rejected(library, monkeypatch):
    from datetime import timedelta

    first, _, alice, _ = library
    token = receipts.issue_for_profile(
        user_id=alice, profile_name=None, session_token="session-one", data=DATA
    )
    initial_now = receipts.utc_now()
    monkeypatch.setattr(
        receipts, "utc_now", lambda: initial_now + receipts.RECEIPT_LIFETIME + timedelta(seconds=5)
    )
    with pytest.raises(ValueError, match="receipt"):
        _import(token, user=alice)
    with db.connect() as conn:
        assert list_sources(conn, profile_id=first) == []
