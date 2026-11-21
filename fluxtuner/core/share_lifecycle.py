# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Transactional expiration and snapshot disposal for recommendations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

DEFAULT_EXPIRY_BATCH = 100
MAX_EXPIRY_BATCH = 500
RESOLVED_RETENTION_DAYS = 30


def expire_shares(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    batch_size: int = DEFAULT_EXPIRY_BATCH,
) -> int:
    """Expire a bounded batch, clearing snapshots in the same transaction.

    This is an explicit maintenance operation, not a read-side side effect.
    The caller must provide a connection without an active transaction.
    An optional timestamp is intended for deterministic internal testing.
    """
    if conn.in_transaction:
        raise ValueError("Recommendation expiry requires an independent transaction.")

    if type(batch_size) is not int or not 1 <= batch_size <= MAX_EXPIRY_BATCH:
        raise ValueError("Invalid recommendation expiry batch size.")

    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Invalid recommendation timestamp.")

    current = (datetime.now(UTC) if now is None else now.astimezone(UTC)).isoformat()

    conn.execute("BEGIN IMMEDIATE")

    try:
        cursor = conn.execute(
            """
            UPDATE playlist_shares
            SET
                status = 'expired',
                snapshot_json = NULL,
                resolved_at = ?
            WHERE id IN (
                SELECT id
                FROM playlist_shares
                WHERE status = 'pending'
                  AND expires_at <= ?
                ORDER BY expires_at ASC, id ASC
                LIMIT ?
            )
              AND status = 'pending'
              AND expires_at <= ?
            """,
            (current, current, batch_size, current),
        )

        updated = cursor.rowcount

        conn.commit()
        return updated

    except Exception:
        conn.rollback()
        raise


def purge_old_shares(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    batch_size: int = DEFAULT_EXPIRY_BATCH,
) -> int:
    """Remove only resolved history older than 30 days, in bounded batches.

    For expired recommendations, retention begins at their actual expiry,
    not at a potentially delayed maintenance run. Pending items are untouched.
    """
    if conn.in_transaction:
        raise ValueError("Recommendation history purge requires an independent transaction.")
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_EXPIRY_BATCH:
        raise ValueError("Invalid recommendation history purge batch size.")
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Invalid recommendation history purge timestamp.")

    current = datetime.now(UTC) if now is None else now.astimezone(UTC)
    cutoff = (current - timedelta(days=RESOLVED_RETENTION_DAYS)).isoformat()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """
            DELETE FROM playlist_shares
            WHERE id IN (
                SELECT id FROM playlist_shares
                WHERE (
                    (status = 'expired' AND expires_at <= ?)
                    OR (status IN ('accepted', 'rejected') AND resolved_at <= ?)
                )
                ORDER BY COALESCE(resolved_at, expires_at), id
                LIMIT ?
            )
            AND (
                (status = 'expired' AND expires_at <= ?)
                OR (status IN ('accepted', 'rejected') AND resolved_at <= ?)
            )
            """,
            (cutoff, cutoff, batch_size, cutoff, cutoff),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
