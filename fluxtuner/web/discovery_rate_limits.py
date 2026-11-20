"""Bounded, multi-worker-safe admission control for discovery redemptions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60


def admit_redemption(
    conn: sqlite3.Connection, *, user_id: int, now: datetime | None = None
) -> bool:
    """Reserve one attempt atomically; at most one SQLite row per user.

    The transaction commits before returning. A rejected attempt cannot grow
    storage, and concurrent requests across workers share the same counter.
    """
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Invalid user.")
    if conn.in_transaction:
        raise RuntimeError("Discovery admission requires an idle connection.")
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Read wall time *after* acquiring the write lock: workers may be
        # scheduled in a different order than their initial timestamps.
        current = (now or datetime.now(UTC)).astimezone(UTC)
        current_text = current.isoformat()
        row = conn.execute(
            "SELECT window_start, attempts FROM web_discovery_rate_limits WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is not None:
            try:
                start = datetime.fromisoformat(str(row["window_start"]))
            except ValueError:
                start = current - timedelta(seconds=WINDOW_SECONDS)
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            age = (current - start.astimezone(UTC)).total_seconds()
            # A backward wall-clock adjustment must not replenish a window.
            if age < WINDOW_SECONDS:
                if int(row["attempts"]) >= MAX_ATTEMPTS:
                    conn.commit()
                    return False
                conn.execute(
                    "UPDATE web_discovery_rate_limits SET attempts = attempts + 1 WHERE user_id = ?",
                    (user_id,),
                )
                conn.commit()
                return True

        conn.execute(
            """
            INSERT INTO web_discovery_rate_limits (user_id, window_start, attempts)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                window_start = excluded.window_start,
                attempts = excluded.attempts
            """,
            (user_id, current_text),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def purge_stale_limits(conn: sqlite3.Connection, *, now: datetime | None = None) -> int:
    """Remove counters that cannot affect the current rate-limit window."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    cutoff = (current - timedelta(seconds=WINDOW_SECONDS)).isoformat()
    return int(
        conn.execute(
            "DELETE FROM web_discovery_rate_limits WHERE window_start < ?", (cutoff,)
        ).rowcount
    )
