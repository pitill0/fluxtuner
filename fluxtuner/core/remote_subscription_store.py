# SPDX-License-Identifier: MIT
"""Profile-owned subscription persistence. The caller controls commit."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from urllib.parse import urlsplit

from fluxtuner.core import db, station_provenance
from fluxtuner.core.m3u_import import M3UEntry, _validated_entries
from fluxtuner.core.remote_subscriptions import CatalogDiff, compare_catalogs


@contextmanager
def _atomic(conn: sqlite3.Connection) -> Iterator[None]:
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT remote_subscription")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT remote_subscription")
        conn.execute("RELEASE SAVEPOINT remote_subscription")
        raise
    else:
        conn.execute("RELEASE SAVEPOINT remote_subscription")


def _validated_snapshot(entries: Sequence[M3UEntry]) -> tuple[M3UEntry, ...]:
    accepted = _validated_entries(entries)
    if len(accepted) != len(entries):
        raise ValueError("Duplicate stream URL in catalog.")
    return accepted


def _catalog_url(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid remote catalog URL.")
    if len(value) > 2048 or any(ord(char) < 33 for char in value):
        raise ValueError("Invalid remote catalog URL.")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("Invalid remote catalog URL.")
    return value


def _owned(conn: sqlite3.Connection, *, profile_id: int, source_id: int) -> sqlite3.Row:
    station_provenance.get_source(
        conn, profile_id=profile_id, source_id=source_id,
    )
    row = conn.execute(
        """
        SELECT sub.*
        FROM remote_catalog_subscriptions AS sub
        JOIN station_sources AS src ON src.id = sub.source_id
        WHERE sub.source_id = ? AND sub.profile_id = ?
          AND src.profile_id = ? AND src.kind = 'remote_collection'
        """,
        (source_id, profile_id, profile_id),
    ).fetchone()
    if row is None:
        raise ValueError("Subscription unavailable for this profile.")
    return row


def get_subscription(
    conn: sqlite3.Connection, *, profile_id: int, source_id: int,
) -> dict:
    row = _owned(conn, profile_id=profile_id, source_id=source_id)
    return dict(row)


def list_subscriptions(
    conn: sqlite3.Connection, *, profile_id: int,
) -> list[dict]:
    station_provenance.list_sources(conn, profile_id=profile_id)
    return [
        dict(row) for row in conn.execute(
            """
            SELECT sub.*
            FROM remote_catalog_subscriptions AS sub
            JOIN station_sources AS src ON src.id = sub.source_id
            WHERE sub.profile_id = ? AND src.profile_id = ?
              AND src.kind = 'remote_collection'
            ORDER BY sub.source_id
            """,
            (profile_id, profile_id),
        ).fetchall()
    ]


def get_entries(
    conn: sqlite3.Connection, *, profile_id: int, source_id: int,
) -> tuple[M3UEntry, ...]:
    _owned(conn, profile_id=profile_id, source_id=source_id)
    rows = conn.execute(
        """
        SELECT name, stream_url FROM remote_catalog_entries
        WHERE source_id = ? ORDER BY position
        """,
        (source_id,),
    ).fetchall()
    return tuple(M3UEntry(row["name"], row["stream_url"]) for row in rows)


def preview_update(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    source_id: int,
    incoming: Sequence[M3UEntry],
) -> tuple[int, CatalogDiff]:
    row = _owned(conn, profile_id=profile_id, source_id=source_id)
    return int(row["revision"]), compare_catalogs(
        get_entries(conn, profile_id=profile_id, source_id=source_id),
        incoming,
    )


def _replace_entries(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    entries: tuple[M3UEntry, ...],
) -> None:
    now = db.utc_now()
    for entry in entries:
        conn.execute(
            """
            INSERT INTO stations (
                station_key, name, url, url_resolved,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '{}', ?, ?)
            ON CONFLICT(station_key) DO NOTHING
            """,
            (entry.url, entry.name, entry.url, entry.url, now, now),
        )

    conn.execute(
        "DELETE FROM remote_catalog_entries WHERE source_id = ?",
        (source_id,),
    )

    for position, entry in enumerate(entries):
        station = conn.execute(
            "SELECT id FROM stations WHERE station_key = ?",
            (entry.url,),
        ).fetchone()
        if station is None:
            raise RuntimeError("Station persistence failed.")
        station_id = int(station["id"])
        conn.execute(
            """
            INSERT INTO remote_catalog_entries
                (source_id, stream_url, name, position)
            VALUES (?, ?, ?, ?)
            """,
            (source_id, entry.url, entry.name, position),
        )
        conn.execute(
            """
            INSERT INTO station_source_memberships
                (source_id, station_id, first_observed_at, last_observed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_id, station_id)
            DO UPDATE SET last_observed_at = excluded.last_observed_at
            """,
            (source_id, station_id, now, now),
        )

    conn.execute(
        """
        DELETE FROM station_source_memberships
        WHERE source_id = ?
          AND station_id NOT IN (
              SELECT stations.id
              FROM stations
              JOIN remote_catalog_entries AS entries
                ON entries.stream_url = stations.station_key
              WHERE entries.source_id = ?
          )
        """,
        (source_id, source_id),
    )


def create_subscription(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    catalog_url: str,
    entries: Sequence[M3UEntry],
    display_name: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> int:
    url = _catalog_url(catalog_url)
    accepted = _validated_snapshot(entries)
    with _atomic(conn):
        source_id = station_provenance.create_source(
            conn,
            profile_id=profile_id,
            kind="remote_collection",
            display_name=display_name,
        )
        conn.execute(
            """
            INSERT INTO remote_catalog_subscriptions (
                source_id, profile_id, catalog_url,
                etag, last_modified, revision, refreshed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                source_id, profile_id, url, etag, last_modified,
                db.utc_now(), db.utc_now(),
            ),
        )
        _replace_entries(conn, source_id=source_id, entries=accepted)
    return source_id


def apply_update(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    source_id: int,
    expected_revision: int,
    entries: Sequence[M3UEntry],
    etag: str | None = None,
    last_modified: str | None = None,
) -> CatalogDiff:
    accepted = _validated_snapshot(entries)
    if type(expected_revision) is not int or expected_revision <= 0:
        raise ValueError("Invalid expected subscription revision.")

    with _atomic(conn):
        row = _owned(conn, profile_id=profile_id, source_id=source_id)
        if int(row["revision"]) != expected_revision:
            raise ValueError("Stale subscription preview.")
        diff = compare_catalogs(
            get_entries(conn, profile_id=profile_id, source_id=source_id),
            accepted,
        )
        _replace_entries(conn, source_id=source_id, entries=accepted)
        now = db.utc_now()
        conn.execute(
            """
            UPDATE remote_catalog_subscriptions
            SET revision = revision + 1, refreshed_at = ?,
                etag = ?, last_modified = ?
            WHERE source_id = ? AND profile_id = ?
            """,
            (now, etag, last_modified, source_id, profile_id),
        )
        conn.execute(
            "UPDATE station_sources SET updated_at = ? WHERE id = ?",
            (now, source_id),
        )
    return diff


def mark_not_modified(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    source_id: int,
    expected_revision: int,
) -> int:
    """A verified 304 retains the exact committed catalog and revision."""
    with _atomic(conn):
        row = _owned(conn, profile_id=profile_id, source_id=source_id)
        revision = int(row["revision"])
        if revision != expected_revision:
            raise ValueError("Stale subscription cache validation.")
        if not get_entries(conn, profile_id=profile_id, source_id=source_id):
            raise ValueError("No committed catalog for HTTP 304.")
        return revision


def delete_subscription(
    conn: sqlite3.Connection, *, profile_id: int, source_id: int,
) -> None:
    with _atomic(conn):
        _owned(conn, profile_id=profile_id, source_id=source_id)
        station_provenance.delete_source(
            conn, profile_id=profile_id, source_id=source_id,
        )
