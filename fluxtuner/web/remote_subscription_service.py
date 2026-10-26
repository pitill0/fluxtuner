# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Profile-bound refresh preview and transactional confirmation."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict
from typing import Any

from fluxtuner.core import db
from fluxtuner.core.m3u_import import parse_station_collection
from fluxtuner.core.profiles import get_profile_by_name
from fluxtuner.core.remote_subscription_store import (
    apply_update,
    create_subscription,
    preview_update,
)
from fluxtuner.web import remote_subscription_receipts as receipts


def _profile_id(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_name: str | None,
) -> int:
    name = db.DEFAULT_PROFILE_NAME if profile_name is None else profile_name
    profile = get_profile_by_name(conn, name, user_id=user_id)
    if profile is None:
        raise LookupError("Selected profile unavailable.")
    return int(profile["id"])


def preview_refresh(
    data: bytes,
    *,
    user_id: int,
    profile_name: str | None,
    source_id: int,
    session_token: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> dict[str, Any]:
    """Preview a verified download and bind its bytes to one-use consent."""
    parsed = parse_station_collection(data)
    if not parsed.entries:
        raise ValueError("Remote catalog has no valid stations.")
    if parsed.issues:
        raise ValueError("Remote catalog contains invalid entries.")

    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(
            conn, user_id=user_id, profile_name=profile_name,
        )
        revision, diff = preview_update(
            conn,
            profile_id=profile_id,
            source_id=source_id,
            incoming=parsed.entries,
        )
        token = receipts.issue(
            conn,
            user_id=user_id,
            profile_id=profile_id,
            source_id=source_id,
            revision=revision,
            session_token=session_token,
            data=data,
            etag=etag,
            last_modified=last_modified,
        )
        conn.commit()

    return {
        "source_id": source_id,
        "revision": revision,
        "receipt": token,
        "added": [asdict(item) for item in diff.added],
        "removed": [asdict(item) for item in diff.removed],
        "changed": [asdict(item) for item in diff.changed],
        "unchanged": diff.unchanged,
    }


def confirm_refresh(
    data: bytes,
    *,
    user_id: int,
    profile_name: str | None,
    source_id: int,
    revision: int,
    receipt: str,
    session_token: str | None,
) -> dict[str, Any]:
    """Consume a precise receipt and replace a catalog atomically."""
    parsed = parse_station_collection(data)
    if not parsed.entries:
        raise ValueError("Remote catalog has no valid stations.")
    if parsed.issues:
        raise ValueError("Remote catalog contains invalid entries.")

    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(
            conn, user_id=user_id, profile_name=profile_name,
        )
        receipts.consume(
            conn,
            token=receipt,
            user_id=user_id,
            profile_id=profile_id,
            source_id=source_id,
            revision=revision,
            session_token=session_token,
            data=data,
        )
        diff = apply_update(
            conn,
            profile_id=profile_id,
            source_id=source_id,
            expected_revision=revision,
            entries=parsed.entries,
        )
        conn.commit()

    return {
        "status": "ok",
        "source_id": source_id,
        "revision": revision + 1,
        "added": len(diff.added),
        "removed": len(diff.removed),
        "changed": len(diff.changed),
        "unchanged": diff.unchanged,
    }



def confirm_stored_refresh(
    *,
    user_id: int,
    profile_name: str | None,
    source_id: int,
    revision: int,
    receipt: str,
    session_token: str | None,
) -> dict[str, Any]:
    """Apply exclusively the server-stored, authorized snapshot.

    The browser supplies only the receipt and expected revision.
    Receipt consumption and catalog update share the same transaction.
    """
    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(
            conn, user_id=user_id, profile_name=profile_name,
        )
        data, pending_etag, pending_last_modified = (
            receipts.snapshot_and_validators_for_confirmation(
                conn,
            token=receipt,
            user_id=user_id,
            profile_id=profile_id,
            source_id=source_id,
            revision=revision,
                session_token=session_token,
            )
        )
        parsed = parse_station_collection(data)
        if not parsed.entries or parsed.issues:
            raise ValueError("Invalid stored remote catalog.")

        receipts.consume(
            conn,
            token=receipt,
            user_id=user_id,
            profile_id=profile_id,
            source_id=source_id,
            revision=revision,
            session_token=session_token,
            data=data,
        )
        diff = apply_update(
            conn,
            profile_id=profile_id,
            source_id=source_id,
            expected_revision=revision,
            entries=parsed.entries,
            etag=pending_etag,
            last_modified=pending_last_modified,
        )
        conn.commit()

    return {
        "status": "ok",
        "source_id": source_id,
        "revision": revision + 1,
        "added": len(diff.added),
        "removed": len(diff.removed),
        "changed": len(diff.changed),
        "unchanged": diff.unchanged,
    }



def create_from_snapshot(
    data: bytes,
    *,
    user_id: int,
    profile_name: str | None,
    catalog_url: str,
    display_name: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> dict[str, Any]:
    """Persist a previously protected-downloaded, validated catalog.

    This function does no network I/O; its HTTP caller must obtain data
    using the existing protected remote collection transport.
    """
    parsed = parse_station_collection(data)
    if not parsed.entries or parsed.issues:
        raise ValueError("Remote catalog has no complete valid collection.")

    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(
            conn, user_id=user_id, profile_name=profile_name,
        )
        source_id = create_subscription(
            conn,
            profile_id=profile_id,
            catalog_url=catalog_url,
            entries=parsed.entries,
            display_name=display_name,
            etag=etag,
            last_modified=last_modified,
        )
        conn.commit()

    return {
        "status": "ok",
        "source_id": source_id,
        "revision": 1,
        "stations": len(parsed.entries),
    }
