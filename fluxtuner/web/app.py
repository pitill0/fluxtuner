from __future__ import annotations

import argparse
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core.api import search_stations_filtered
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.history import add_history, load_history
from fluxtuner.core.manual_playlists import (
    add_station_to_playlist,
    create_playlist,
    delete_playlist,
    get_playlist_stations,
    load_playlists,
    remove_station_from_playlist,
)
from fluxtuner.core.profiles import resolve_effective_profile_name


def _missing_web_dependency_message() -> str:
    return (
        'FluxTuner Web dependencies are not installed. Install them with: pip install -e ".[web]"'
    )


def _read_template(name: str) -> str:
    return resources.files("fluxtuner.web").joinpath("templates", name).read_text(encoding="utf-8")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _favorite_tags_payload(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _station_payload(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(station.get("name") or "Unknown station"),
        "url": str(station.get("url") or ""),
        "url_resolved": str(station.get("url_resolved") or station.get("url") or ""),
        "country": str(station.get("country") or "Unknown"),
        "countrycode": str(station.get("countrycode") or ""),
        "tags": str(station.get("tags") or ""),
        "codec": str(station.get("codec") or ""),
        "bitrate": _safe_int(station.get("bitrate")),
        "homepage": str(station.get("homepage") or ""),
        "language": str(station.get("language") or ""),
        "last_played_at": str(station.get("last_played_at") or ""),
        "play_count": _safe_int(station.get("play_count")),
        "custom_name": str(station.get("custom_name") or ""),
        "favorite_tags": _favorite_tags_payload(station.get("favorite_tags")),
    }


def _playlist_name(payload: dict[str, Any]) -> str:
    return str(payload.get("name") or "").strip()


def create_app() -> Any:
    """Create the experimental FluxTuner Web application."""
    try:
        from fastapi import Body, FastAPI, HTTPException, Query
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    required_body = Body(...)

    def effective_profile_name(profile: str | None = None) -> str | None:
        return resolve_effective_profile_name(profile)

    app = FastAPI(
        title=f"{__app_name__} Web",
        version=__version__,
        description="FluxTuner web/server interface.",
    )

    static_dir = resources.files("fluxtuner.web").joinpath("static")
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _read_template("index.html").replace("__FLUXTUNER_VERSION__", __version__)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": __app_name__,
            "version": __version__,
            "mode": "web",
        }

    @app.get("/api/search")
    def search(
        q: str = Query(default="", max_length=120),
        country: str = Query(default="", max_length=80),
        min_bitrate: int = Query(default=0, ge=0, le=1000),
        limit: int = Query(default=25, ge=1, le=50),
    ) -> dict[str, Any]:
        query = q.strip()
        country_filter = country.strip() or None
        bitrate_filter = min_bitrate if min_bitrate > 0 else None

        stations = search_stations_filtered(
            query=query,
            country=country_filter,
            min_bitrate=bitrate_filter,
            limit=limit,
        )

        return {
            "query": query,
            "country": country_filter or "",
            "min_bitrate": min_bitrate,
            "limit": limit,
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.get("/api/history")
    def history(
        limit: int = Query(default=25, ge=1, le=100),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        profile_name = effective_profile_name(profile)
        stations = load_history(profile_name=profile_name)[:limit]

        return {
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/history")
    def record_history(
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        add_history(station_data, profile_name=effective_profile_name(profile))

        return {
            "status": "ok",
            "station": station_data,
        }

    @app.get("/api/favorites")
    def favorites(
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        profile_name = effective_profile_name(profile)
        stations = load_favorites(profile_name=profile_name)

        return {
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/favorites")
    def create_favorite(
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        added = add_favorite(station_data, profile_name=effective_profile_name(profile))

        return {
            "status": "ok",
            "added": added,
            "station": station_data,
        }

    @app.delete("/api/favorites")
    def delete_favorite(
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        removed = remove_favorite(url, profile_name=effective_profile_name(profile))

        return {
            "status": "ok",
            "removed": removed,
            "url": url,
        }

    @app.get("/api/playlists")
    def playlists(
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        profile_name = effective_profile_name(profile)
        items = load_playlists(profile_name=profile_name)

        return {
            "count": len(items),
            "playlists": [
                {
                    "name": item["name"],
                    "count": len(get_playlist_stations(item["name"], profile_name=profile_name)),
                }
                for item in items
            ],
        }

    @app.post("/api/playlists")
    def create_web_playlist(
        payload: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        name = _playlist_name(payload)
        if not name:
            raise HTTPException(status_code=400, detail="Playlist name is required.")

        created = create_playlist(name, profile_name=effective_profile_name(profile))

        return {
            "status": "ok",
            "created": created,
            "name": name,
        }

    @app.delete("/api/playlists/{name}")
    def delete_web_playlist(
        name: str,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        removed = delete_playlist(name, profile_name=effective_profile_name(profile))

        return {
            "status": "ok",
            "removed": removed,
            "name": name,
        }

    @app.get("/api/playlists/{name}/stations")
    def playlist_stations(
        name: str,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        stations = get_playlist_stations(name, profile_name=effective_profile_name(profile))

        return {
            "name": name,
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/playlists/{name}/stations")
    def add_web_station_to_playlist(
        name: str,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        profile_name = effective_profile_name(profile)
        add_favorite(station_data, profile_name=profile_name)
        added = add_station_to_playlist(name, station_data, profile_name=profile_name)

        return {
            "status": "ok",
            "added": added,
            "name": name,
            "station": station_data,
        }

    @app.delete("/api/playlists/{name}/stations")
    def remove_web_station_from_playlist(
        name: str,
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        removed = remove_station_from_playlist(
            name,
            {"url": url},
            profile_name=effective_profile_name(profile),
        )

        return {
            "status": "ok",
            "removed": removed,
            "name": name,
            "url": url,
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FluxTuner Web")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on. Defaults to 8080.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload for development.",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    uvicorn.run(
        "fluxtuner.web.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
