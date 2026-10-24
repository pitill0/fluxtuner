# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""One-use, profile-scoped attestations for Web remote station downloads."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

from fluxtuner.core import db
from fluxtuner.core.profiles import get_profile_by_name

RECEIPT_LIFETIME = timedelta(minutes=15)


def utc_now():
    return datetime.now(UTC)


def encode_datetime(value):
    return value.isoformat()


MAX_TOKEN_LENGTH = 128


def _digest(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def issue_for_default_profile(*, user_id: int, session_token: str, data: bytes) -> str:
    """Compatibility wrapper for callers using the default profile."""
    return issue_for_profile(
        user_id=user_id, profile_name=None, session_token=session_token, data=data
    )


def issue_for_profile(
    *, user_id: int, profile_name: str | None, session_token: str, data: bytes
) -> str:
    """Persist attestation; never retain URL, raw session token or playlist bytes."""
    if not session_token or not data:
        raise ValueError("Authenticated snapshot required.")
    token = secrets.token_urlsafe(32)
    now = utc_now()
    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile = get_profile_by_name(
            conn, db.DEFAULT_PROFILE_NAME if profile_name is None else profile_name, user_id=user_id
        )
        if profile is None:
            raise ValueError("The selected profile is unavailable.")
        conn.execute(
            "DELETE FROM remote_import_receipts WHERE expires_at < ?",
            (encode_datetime(now),),
        )
        conn.execute(
            "INSERT INTO remote_import_receipts "
            "(token_hash, user_id, profile_id, session_hash, payload_hash, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                _digest(token),
                user_id,
                int(profile["id"]),
                _digest(session_token),
                _digest(data),
                encode_datetime(now + RECEIPT_LIFETIME),
            ),
        )
        conn.commit()
    return token


def consume(
    conn: sqlite3.Connection,
    *,
    token: str,
    user_id: int,
    profile_id: int,
    session_token: str | None,
    data: bytes,
) -> None:
    """Consume only a matching unused receipt inside the caller transaction."""
    if not isinstance(token, str) or not 1 <= len(token) <= MAX_TOKEN_LENGTH:
        raise ValueError("Invalid remote collection receipt.")
    if not session_token:
        raise ValueError("Invalid remote collection receipt.")
    now = encode_datetime(utc_now())
    cursor = conn.execute(
        "UPDATE remote_import_receipts SET consumed_at = ? "
        "WHERE token_hash = ? AND user_id = ? AND profile_id = ? "
        "AND session_hash = ? AND payload_hash = ? "
        "AND consumed_at IS NULL AND expires_at > ?",
        (now, _digest(token), user_id, profile_id, _digest(session_token), _digest(data), now),
    )
    if cursor.rowcount != 1:
        raise ValueError("Invalid or expired remote collection receipt.")
