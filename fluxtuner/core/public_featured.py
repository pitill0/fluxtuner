# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Daily public station suggestion without exposing stream details."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, date, datetime
from urllib.parse import urlsplit


def _safe_directory_url(value: object) -> bool:
    """Conservatively exclude credential-bearing and parameterized stream URLs."""
    try:
        parsed = urlsplit(str(value or ""))
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and parsed.port != 0
        )
    except ValueError:
        return False


def public_featured_station(
    conn: sqlite3.Connection, *, as_of: date | None = None
) -> dict[str, object]:
    """Rotate over catalog stations and currently opted-in favorites, name only.

    An opt-in belongs to a favorite owned by an active, approved account.
    Revoking the last opt-in removes a custom station from the candidate set.
    A catalog identifier or opt-in alone is not a stream-health verification.
    """
    day = as_of if as_of is not None else datetime.now(UTC).date()
    chosen = featured_station_candidate(conn, as_of=day)
    if chosen is None:
        return {"station": None, "date_utc": day.isoformat()}
    return {"station": {"name": str(chosen["name"])}, "date_utc": day.isoformat()}


def featured_station_candidate(conn: sqlite3.Connection, *, as_of: date) -> sqlite3.Row | None:
    """Return the current eligible candidate for this UTC day, server-side only."""
    day = as_of
    if not isinstance(day, date) or isinstance(day, datetime):
        raise TypeError("as_of must be a date")

    rows = conn.execute(
        """
        SELECT s.id, s.station_key, s.name, s.url, s.url_resolved
        FROM stations AS s
        WHERE s.name IS NOT NULL AND trim(s.name) != ''
          AND (
              EXISTS (
                  SELECT 1
                  FROM public_station_opt_ins AS o
                  JOIN favorites AS f ON f.id = o.favorite_id
                  JOIN profiles AS p ON p.id = f.profile_id
                  JOIN users AS u ON u.id = p.user_id
                  WHERE f.station_id = s.id
                    AND u.is_active = 1
                    AND u.approval_status = 'approved'
              )
          )
        ORDER BY COALESCE(NULLIF(trim(s.stationuuid), ''), '') ASC, s.id ASC
        """
    ).fetchall()
    eligible = [
        row
        for row in rows
        if _safe_directory_url(row["url"]) and _safe_directory_url(row["url_resolved"])
    ]
    if not eligible:
        return None

    # Stable across workers and restarts; no global RNG state or playback counts.
    seed = hashlib.sha256(day.isoformat().encode("ascii")).digest()
    return eligible[int.from_bytes(seed, "big") % len(eligible)]
