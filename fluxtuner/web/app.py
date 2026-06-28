from __future__ import annotations

import argparse
import hashlib
import hmac
import os
from importlib import resources
from typing import Any

from fluxtuner import __app_name__, __version__
from fluxtuner.core import db
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
from fluxtuner.web import auth

SESSION_COOKIE_NAME = "fluxtuner_session"
AUTH_ERROR_DETAIL = "Invalid username or password."
RATE_LIMIT_DETAIL = "Too many login attempts. Try again later."
AUTH_REQUIRED_DETAIL = "Authentication required."
CSRF_HEADER_NAME = "X-FluxTuner-CSRF"
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."


def _web_secure_cookies() -> bool:
    value = os.getenv("FLUXTUNER_WEB_SECURE_COOKIES", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _session_cookie_max_age() -> int:
    value = os.getenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "")
    try:
        max_age = int(value)
    except ValueError:
        return auth.DEFAULT_SESSION_MAX_AGE_SECONDS
    return max_age if max_age > 0 else auth.DEFAULT_SESSION_MAX_AGE_SECONDS


def _request_client_host(request: Any) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return auth.client_key_from_host(str(host) if host else None)


def _public_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "display_name": str(user["display_name"]),
        "is_admin": bool(user["is_admin"]),
    }


def _authenticated_user(request: Any) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    with db.connect() as conn:
        return auth.get_session_user(conn, token)


def _csrf_token_for_session_token(token: str | None) -> str:
    """Return a CSRF token derived from the opaque session token."""
    if not token:
        return ""

    return hmac.new(
        token.encode("utf-8"),
        b"fluxtuner-web-csrf-v1",
        hashlib.sha256,
    ).hexdigest()


def _set_session_cookie(response: Any, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=_session_cookie_max_age(),
        httponly=True,
        secure=_web_secure_cookies(),
        samesite="lax",
        path="/",
    )


def _delete_session_cookie(response: Any) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=_web_secure_cookies(),
        httponly=True,
        samesite="lax",
    )


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
        from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles

        globals()["Request"] = Request
        globals()["Response"] = Response
    except ImportError as exc:
        raise RuntimeError(_missing_web_dependency_message()) from exc

    required_body = Body(...)

    def require_csrf(request: Request) -> None:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        expected = _csrf_token_for_session_token(token)
        provided = request.headers.get(CSRF_HEADER_NAME, "")

        if not expected or not hmac.compare_digest(provided, expected):
            raise HTTPException(status_code=403, detail=CSRF_ERROR_DETAIL)

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

    @app.post("/api/auth/login")
    def login(
        request: Request,
        response: Response,
        payload: dict[str, Any] = required_body,
    ) -> dict[str, Any]:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        client_key = _request_client_host(request)

        if not username or not password:
            raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

        with db.connect() as conn:
            if auth.is_login_rate_limited(conn, username, client_key):
                raise HTTPException(status_code=429, detail=RATE_LIMIT_DETAIL)

            user = db.get_user_by_username(conn, username)
            password_hash = None
            if user is not None and bool(user["is_active"]):
                password_hash = str(user["password_hash"] or "")

            if not password_hash:
                auth.verify_password(password, auth.DUMMY_PASSWORD_HASH)
                auth.record_login_attempt(
                    conn,
                    username,
                    client_key,
                    success=False,
                )
                conn.commit()
                raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

            if not auth.verify_password(password, password_hash):
                auth.record_login_attempt(
                    conn,
                    username,
                    client_key,
                    success=False,
                )
                conn.commit()
                raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

            authenticated_user = user
            if authenticated_user is None:
                raise HTTPException(status_code=401, detail=AUTH_ERROR_DETAIL)

            token = auth.create_session(
                conn,
                int(authenticated_user["id"]),
                max_age_seconds=_session_cookie_max_age(),
            )
            auth.record_login_attempt(
                conn,
                username,
                client_key,
                success=True,
            )
            conn.commit()

        _set_session_cookie(response, token)
        return {
            "authenticated": True,
            "user": _public_user_payload(authenticated_user),
            "csrf_token": _csrf_token_for_session_token(token),
        }

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        with db.connect() as conn:
            revoked = auth.revoke_session(conn, token)
            conn.commit()

        _delete_session_cookie(response)
        return {"status": "ok", "revoked": revoked}

    @app.get("/api/auth/me")
    def me(request: Request) -> dict[str, Any]:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        with db.connect() as conn:
            user = auth.get_session_user(conn, token)

        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        return {
            "authenticated": True,
            "user": _public_user_payload(user),
            "csrf_token": _csrf_token_for_session_token(token),
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
        request: Request,
        limit: int = Query(default=25, ge=1, le=100),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        profile_name = effective_profile_name(profile)
        stations = load_history(
            profile_name=profile_name,
            user_id=int(user["id"]),
        )[:limit]

        return {
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/history")
    def record_history(
        request: Request,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        add_history(
            station_data,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "status": "ok",
            "station": station_data,
        }

    @app.get("/api/favorites")
    def favorites(
        request: Request,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        profile_name = effective_profile_name(profile)
        stations = load_favorites(
            profile_name=profile_name,
            user_id=int(user["id"]),
        )

        return {
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/favorites")
    def create_favorite(
        request: Request,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        added = add_favorite(
            station_data,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "status": "ok",
            "added": added,
            "station": station_data,
        }

    @app.delete("/api/favorites")
    def delete_favorite(
        request: Request,
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        removed = remove_favorite(
            url,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "status": "ok",
            "removed": removed,
            "url": url,
        }

    @app.get("/api/playlists")
    def playlists(
        request: Request,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        user_id = int(user["id"])
        profile_name = effective_profile_name(profile)
        items = load_playlists(profile_name=profile_name, user_id=user_id)

        return {
            "count": len(items),
            "playlists": [
                {
                    "name": item["name"],
                    "count": len(
                        get_playlist_stations(
                            item["name"],
                            profile_name=profile_name,
                            user_id=user_id,
                        )
                    ),
                }
                for item in items
            ],
        }

    @app.post("/api/playlists")
    def create_web_playlist(
        request: Request,
        payload: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        name = _playlist_name(payload)
        if not name:
            raise HTTPException(status_code=400, detail="Playlist name is required.")

        created = create_playlist(
            name,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "status": "ok",
            "created": created,
            "name": name,
        }

    @app.delete("/api/playlists/{name}")
    def delete_web_playlist(
        request: Request,
        name: str,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        removed = delete_playlist(
            name,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "status": "ok",
            "removed": removed,
            "name": name,
        }

    @app.get("/api/playlists/{name}/stations")
    def playlist_stations(
        request: Request,
        name: str,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        stations = get_playlist_stations(
            name,
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
        )

        return {
            "name": name,
            "count": len(stations),
            "stations": [_station_payload(station) for station in stations],
        }

    @app.post("/api/playlists/{name}/stations")
    def add_web_station_to_playlist(
        request: Request,
        name: str,
        station: dict[str, Any] = required_body,
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        station_data = _station_payload(station)

        if not station_data["url"]:
            raise HTTPException(status_code=400, detail="Station URL is required.")

        user_id = int(user["id"])
        profile_name = effective_profile_name(profile)
        add_favorite(station_data, profile_name=profile_name, user_id=user_id)
        added = add_station_to_playlist(
            name,
            station_data,
            profile_name=profile_name,
            user_id=user_id,
        )

        return {
            "status": "ok",
            "added": added,
            "name": name,
            "station": station_data,
        }

    @app.delete("/api/playlists/{name}/stations")
    def remove_web_station_from_playlist(
        request: Request,
        name: str,
        url: str = Query(..., min_length=1, max_length=4096),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, Any]:
        user = _authenticated_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail=AUTH_REQUIRED_DETAIL)

        require_csrf(request)

        removed = remove_station_from_playlist(
            name,
            {"url": url},
            profile_name=effective_profile_name(profile),
            user_id=int(user["id"]),
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
