"""Manual station creation shared by FluxTuner interfaces."""

from __future__ import annotations

import sqlite3
import unicodedata
from urllib.parse import urlsplit

from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.stations import station_metadata

MAX_NAME_LENGTH = 200
MAX_URL_LENGTH = 2048


def _has_controls(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or _has_controls(name):
        raise ValueError("Station name contains invalid characters.")
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Station name is required.")
    if len(clean_name) > MAX_NAME_LENGTH:
        raise ValueError(f"Station name must not exceed {MAX_NAME_LENGTH} characters.")
    return clean_name


def _validate_url(url: str) -> str:
    if not isinstance(url, str) or _has_controls(url):
        raise ValueError("Stream URL contains invalid characters.")
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("Stream URL is required.")
    if len(clean_url) > MAX_URL_LENGTH:
        raise ValueError(f"Stream URL must not exceed {MAX_URL_LENGTH} characters.")
    if any(character.isspace() for character in clean_url) or "\\" in clean_url:
        raise ValueError("Stream URL contains invalid characters.")

    try:
        parsed = urlsplit(clean_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Stream URL is malformed.") from None

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("Stream URL must be an HTTP or HTTPS URL with a host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials in stream URLs are not supported.")
    if port is not None and port == 0:
        raise ValueError("Stream URL port is invalid.")

    # Preserve identity: no DNS, redirects, query rewriting or scheme changes.
    return clean_url


def add_custom_station(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    name: str,
    url: str,
    record_manual_provenance: bool = False,
) -> bool:
    """Add a manual station to one existing profile's favorites.

    Return False for an existing favorite without changing its metadata.
    Shared station records are inserted only when absent. The requested name
    belongs to the new profile favorite, so other profiles remain unchanged.
    The caller owns the transaction and must commit successful changes.
    """
    if type(record_manual_provenance) is not bool:
        raise ValueError("Invalid manual provenance option.")
    clean_name = _validate_name(name)
    clean_url = _validate_url(url)
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing profile is required.")
    if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone() is None:
        raise ValueError("The selected profile no longer exists.")

    # An outer transaction keeps RELEASE from committing the caller's work.
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT add_custom_station")
    try:
        now = db.utc_now()
        station = {
            "name": clean_name,
            "url": clean_url,
            "url_resolved": clean_url,
        }
        conn.execute(
            """
            INSERT INTO stations (
                station_key, name, url, url_resolved,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(station_key) DO NOTHING
            """,
            (
                clean_url,
                clean_name,
                clean_url,
                clean_url,
                station_metadata(station),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT id FROM stations WHERE station_key = ?", (clean_url,)).fetchone()
        if row is None:
            raise RuntimeError("Could not persist station.")

        cursor = conn.execute(
            """
            INSERT INTO favorites (
                profile_id, station_id, custom_name,
                favorite_tags_json, created_at, updated_at
            )
            VALUES (?, ?, ?, '[]', ?, ?)
            ON CONFLICT(profile_id, station_id) DO NOTHING
            """,
            (profile_id, int(row["id"]), clean_name, now, now),
        )
        added = cursor.rowcount > 0
        if added and record_manual_provenance:
            source_id = provenance.create_source(conn, profile_id=profile_id, kind="manual_entry")
            provenance.record_observation(
                conn,
                profile_id=profile_id,
                source_id=source_id,
                station_id=int(row["id"]),
            )
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT add_custom_station")
        conn.execute("RELEASE SAVEPOINT add_custom_station")
        raise
    conn.execute("RELEASE SAVEPOINT add_custom_station")
    return added
