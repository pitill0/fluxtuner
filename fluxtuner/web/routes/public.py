# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from fluxtuner.core import db
from fluxtuner.core.artwork_cache import ArtworkCache
from fluxtuner.core.public_featured import featured_station_candidate
from fluxtuner.core.public_genres import public_popular_genres
from fluxtuner.core.public_station_visibility import public_station_urls_safe
from fluxtuner.core.public_stats import public_top_station_rows
from fluxtuner.core.public_trending import public_station_trends
from fluxtuner.web import guards as web_guards
from fluxtuner.web.discovery_rate_limits import admit_redemption
from fluxtuner.web.discovery_selection import (
    issue_selection,
    revalidate_selection_station,
    verify_selection,
)
from fluxtuner.web.public_cache import public_response_cache
from fluxtuner.web.routes.artwork import get_artwork_signing_key

router = APIRouter()
required_body = Body(...)


@router.get("/api/public/stats")
def public_stats(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return public_response_cache.get("stats", db.public_activity_stats)


@router.get("/api/public/trending")
def public_trending(response: Response) -> dict[str, object]:
    """Expose only completed-day station names after aggregate activity checks."""
    response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    day = datetime.now(UTC).date().isoformat()
    return public_response_cache.get(f"trending:{day}", public_station_trends)


@router.get("/api/public/genres")
def public_genres(response: Response) -> dict[str, object]:
    """Publish recognized, sufficiently active genres without listener details."""
    response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    day = datetime.now(UTC).date().isoformat()
    return public_response_cache.get(f"genres:{day}", public_popular_genres)


@router.get("/api/public/featured")
def public_featured(response: Response) -> dict[str, object]:
    """Provide a name-only, UTC-day rotating suggestion with live revocation."""
    response.headers["Cache-Control"] = "no-store"
    day = datetime.now(UTC).date()
    cached = public_response_cache.get(
        f"featured:{day.isoformat()}",
        lambda conn: {"candidate": featured_station_candidate(conn, as_of=day)},
    )
    candidate = cached["candidate"]
    payload: dict[str, object] = {
        "station": {"name": str(candidate["name"])} if candidate is not None else None,
        "date_utc": day.isoformat(),
    }
    if candidate is not None:
        # Mint a fresh signed reference for each request, even on cache hits.
        with suppress(OSError, ValueError):
            payload["selection"] = issue_selection(candidate, get_artwork_signing_key())
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
        # Verify the signed daily candidate before acquiring the SQLite
        # writer lock; the catalog scan can be expensive on large instances.
        try:
            selected = verify_selection(conn, payload.get("selection"), get_artwork_signing_key())
        except (OSError, ValueError):
            selected = None
        if selected is None:
            raise HTTPException(status_code=404, detail="Station unavailable.")

        # Recheck only this station while holding the writer reservation:
        # publication, ownership and signed identity cannot change before insert.
        conn.execute("BEGIN IMMEDIATE")
        row = revalidate_selection_station(conn, selected)
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
        # Reject missing, unpublished, or unsafe stations before running
        # the ranking query. This check is deliberately never cached.
        eligible = conn.execute(
            """
            SELECT s.favicon, s.url, s.url_resolved
            FROM stations AS s
            WHERE s.id = ?
              AND trim(COALESCE(s.favicon, '')) != ''
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
            (station_id,),
        ).fetchone()
        if eligible is None or not public_station_urls_safe(
            eligible["url"], eligible["url_resolved"]
        ):
            raise HTTPException(status_code=404, detail="Artwork not available.")

    # Reuse the Top ranking across artwork requests. A SQLite commit
    # invalidates this result, and the publication preflight remains live.
    cached_top = public_response_cache.get(
        "artwork-top",
        lambda ranked_conn: {"rows": public_top_station_rows(ranked_conn)},
    )
    row = next(
        (item for item in cached_top["rows"] if int(item["station_id"]) == station_id),
        None,
    )

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
