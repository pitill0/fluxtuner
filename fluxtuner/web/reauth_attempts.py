# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Persistent admission control for recovery-code reauthentication."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 5 * 60
MAX_PENDING_ATTEMPTS = 2
PENDING_LEASE_SECONDS = 2 * 60
PENDING_CLEANUP_GRACE_SECONDS = 5 * 60
MAX_CLIENT_KEY_LENGTH = 200


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _client_key(value: str) -> str:
    return (value.strip() or "unknown")[:MAX_CLIENT_KEY_LENGTH]


def reserve_attempt(
    conn: sqlite3.Connection,
    user_id: int,
    client_key: str,
    *,
    now: datetime | None = None,
) -> int | None:
    """Atomically admit an attempt, or return None when limited.

    The transaction is committed before returning; callers must perform
    password verification only after this function returns.
    """
    current = now or datetime.now(UTC)
    cutoff = _timestamp(current - timedelta(seconds=FAILED_WINDOW_SECONDS))
    timestamp = _timestamp(current)
    lease_end = _timestamp(current + timedelta(seconds=PENDING_LEASE_SECONDS))
    key = _client_key(client_key)

    if conn.in_transaction:
        raise RuntimeError("Reauthentication admission requires an idle connection.")

    conn.execute("BEGIN IMMEDIATE")
    try:
        failed = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM web_reauth_attempts
            WHERE user_id = ?
              AND status = 'failed' AND attempted_at >= ?
            """,
            (user_id, cutoff),
        ).fetchone()

        pending = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM web_reauth_attempts
            WHERE user_id = ?
              AND status = 'pending' AND expires_at > ?
            """,
            (user_id, timestamp),
        ).fetchone()

        failed_count = int(failed["count"])
        pending_count = int(pending["count"])

        if (
            failed_count + pending_count >= MAX_FAILED_ATTEMPTS
            or pending_count >= MAX_PENDING_ATTEMPTS
        ):
            conn.commit()
            return None

        cursor = conn.execute(
            """
            INSERT INTO web_reauth_attempts (
                user_id, client_key, status, attempted_at, expires_at
            )
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (user_id, key, timestamp, lease_end),
        )
        attempt_id = cursor.lastrowid
        if attempt_id is None:
            raise RuntimeError(
                "SQLite did not return a reauthentication attempt ID."
            )
        conn.commit()
        return attempt_id
    except Exception:
        conn.rollback()
        raise


def finish_attempt(
    conn: sqlite3.Connection,
    attempt_id: int,
    *,
    success: bool,
    now: datetime | None = None,
) -> bool:
    """Finalize a live reservation. Expired reservations cannot succeed.

    Caller owns the surrounding transaction, allowing successful
    completion to be committed atomically with recovery-code rotation.
    """
    current = now or datetime.now(UTC)
    timestamp = _timestamp(current)
    status = "succeeded" if success else "failed"

    # Only a live lease may authorize a successful operation.
    # A failed verification must still count even if Argon2 outlasted
    # the lease; otherwise expensive requests could escape throttling.
    expiry_guard = "AND expires_at > ?" if success else ""
    parameters: tuple[str | int, ...] = (
        status,
        timestamp,
        _timestamp(current + timedelta(seconds=FAILED_WINDOW_SECONDS)),
        attempt_id,
    )
    if success:
        parameters += (timestamp,)

    cursor = conn.execute(
        f"""
        UPDATE web_reauth_attempts
        SET status = ?, attempted_at = ?, expires_at = ?
        WHERE id = ? AND status = 'pending' {expiry_guard}
        """,
        parameters,
    )
    return cursor.rowcount == 1



def purge_old_reauth_attempts(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    window_seconds: int = 24 * 60 * 60,
) -> int:
    """Remove expired reservations and completed attempts beyond retention."""
    if window_seconds < FAILED_WINDOW_SECONDS:
        raise ValueError(
            "Reauthentication retention cannot be shorter than "
            "the failed-attempt window."
        )

    current = now or datetime.now(UTC)
    pending_cutoff = _timestamp(
        current - timedelta(seconds=PENDING_CLEANUP_GRACE_SECONDS)
    )
    cutoff = _timestamp(current - timedelta(seconds=window_seconds))

    cursor = conn.execute(
        """
        DELETE FROM web_reauth_attempts
        WHERE (status = 'pending' AND expires_at <= ?)
           OR (
               status IN ('failed', 'succeeded')
               AND attempted_at < ?
           )
        """,
        (pending_cutoff, cutoff),
    )
    return cursor.rowcount
