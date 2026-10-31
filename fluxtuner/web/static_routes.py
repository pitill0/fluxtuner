# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Static publication, mounts and cache-aware HTML responses."""

from __future__ import annotations

import gzip
import hashlib
import logging
import os
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fluxtuner import __version__, paths
from fluxtuner.web.static_build_http import StaticBuildHTTP
from fluxtuner.web.static_builds import StaticBuildError, create_static_snapshot
from fluxtuner.web.static_compression import StaticCompression, _accepts_gzip


def _read_template(name: str) -> str:
    template_path = resources.files("fluxtuner.web").joinpath("templates").joinpath(name)
    return template_path.read_text(encoding="utf-8")


def register_static_routes(app: FastAPI) -> None:
    """Publish assets before building the HTML that references their URLs."""
    static_dir = resources.files("fluxtuner.web").joinpath("static")
    static_build_root = paths.DATA_DIR / "web" / "static-builds"

    static_build_prefix = ""
    if os.environ.get("FLUXTUNER_WEB_VERSIONED_STATIC") == "1":
        try:
            snapshot = create_static_snapshot(
                Path(str(static_dir)),
                static_build_root,
            )
            static_build_prefix = f"/static/build/{snapshot.build_id}"
        except (OSError, StaticBuildError):
            logging.getLogger(__name__).exception(
                "Static snapshot publication failed; using legacy static URLs"
            )

    # Versioned assets must be mounted before the legacy /static route.
    app.mount(
        "/static/build",
        StaticBuildHTTP(static_build_root),
        name="static-build",
    )
    app.mount(
        "/static",
        StaticCompression(StaticFiles(directory=str(static_dir))),
        name="static",
    )

    @app.api_route("/apple-touch-icon.png", methods=["GET", "HEAD"], include_in_schema=False)
    def apple_touch_icon() -> FileResponse:
        return FileResponse(str(static_dir.joinpath("icons").joinpath("apple-touch-icon.png")))

    @app.api_route(
        "/apple-touch-icon-precomposed.png",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    def apple_touch_icon_precomposed() -> FileResponse:
        return FileResponse(str(static_dir.joinpath("icons").joinpath("apple-touch-icon.png")))

    index_template = _read_template("index.html").replace("__FLUXTUNER_VERSION__", __version__)
    if static_build_prefix:
        index_template = index_template.replace('="/static/', f'="{static_build_prefix}/')
    index_html = index_template.encode("utf-8")
    index_gzip = gzip.compress(index_html, compresslevel=9, mtime=0)
    index_hash = hashlib.sha256(index_html).hexdigest()[:16]
    index_identity_etag = f'"{index_hash}"'
    index_gzip_etag = f'W/"gzip-{index_hash}"'

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def index(request: Request) -> Response:
        compressed = _accepts_gzip(request.scope)
        etag = index_gzip_etag if compressed else index_identity_etag
        headers = {
            "ETag": etag,
            "Cache-Control": "no-cache",
            "Vary": "Accept-Encoding",
        }
        requested = request.headers.get("if-none-match")
        # HTTP weak comparison is sufficient for If-None-Match on GET/HEAD.
        if requested is not None and any(
            value.strip() == "*" or value.strip().removeprefix("W/") == etag.removeprefix("W/")
            for value in requested.split(",")
        ):
            return Response(status_code=304, headers=headers)
        if compressed:
            headers["Content-Encoding"] = "gzip"
        body = index_gzip if compressed else index_html
        if request.method == "HEAD":
            headers["Content-Length"] = str(len(body))
        return Response(
            b"" if request.method == "HEAD" else body,
            media_type="text/html",
            headers=headers,
        )
