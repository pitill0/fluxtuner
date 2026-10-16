# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

RECOVERY_CODE_COUNT = 8
RECOVERY_CODE_PREFIX = "FT-RCV"
MAX_FAILED_RECOVERY_ATTEMPTS = 5
RECOVERY_RATE_LIMIT_WINDOW_SECONDS = 60 * 5
MAX_CLIENT_KEY_LENGTH = 200


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_recovery_code() -> str:
    secret = secrets.token_hex(16).upper()
    grouped = "-".join(secret[index : index + 8] for index in range(0, len(secret), 8))
    return f"{RECOVERY_CODE_PREFIX}-{grouped}"


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def bootstrap_recovery_codes(
    conn: sqlite3.Connection,
    user_id: int,
) -> list[str] | None:
    """Create the first recovery-code set for a user exactly once."""
    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    created_at = utc_now()
    inserted = 0

    conn.execute("SAVEPOINT recovery_codes_bootstrap")
    try:
        for slot, code in enumerate(codes, start=1):
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO web_recovery_codes (
                    user_id,
                    slot,
                    code_hash,
                    created_at,
                    used_at
                )
                VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    user_id,
                    slot,
                    hash_recovery_code(code),
                    created_at,
                ),
            )
            inserted += int(cursor.rowcount)

        if inserted != RECOVERY_CODE_COUNT:
            conn.execute("ROLLBACK TO SAVEPOINT recovery_codes_bootstrap")
            conn.execute("RELEASE SAVEPOINT recovery_codes_bootstrap")
            return None

        conn.execute("RELEASE SAVEPOINT recovery_codes_bootstrap")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT recovery_codes_bootstrap")
        conn.execute("RELEASE SAVEPOINT recovery_codes_bootstrap")
        raise

    return codes


def consume_recovery_code(
    conn: sqlite3.Connection,
    username: str,
    code: str,
) -> int | None:
    """Atomically claim one unused recovery code for an active approved user."""
    code_hash = hash_recovery_code(code)
    row = conn.execute(
        """
        SELECT
            c.id,
            c.user_id
        FROM web_recovery_codes c
        JOIN users u ON u.id = c.user_id
        WHERE lower(u.username) = lower(?)
          AND u.is_active = 1
          AND u.approval_status = 'approved'
          AND c.code_hash = ?
          AND c.used_at IS NULL
        LIMIT 1
        """,
        (username.strip(), code_hash),
    ).fetchone()

    if row is None:
        return None

    cursor = conn.execute(
        """
        UPDATE web_recovery_codes
        SET used_at = ?
        WHERE id = ?
          AND used_at IS NULL
        """,
        (utc_now(), int(row["id"])),
    )
    if cursor.rowcount != 1:
        return None

    return int(row["user_id"])


def invalidate_recovery_codes(
    conn: sqlite3.Connection,
    user_id: int,
) -> int:
    """Invalidate every recovery code currently issued to a user."""
    cursor = conn.execute(
        "DELETE FROM web_recovery_codes WHERE user_id = ?",
        (user_id,),
    )
    return int(cursor.rowcount)


def rotate_recovery_codes(
    conn: sqlite3.Connection,
    user_id: int,
) -> list[str]:
    """Replace every recovery code for a user with a fresh set."""
    conn.execute(
        "DELETE FROM web_recovery_codes WHERE user_id = ?",
        (user_id,),
    )

    codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    created_at = utc_now()

    for slot, code in enumerate(codes, start=1):
        conn.execute(
            """
            INSERT INTO web_recovery_codes (
                user_id,
                slot,
                code_hash,
                created_at,
                used_at
            )
            VALUES (?, ?, ?, ?, NULL)
            """,
            (
                user_id,
                slot,
                hash_recovery_code(code),
                created_at,
            ),
        )

    return codes


def normalize_recovery_username(username: str) -> str:
    return username.strip().casefold()


def normalize_client_key(client_key: str) -> str:
    clean_key = client_key.strip() or "unknown"
    return clean_key[:MAX_CLIENT_KEY_LENGTH]


def record_recovery_attempt(
    conn: sqlite3.Connection,
    username: str,
    client_key: str,
    *,
    success: bool,
    now: datetime | None = None,
) -> None:
    normalized_username = normalize_recovery_username(username)
    if not normalized_username:
        return

    current_time = now or datetime.now(UTC)
    conn.execute(
        """
        INSERT INTO web_recovery_attempts (
            normalized_username,
            client_key,
            success,
            attempted_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            normalized_username,
            normalize_client_key(client_key),
            int(success),
            current_time.isoformat(),
        ),
    )


def count_recent_failed_recovery_attempts(
    conn: sqlite3.Connection,
    username: str,
    client_key: str,
    *,
    now: datetime | None = None,
    window_seconds: int = RECOVERY_RATE_LIMIT_WINDOW_SECONDS,
) -> int:
    normalized_username = normalize_recovery_username(username)
    if not normalized_username:
        return 0

    current_time = now or datetime.now(UTC)
    since = current_time - timedelta(seconds=window_seconds)

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM web_recovery_attempts
        WHERE normalized_username = ?
          AND client_key = ?
          AND success = 0
          AND attempted_at >= ?
        """,
        (
            normalized_username,
            normalize_client_key(client_key),
            since.isoformat(),
        ),
    ).fetchone()

    return int(row["count"] if row is not None else 0)


def is_recovery_rate_limited(
    conn: sqlite3.Connection,
    username: str,
    client_key: str,
    *,
    now: datetime | None = None,
) -> bool:
    return (
        count_recent_failed_recovery_attempts(
            conn,
            username,
            client_key,
            now=now,
        )
        >= MAX_FAILED_RECOVERY_ATTEMPTS
    )


def purge_old_recovery_attempts(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    window_seconds: int = RECOVERY_RATE_LIMIT_WINDOW_SECONDS,
) -> int:
    current_time = now or datetime.now(UTC)
    cutoff = current_time - timedelta(seconds=window_seconds)

    cursor = conn.execute(
        """
        DELETE FROM web_recovery_attempts
        WHERE attempted_at < ?
        """,
        (cutoff.isoformat(),),
    )
    return int(cursor.rowcount)
