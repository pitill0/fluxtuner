# SPDX-License-Identifier: MIT

from __future__ import annotations

import sqlite3
from typing import Any

from fluxtuner import config
from fluxtuner.core import db

ACTIVE_PROFILE_CONFIG_KEY = "active_profile"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def normalize_profile_name(name: str) -> str:
    """Normalize a profile name for storage and lookup."""
    return name.strip()


def profile_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a public profile dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "name": str(row["name"]),
        "display_name": str(row["display_name"] or row["name"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def get_profile_by_name(
    conn: sqlite3.Connection,
    name: str,
    *,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    """Return a profile by name for a user."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        return None

    resolved_user_id = user_id if user_id is not None else db.ensure_default_user(conn)

    row = conn.execute(
        """
        SELECT id, user_id, name, display_name, created_at, updated_at
        FROM profiles
        WHERE user_id = ? AND lower(name) = lower(?)
        """,
        (resolved_user_id, clean_name),
    ).fetchone()

    if row is None:
        return None

    return profile_from_row(row)


def get_or_create_profile(
    conn: sqlite3.Connection,
    name: str,
    *,
    display_name: str | None = None,
    user_id: int | None = None,
) -> int:
    """Return a profile id for a user, creating the profile if needed."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        raise ValueError("Profile name is required.")

    resolved_user_id = user_id if user_id is not None else db.ensure_default_user(conn)

    existing = get_profile_by_name(conn, clean_name, user_id=resolved_user_id)
    if existing is not None:
        return int(existing["id"])

    now = db.utc_now()
    clean_display_name = _clean_text(display_name) or clean_name

    cursor = conn.execute(
        """
        INSERT INTO profiles (
            user_id,
            name,
            display_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            resolved_user_id,
            clean_name,
            clean_display_name,
            now,
            now,
        ),
    )

    profile_id = cursor.lastrowid
    if profile_id is None:
        raise RuntimeError("Could not create profile.")

    return int(profile_id)


def list_profiles(
    conn: sqlite3.Connection,
    *,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return known profiles, optionally scoped to a user."""
    if user_id is None:
        rows = conn.execute(
            """
            SELECT id, user_id, name, display_name, created_at, updated_at
            FROM profiles
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, user_id, name, display_name, created_at, updated_at
            FROM profiles
            WHERE user_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (user_id,),
        ).fetchall()

    return [profile_from_row(row) for row in rows]


def resolve_profile_id(
    conn: sqlite3.Connection,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    user_id: int | None = None,
) -> int | None:
    """Resolve an optional profile selector to a profile id.

    Returning None preserves the existing default-profile behavior in db helpers
    for legacy callers that do not provide a user. When a user is provided, the
    user's default profile is resolved explicitly so user-scoped callers do not
    fall back to the global default profile.
    """
    if profile_id is not None:
        return profile_id

    if profile_name is not None:
        return get_or_create_profile(conn, profile_name, user_id=user_id)

    if user_id is not None:
        return db.ensure_default_profile(conn, user_id=user_id)

    return None


def load_profiles() -> list[dict[str, Any]]:
    """Return known profiles from the default FluxTuner database."""
    db.init_db()

    with db.connect() as conn:
        return list_profiles(conn)


def get_active_profile_name() -> str | None:
    """Return the persisted active profile name, if configured."""
    value = config.get_config_value(ACTIVE_PROFILE_CONFIG_KEY)
    if not isinstance(value, str):
        return None

    normalized = normalize_profile_name(value)
    return normalized or None


def set_active_profile_name(profile_name: str) -> str:
    """Persist the active profile name and return its normalized value."""
    normalized = normalize_profile_name(profile_name)
    config.set_config_value(ACTIVE_PROFILE_CONFIG_KEY, normalized)
    return normalized


def clear_active_profile_name() -> None:
    """Clear the persisted active profile name."""
    stored_config = config.load_config()
    stored_config.pop(ACTIVE_PROFILE_CONFIG_KEY, None)
    config.save_config(stored_config)


def resolve_effective_profile_name(
    profile_name: str | None = None,
) -> str | None:
    """Resolve an explicit profile name or the persisted active profile."""
    if profile_name is not None:
        return normalize_profile_name(profile_name)

    return get_active_profile_name()
