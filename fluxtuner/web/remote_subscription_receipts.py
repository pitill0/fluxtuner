# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""One-use authorization of exact remote subscription refresh snapshots."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from fluxtuner.core.remote_subscription_store import get_subscription

LIFETIME = timedelta(minutes=15)
MAX_TOKEN_LENGTH = 128


def _digest(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def issue(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    source_id: int,
    revision: int,
    session_token: str,
    data: bytes,
    etag: str | None = None,
    last_modified: str | None = None,
) -> str:
    """Issue a scoped receipt; caller controls the transaction."""
    if not session_token or not isinstance(data, bytes) or not data or len(data) > 1024 * 1024:
        raise ValueError("Session and bounded snapshot are required.")
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Invalid user.")
    if type(revision) is not int or revision <= 0:
        raise ValueError("Invalid revision.")

    profile = conn.execute(
        "SELECT 1 FROM profiles WHERE id = ? AND user_id = ?",
        (profile_id, user_id),
    ).fetchone()
    if profile is None:
        raise ValueError("Profile does not belong to the user.")

    subscription = get_subscription(
        conn,
        profile_id=profile_id,
        source_id=source_id,
    )
    if subscription["revision"] != revision:
        raise ValueError("Subscription revision has changed.")

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    conn.execute(
        "DELETE FROM remote_catalog_refresh_receipts WHERE expires_at < ?",
        (now.isoformat(),),
    )
    conn.execute(
        """
        DELETE FROM remote_catalog_refresh_receipts
        WHERE user_id = ? AND profile_id = ? AND source_id = ?
        """,
        (user_id, profile_id, source_id),
    )
    conn.execute(
        """
        INSERT INTO remote_catalog_refresh_receipts (
            token_hash, user_id, profile_id, source_id, revision,
            session_hash, payload_hash, snapshot_bytes,
            pending_etag, pending_last_modified, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _digest(token),
            user_id,
            profile_id,
            source_id,
            revision,
            _digest(session_token),
            _digest(data),
            data,
            etag,
            last_modified,
            (now + LIFETIME).isoformat(),
        ),
    )
    return token


def consume(
    conn: sqlite3.Connection,
    *,
    token: str,
    user_id: int,
    profile_id: int,
    source_id: int,
    revision: int,
    session_token: str | None,
    data: bytes,
) -> None:
    """Consume only the precise unexpired, unused preview receipt."""
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= MAX_TOKEN_LENGTH
        or not session_token
        or not isinstance(data, bytes)
        or not data
    ):
        raise ValueError("Invalid refresh receipt.")

    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        DELETE FROM remote_catalog_refresh_receipts
        WHERE token_hash = ?
          AND user_id = ?
          AND profile_id = ?
          AND source_id = ?
          AND revision = ?
          AND session_hash = ?
          AND payload_hash = ?
          AND consumed_at IS NULL
          AND expires_at > ?
        """,
        (
            _digest(token),
            user_id,
            profile_id,
            source_id,
            revision,
            _digest(session_token),
            _digest(data),
            now,
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Invalid or expired refresh receipt.")


def snapshot_and_validators_for_confirmation(
    conn: sqlite3.Connection,
    *,
    token: str,
    user_id: int,
    profile_id: int,
    source_id: int,
    revision: int,
    session_token: str | None,
) -> tuple[bytes, str | None, str | None]:
    """Retrieve an authorized snapshot and its pending validators."""
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= MAX_TOKEN_LENGTH
        or not session_token
        or type(revision) is not int
        or revision <= 0
    ):
        raise ValueError("Invalid refresh receipt.")

    row = conn.execute(
        """
        SELECT snapshot_bytes, pending_etag, pending_last_modified
        FROM remote_catalog_refresh_receipts
        WHERE token_hash = ?
          AND user_id = ?
          AND profile_id = ?
          AND source_id = ?
          AND revision = ?
          AND session_hash = ?
          AND consumed_at IS NULL
          AND expires_at > ?
        """,
        (
            _digest(token),
            user_id,
            profile_id,
            source_id,
            revision,
            _digest(session_token),
            datetime.now(UTC).isoformat(),
        ),
    ).fetchone()

    if row is None:
        raise ValueError("Invalid or expired refresh receipt.")

    data = bytes(row["snapshot_bytes"])
    if not data or len(data) > 1024 * 1024:
        raise ValueError("Invalid stored refresh snapshot.")
    return data, row["pending_etag"], row["pending_last_modified"]


def snapshot_for_confirmation(
    conn: sqlite3.Connection,
    *,
    token: str,
    user_id: int,
    profile_id: int,
    source_id: int,
    revision: int,
    session_token: str | None,
) -> bytes:
    """Backward-compatible exact-snapshot reader."""
    data, _, _ = snapshot_and_validators_for_confirmation(
        conn,
        token=token,
        user_id=user_id,
        profile_id=profile_id,
        source_id=source_id,
        revision=revision,
        session_token=session_token,
    )
    return data
