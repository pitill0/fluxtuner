# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Daily public-directory station suggestion without exposing stream details."""

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
    """Rotate daily over catalog-identified stations; never publish URLs or IDs.

    Custom stations are excluded until an explicit owner-controlled opt-in exists.
    A catalog identifier alone is not a stream-health verification.
    """
    day = as_of if as_of is not None else datetime.now(UTC).date()
    if not isinstance(day, date) or isinstance(day, datetime):
        raise TypeError("as_of must be a date")

    rows = conn.execute(
        """
        SELECT stationuuid, name, url, url_resolved
        FROM stations
        WHERE stationuuid IS NOT NULL AND trim(stationuuid) != ''
          AND name IS NOT NULL AND trim(name) != ''
        ORDER BY stationuuid ASC, id ASC
        """
    ).fetchall()
    eligible = [
        row
        for row in rows
        if _safe_directory_url(row["url"]) and _safe_directory_url(row["url_resolved"])
    ]
    if not eligible:
        return {"station": None, "date_utc": day.isoformat()}

    # Stable across workers and restarts; no global RNG state or playback counts.
    seed = hashlib.sha256(day.isoformat().encode("ascii")).digest()
    chosen = eligible[int.from_bytes(seed, "big") % len(eligible)]
    return {"station": {"name": str(chosen["name"])}, "date_utc": day.isoformat()}
