# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from fluxtuner.core import db
from fluxtuner.core.artwork_cache import ArtworkCache
from fluxtuner.core.public_featured import featured_station_candidate, public_featured_station
from fluxtuner.core.public_trending import public_station_trends
from fluxtuner.web import guards as web_guards
from fluxtuner.web.discovery_rate_limits import admit_redemption
from fluxtuner.web.discovery_selection import issue_selection, verify_selection
from fluxtuner.web.routes.artwork import get_artwork_signing_key

router = APIRouter()
required_body = Body(...)


@router.get("/api/public/stats")
def public_stats() -> dict[str, Any]:
    with db.connect() as conn:
        return db.public_activity_stats(conn)


@router.get("/api/public/trending")
def public_trending(response: Response) -> dict[str, object]:
    """Expose only completed-day station names after aggregate activity checks."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    with db.connect() as conn:
        return public_station_trends(conn)


@router.get("/api/public/featured")
def public_featured(response: Response) -> dict[str, object]:
    """Provide a name-only, UTC-day rotating suggestion with live revocation."""
    response.headers["Cache-Control"] = "no-store"
    with db.connect() as conn:
        day = datetime.now(UTC).date()
        payload = public_featured_station(conn, as_of=day)
        if payload["station"] is not None:
            try:
                candidate = featured_station_candidate(conn, as_of=day)
                if candidate is not None:
                    payload["selection"] = issue_selection(candidate, get_artwork_signing_key())
            except (OSError, ValueError):
                # Signing is optional for displaying the public suggestion.
                pass
        return payload


@router.post("/api/public/featured/redeem")
def redeem_public_featured(
    request: Request,
    response: Response,
    payload: dict[str, object] = required_body,
) -> dict[str, object]:
    """Redeem one selection into the signed-in user's own default favorites."""
    response.headers["Cache-Control"] = "no-store"
    user = web_guards.require_authenticated_user(
        request, auth_required_detail="Authentication required."
    )
    web_guards.require_csrf(request, csrf_error_detail="CSRF token is missing or invalid.")
    user_id = int(user["id"])
    with db.connect() as conn:
        # Charge malformed and replayed requests too, before any token work.
        if not admit_redemption(conn, user_id=user_id):
            raise HTTPException(status_code=429, detail="Too many discovery attempts.")
        # Pin eligibility through insertion so consent cannot be revoked mid-redeem.
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = verify_selection(conn, payload.get("selection"), get_artwork_signing_key())
        except (OSError, ValueError):
            row = None
        if row is None:
            raise HTTPException(status_code=404, detail="Station unavailable.")
        profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
        now = db.utc_now()
        inserted = conn.execute(
            """
            INSERT OR IGNORE INTO favorites (profile_id, station_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (profile_id, int(row["id"]), now, now),
        )
        conn.commit()
        return {"added": inserted.rowcount > 0, "name": str(row["name"])}


@router.get("/api/public/stations/{station_id}/artwork", include_in_schema=False)
def public_station_artwork(station_id: int) -> Response:
    """Serve cached artwork only for a station currently in the public top three.

    A public request must never trigger a network lookup or expose favicon URLs.
    """
    if station_id < 1:
        raise HTTPException(status_code=404, detail="Artwork not available.")
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT favicon FROM stations
            WHERE id = ? AND id IN (
                SELECT history_entries.station_id
                FROM history_entries
                JOIN stations AS ranked ON ranked.id = history_entries.station_id
                GROUP BY history_entries.station_id
                ORDER BY SUM(history_entries.play_count) DESC,
                         MAX(history_entries.last_played_at) DESC,
                         COALESCE(NULLIF(trim(ranked.name), ''), 'Unknown station')
                             COLLATE NOCASE ASC
                LIMIT 3
            )
            """,
            (station_id,),
        ).fetchone()
    favicon = str(row["favicon"] or "").strip() if row else ""
    if not favicon:
        raise HTTPException(status_code=404, detail="Artwork not available.")
    cached = ArtworkCache().get(favicon)
    if cached is None:
        raise HTTPException(status_code=404, detail="Artwork not available.")
    data, mime_type = cached
    return Response(
        content=data,
        media_type=mime_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
