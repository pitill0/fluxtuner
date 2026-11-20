# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response

from fluxtuner.core import db
from fluxtuner.core.artwork_cache import ArtworkCache
from fluxtuner.core.public_featured import public_featured_station
from fluxtuner.core.public_trending import public_station_trends

router = APIRouter()


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
    """Provide a name-only, UTC-day rotating public directory suggestion."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    with db.connect() as conn:
        return public_featured_station(conn)


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
