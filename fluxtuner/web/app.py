from __future__ import annotations

import argparse
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core.api import search_stations_filtered
from fluxtuner.core.history import add_history, load_history


def _missing_web_dependency_message() -> str:
    return (
        "FluxTuner Web dependencies are not installed. "
        'Install them with: pip install -e ".[web]"'
    )


def _read_template(name: str) -> str:
    return resources.files("fluxtuner.web").joinpath("templates", name).read_text(
        encoding="utf-8"
    )


def _station_payload(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": station.get("name") or "Unknown station",
        "url": station.get("url") or "",
        "url_resolved": station.get("url_resolved") or station.get("url") or "",
        "country": station.get("country") or "Unknown",
        "countrycode": station.get("countrycode") or "",
        "tags": station.get("tags") or "",
        "codec": station.get("codec") or "",
        "bitrate": int(station.get("bitrate") or 0),
        "homepage": station.get("homepage") or "",
        "language": station.get("language") or "",
        "last_played_at": station.get("last_played_at") or "",
        "play_count": int(station.get("play_count") or 0),
    }


def create_app() -> Any:
    """Create the experimental FluxTuner Web application."""
    try:
        from fastapi import FastAPI, Query
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    class StationPayload(BaseModel):
        name: str = Field(default="Unknown station", max_length=240)
        url: str = Field(default="", max_length=4096)
        url_resolved: str = Field(default="", max_length=4096)
        country: str = Field(default="Unknown", max_length=120)
        countrycode: str = Field(default="", max_length=8)
        tags: str = Field(default="", max_length=1000)
        codec: str = Field(default="", max_length=40)
        bitrate: int = Field(default=0, ge=0, le=10000)
        homepage: str = Field(default="", max_length=4096)
        language: str = Field(default="", max_length=200)

    app = FastAPI(
        title=f"{__app_name__} Web",
        version=__version__,
        description="Experimental FluxTuner web/server interface.",
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
    def history(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
        stations = load_history()[:limit]

        return {
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/history")
    def record_history(station: StationPayload) -> dict[str, Any]:
        station_data = station.model_dump()
        add_history(station_data)

        return {
            "status": "ok",
            "station": _station_payload(station_data),
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
