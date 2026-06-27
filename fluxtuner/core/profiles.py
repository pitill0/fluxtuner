from __future__ import annotations

import sqlite3
from typing import Any

from fluxtuner import config
from fluxtuner.core import db

ACTIVE_PROFILE_CONFIG_KEY = "active_profile"


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
        return db.get_or_create_profile(conn, profile_name, user_id=user_id)

    if user_id is not None:
        return db.ensure_default_profile(conn, user_id=user_id)

    return None


def load_profiles() -> list[dict[str, Any]]:
    """Return known profiles from the default FluxTuner database."""
    db.init_db()

    with db.connect() as conn:
        return db.list_profiles(conn)


def get_active_profile_name() -> str | None:
    """Return the persisted active profile name, if configured."""
    value = config.get_config_value(ACTIVE_PROFILE_CONFIG_KEY)
    if not isinstance(value, str):
        return None

    normalized = db.normalize_profile_name(value)
    return normalized or None


def set_active_profile_name(profile_name: str) -> str:
    """Persist the active profile name and return its normalized value."""
    normalized = db.normalize_profile_name(profile_name)
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
        return db.normalize_profile_name(profile_name)

    return get_active_profile_name()
