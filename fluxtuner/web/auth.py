# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from fluxtuner.core import db

ARGON2_MEMORY_COST_KIB = 65536
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_BYTES = 1024

SESSION_TOKEN_BYTES = 32
DEFAULT_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60 * 5
MAX_CLIENT_KEY_LENGTH = 200
# Not a credential. This dummy Argon2id hash is used only to spend comparable
# verification work for missing/inactive users and reduce login timing leaks.
DUMMY_PASSWORD_HASH = (  # nosec B105
    "$argon2id$v=19$m=65536,t=3,p=4"
    "$wheXMWg7h8om/H0ubwpzpg"
    "$nFtO6iixRfJJCp7LILVWBgn3NZuneJy4Te1mw2GQ6MA"
)

_PASSWORD_HASHER = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST_KIB,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    type=Type.ID,
)


class PasswordValidationError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def encode_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def validate_password(password: str) -> None:
    if not password:
        raise PasswordValidationError("Password is required.")

    if not password.strip():
        raise PasswordValidationError("Password cannot be only whitespace.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    password_size = len(password.encode("utf-8"))
    if password_size > MAX_PASSWORD_BYTES:
        raise PasswordValidationError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )


def hash_password(password: str) -> str:
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False

    try:
        return _PASSWORD_HASHER.verify(password_hash, password) is True
    except (InvalidHashError, VerificationError, TypeError, ValueError):
        return False


def password_needs_rehash(password_hash: str | None) -> bool:
    if not password_hash:
        return True

    try:
        return _PASSWORD_HASHER.check_needs_rehash(password_hash)
    except (InvalidHashError, TypeError, ValueError):
        return True


def password_hash_parameters() -> dict[str, int | str]:
    return {
        "algorithm": "argon2id",
        "memory_cost_kib": ARGON2_MEMORY_COST_KIB,
        "time_cost": ARGON2_TIME_COST,
        "parallelism": ARGON2_PARALLELISM,
        "hash_len": ARGON2_HASH_LEN,
        "salt_len": ARGON2_SALT_LEN,
        "min_password_length": MIN_PASSWORD_LENGTH,
        "max_password_bytes": MAX_PASSWORD_BYTES,
    }


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    if not token:
        raise ValueError("Session token is required.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "token_hash": str(row["token_hash"]),
        "created_at": str(row["created_at"]),
        "last_seen_at": str(row["last_seen_at"]),
        "expires_at": str(row["expires_at"]),
        "revoked_at": str(row["revoked_at"]) if row["revoked_at"] is not None else None,
    }


def create_session(
    conn: Any,
    user_id: int,
    *,
    max_age_seconds: int = DEFAULT_SESSION_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> str:
    if max_age_seconds <= 0:
        raise ValueError("Session max age must be positive.")

    current_time = now or utc_now()
    expires_at = current_time + timedelta(seconds=max_age_seconds)
    token = generate_session_token()
    token_hash = hash_session_token(token)

    conn.execute(
        """
        INSERT INTO web_sessions (
            user_id,
            token_hash,
            created_at,
            last_seen_at,
            expires_at,
            revoked_at
        )
        VALUES (?, ?, ?, ?, ?, NULL)
        """,
        (
            user_id,
            token_hash,
            encode_datetime(current_time),
            encode_datetime(current_time),
            encode_datetime(expires_at),
        ),
    )
    return token


def get_session(
    conn: Any,
    token: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        token_hash = hash_session_token(token)
    except (TypeError, ValueError):
        return None

    row = conn.execute(
        """
        SELECT
            id,
            user_id,
            token_hash,
            created_at,
            last_seen_at,
            expires_at,
            revoked_at
        FROM web_sessions
        WHERE token_hash = ?
        """,
        (token_hash,),
    ).fetchone()

    if row is None:
        return None

    session = session_from_row(row)
    if session["revoked_at"] is not None:
        return None

    current_time = now or utc_now()
    if parse_datetime(str(session["expires_at"])) <= current_time:
        return None

    return session


def get_session_user(
    conn: Any,
    token: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    session = get_session(conn, token, now=now)
    if session is None:
        return None

    row = conn.execute(
        """
        SELECT
            id,
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        FROM users
        WHERE id = ? AND is_active = 1 AND approval_status = 'approved'
        """,
        (session["user_id"],),
    ).fetchone()

    if row is None:
        return None

    return db.user_from_row(row)


def revoke_session(
    conn: Any,
    token: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not token:
        return False

    try:
        token_hash = hash_session_token(token)
    except (TypeError, ValueError):
        return False

    current_time = now or utc_now()
    cursor = conn.execute(
        """
        UPDATE web_sessions
        SET revoked_at = ?
        WHERE token_hash = ? AND revoked_at IS NULL
        """,
        (encode_datetime(current_time), token_hash),
    )
    return cursor.rowcount > 0


def purge_expired_sessions(
    conn: Any,
    *,
    now: datetime | None = None,
) -> int:
    current_time = now or utc_now()
    cursor = conn.execute(
        """
        DELETE FROM web_sessions
        WHERE expires_at <= ?
        """,
        (encode_datetime(current_time),),
    )
    return int(cursor.rowcount)


def normalize_login_username(username: str) -> str:
    return username.strip().casefold()


def client_key_from_host(host: str | None) -> str:
    clean_host = (host or "unknown").strip() or "unknown"
    return clean_host[:MAX_CLIENT_KEY_LENGTH]


def record_login_attempt(
    conn: Any,
    username: str,
    client_key: str,
    *,
    success: bool,
    now: datetime | None = None,
) -> None:
    normalized_username = normalize_login_username(username)
    if not normalized_username:
        return

    current_time = now or utc_now()
    conn.execute(
        """
        INSERT INTO web_login_attempts (
            normalized_username,
            client_key,
            success,
            attempted_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            normalized_username,
            client_key_from_host(client_key),
            1 if success else 0,
            encode_datetime(current_time),
        ),
    )


def count_recent_failed_login_attempts(
    conn: Any,
    username: str,
    client_key: str,
    *,
    now: datetime | None = None,
    window_seconds: int = LOGIN_RATE_LIMIT_WINDOW_SECONDS,
) -> int:
    normalized_username = normalize_login_username(username)
    if not normalized_username:
        return 0

    current_time = now or utc_now()
    since = current_time - timedelta(seconds=window_seconds)
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM web_login_attempts
        WHERE normalized_username = ?
          AND client_key = ?
          AND success = 0
          AND attempted_at >= ?
        """,
        (
            normalized_username,
            client_key_from_host(client_key),
            encode_datetime(since),
        ),
    ).fetchone()
    return int(row["count"] if row is not None else 0)


def is_login_rate_limited(
    conn: Any,
    username: str,
    client_key: str,
    *,
    now: datetime | None = None,
) -> bool:
    return (
        count_recent_failed_login_attempts(
            conn,
            username,
            client_key,
            now=now,
        )
        >= MAX_FAILED_LOGIN_ATTEMPTS
    )


def purge_old_login_attempts(
    conn: Any,
    *,
    now: datetime | None = None,
    window_seconds: int = LOGIN_RATE_LIMIT_WINDOW_SECONDS,
) -> int:
    current_time = now or utc_now()
    cutoff = current_time - timedelta(seconds=window_seconds)
    cursor = conn.execute(
        """
        DELETE FROM web_login_attempts
        WHERE attempted_at < ?
        """,
        (encode_datetime(cutoff),),
    )
    return int(cursor.rowcount)
