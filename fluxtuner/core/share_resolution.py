# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Atomic, recipient-authorized recommendation acceptance and rejection."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.m3u_import import M3UEntry, import_m3u
from fluxtuner.core.share_snapshots import build_share_snapshot

MAX_SNAPSHOT_STORED_BYTES = 1_048_576


def _timestamp(now: datetime | None) -> str:
    if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
        raise ValueError("Invalid resolution timestamp.")
    return (datetime.now(UTC) if now is None else now.astimezone(UTC)).isoformat()


def _entries_from_snapshot(raw: str, kind: str) -> tuple[M3UEntry, ...]:
    """Fail closed if stored recommendation content is malformed."""
    if not isinstance(raw, str):
        raise ValueError("Invalid stored recommendation.")
    if len(raw.encode("utf-8")) > MAX_SNAPSHOT_STORED_BYTES:
        raise ValueError("Invalid stored recommendation.")

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Invalid stored recommendation.") from None

    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "stations"}
        or type(payload["version"]) is not int
        or payload["version"] != 1
        or not isinstance(payload["stations"], list)
    ):
        raise ValueError("Invalid stored recommendation.")

    entries: list[M3UEntry] = []
    for station in payload["stations"]:
        if (
            not isinstance(station, dict)
            or set(station) != {"name", "url"}
            or not isinstance(station["name"], str)
            or not isinstance(station["url"], str)
        ):
            raise ValueError("Invalid stored recommendation.")
        entries.append(M3UEntry(name=station["name"], url=station["url"]))

    try:
        canonical = build_share_snapshot(kind=kind, entries=entries)
    except ValueError:
        raise ValueError("Invalid stored recommendation.") from None

    # Validate the complete payload, not just its individual fields.
    if json.loads(canonical) != payload:
        raise ValueError("Invalid stored recommendation.")

    urls = [entry.url for entry in entries]
    if len(urls) != len(set(urls)):
        raise ValueError("Invalid stored recommendation.")

    return tuple(entries)


def _accept_into_profile(
    conn: sqlite3.Connection,
    *,
    recipient_user_id: int,
    destination_profile_id: int,
    destination_playlist_name: str | None,
    row: sqlite3.Row,
) -> dict[str, Any]:
    """Import one authorized snapshot within the caller's transaction."""
    profile = conn.execute(
        """
        SELECT 1 FROM profiles
        WHERE id = ? AND user_id = ?
        """,
        (destination_profile_id, recipient_user_id),
    ).fetchone()

    if profile is None:
        raise ValueError("Destination unavailable.")

    entries = _entries_from_snapshot(
        str(row["snapshot_json"]),
        str(row["kind"]),
    )

    if row["kind"] == "station":
        if destination_playlist_name is not None:
            raise ValueError("Station requires no playlist destination.")

        added = add_custom_station(
            conn,
            profile_id=destination_profile_id,
            name=entries[0].name,
            url=entries[0].url,
        )
        return {
            "added_favorites": int(added),
            "existing_favorites": int(not added),
        }

    if destination_playlist_name is not None:
        if not isinstance(destination_playlist_name, str):
            raise ValueError("Invalid playlist destination.")
        playlist_name = destination_playlist_name
    else:
        playlist_name = str(row["title"])

    if not playlist_name.strip():
        raise ValueError("Invalid playlist destination.")

    existing = conn.execute(
        """
        SELECT 1 FROM playlists
        WHERE profile_id = ?
          AND lower(name) = lower(?)
        """,
        (destination_profile_id, playlist_name.strip()),
    ).fetchone()

    if existing is not None:
        raise ValueError("Destination playlist already exists.")

    imported = import_m3u(
        conn,
        profile_id=destination_profile_id,
        playlist_name=playlist_name,
        entries=entries,
    )

    return {
        "playlist_name": playlist_name.strip(),
        **asdict(imported),
    }


def resolve_share(
    conn: sqlite3.Connection,
    *,
    recipient_user_id: int,
    share_id: int,
    action: str,
    destination_profile_id: int | None = None,
    destination_playlist_name: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Consume one recommendation without partial imports or double acceptance.

    Recipient identity must come from a trusted authenticated context.
    The supplied connection must not already own a transaction.
    """
    if conn.in_transaction:
        raise ValueError("Resolution requires an independent transaction.")

    if (
        type(recipient_user_id) is not int
        or recipient_user_id <= 0
        or type(share_id) is not int
        or share_id <= 0
    ):
        raise ValueError("Recommendation unavailable.")

    if action not in ("accept", "reject"):
        raise ValueError("Invalid recommendation action.")

    if action == "reject":
        if destination_profile_id is not None or destination_playlist_name is not None:
            raise ValueError("Reject does not accept a destination.")
    elif type(destination_profile_id) is not int or destination_profile_id <= 0:
        raise ValueError("Destination unavailable.")

    current = _timestamp(now)

    conn.execute("BEGIN IMMEDIATE")
    try:
        approved = conn.execute(
            """
            SELECT 1 FROM users
            WHERE id = ? AND is_active = 1
              AND approval_status = 'approved'
            """,
            (recipient_user_id,),
        ).fetchone()
        if approved is None:
            raise ValueError("Recommendation unavailable.")

        row = conn.execute(
            """
            SELECT id, kind, title, snapshot_json, expires_at
            FROM playlist_shares
            WHERE id = ?
              AND recipient_user_id = ?
              AND status = 'pending'
              AND expires_at > ?
            """,
            (share_id, recipient_user_id, current),
        ).fetchone()

        if row is None:
            raise ValueError("Recommendation unavailable.")

        result: dict[str, Any] = {
            "id": share_id,
            "status": "rejected" if action == "reject" else "accepted",
        }

        if action == "accept":
            if destination_profile_id is None:
                raise ValueError("Destination unavailable.")
            result.update(
                _accept_into_profile(
                    conn,
                    recipient_user_id=recipient_user_id,
                    destination_profile_id=destination_profile_id,
                    destination_playlist_name=destination_playlist_name,
                    row=row,
                )
            )

        updated = conn.execute(
            """
            UPDATE playlist_shares
            SET status = ?, snapshot_json = NULL, resolved_at = ?
            WHERE id = ?
              AND recipient_user_id = ?
              AND status = 'pending'
              AND expires_at > ?
            """,
            (
                result["status"],
                current,
                share_id,
                recipient_user_id,
                current,
            ),
        ).rowcount

        if updated != 1:
            raise ValueError("Recommendation unavailable.")

        conn.commit()
        return result

    except Exception:
        conn.rollback()
        raise
