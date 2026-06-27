from __future__ import annotations

import sqlite3

from fluxtuner.core import db


def resolve_profile_id(
    conn: sqlite3.Connection,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
) -> int | None:
    """Resolve an optional profile selector to a profile id.

    Returning None preserves the existing default-profile behavior in db helpers.
    """
    if profile_id is not None:
        return profile_id

    if profile_name is None:
        return None

    return db.get_or_create_profile(conn, profile_name)
