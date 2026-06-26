from __future__ import annotations

import argparse
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__


def _missing_web_dependency_message() -> str:
    return (
        "FluxTuner Web dependencies are not installed. "
        'Install them with: pip install -e ".[web]"'
    )


def _read_template(name: str) -> str:
    return resources.files("fluxtuner.web").joinpath("templates", name).read_text(
        encoding="utf-8"
    )


def create_app() -> Any:
    """Create the experimental FluxTuner Web application."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

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
