# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Short-lived, opaque public discovery selections without server-side sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import sqlite3
from datetime import UTC, datetime

from fluxtuner.core.public_featured import featured_station_candidate

TTL_SECONDS = 15 * 60
_DOMAIN = b"fluxtuner-discovery-selection-v1\x00"


def _signature(row: sqlite3.Row, issued: int, key: bytes) -> str:
    # Length-prefix every field so a changed URL/key cannot collide by concatenation.
    fields = (str(issued), str(row["station_key"]), str(row["url"]), str(row["url_resolved"]))
    message = _DOMAIN + b"".join(
        len(part.encode("utf-8")).to_bytes(4, "big") + part.encode("utf-8") for part in fields
    )
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def issue_selection(row: sqlite3.Row, key: bytes, *, now: datetime | None = None) -> str:
    """Mint an opaque reference: no station id, URL, or account identifier."""
    if len(key) < 32:
        raise ValueError("Discovery signing key too short.")
    issued = int((now or datetime.now(UTC)).timestamp())
    return f"v1.{issued}.{_signature(row, issued, key)}"


def verify_selection(
    conn: sqlite3.Connection,
    reference: object,
    key: bytes,
    *,
    now: datetime | None = None,
) -> sqlite3.Row | None:
    """Recheck today's original candidate and its *current* public eligibility."""
    if not isinstance(reference, str) or len(reference) > 96 or len(reference) < 50:
        return None
    parts = reference.split(".")
    if len(parts) != 3 or parts[0] != "v1" or not parts[1].isdigit():
        return None
    try:
        issued = int(parts[1])
        current = now or datetime.now(UTC)
        age = current.timestamp() - issued
        if age < 0 or age > TTL_SECONDS:
            return None
        issue_day = datetime.fromtimestamp(issued, UTC).date()
    except (OverflowError, OSError, ValueError):
        return None
    row = featured_station_candidate(conn, as_of=issue_day)
    if row is None:
        return None
    expected = _signature(row, issued, key)
    if not hmac.compare_digest(parts[2], expected):
        return None
    return row


def revalidate_selection_station(
    conn: sqlite3.Connection, selected: sqlite3.Row
) -> sqlite3.Row | None:
    """Recheck selected identity, URL safety and live opt-in under the writer lock.

    The expensive daily-candidate scan and HMAC check happen beforehand.
    This query is intentionally restricted to the previously signed station.
    """
    row = conn.execute(
        """
        SELECT s.id, s.station_key, s.name, s.url, s.url_resolved
        FROM stations AS s
        WHERE s.id = ?
          AND s.station_key = ?
          AND s.url = ?
          AND s.url_resolved = ?
          AND s.name IS NOT NULL
          AND trim(s.name) != ''
          AND EXISTS (
              SELECT 1
              FROM public_station_opt_ins AS o
              JOIN favorites AS f ON f.id = o.favorite_id
              JOIN profiles AS p ON p.id = f.profile_id
              JOIN users AS u ON u.id = p.user_id
              WHERE f.station_id = s.id
                AND u.is_active = 1
                AND u.approval_status = 'approved'
          )
        """,
        (
            int(selected["id"]),
            str(selected["station_key"]),
            str(selected["url"]),
            str(selected["url_resolved"]),
        ),
    ).fetchone()
    if row is None:
        return None

    from fluxtuner.core.public_station_visibility import public_station_urls_safe

    if not public_station_urls_safe(row["url"], row["url_resolved"]):
        return None
    return row
