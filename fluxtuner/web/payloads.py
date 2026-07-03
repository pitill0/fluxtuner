# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def favorite_tags_payload(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def station_payload(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(station.get("name") or "Unknown station"),
        "url": str(station.get("url") or ""),
        "url_resolved": str(station.get("url_resolved") or station.get("url") or ""),
        "country": str(station.get("country") or "Unknown"),
        "countrycode": str(station.get("countrycode") or ""),
        "tags": str(station.get("tags") or ""),
        "codec": str(station.get("codec") or ""),
        "bitrate": safe_int(station.get("bitrate")),
        "homepage": str(station.get("homepage") or ""),
        "language": str(station.get("language") or ""),
        "last_played_at": str(station.get("last_played_at") or ""),
        "play_count": safe_int(station.get("play_count")),
        "custom_name": str(station.get("custom_name") or ""),
        "favorite_tags": favorite_tags_payload(station.get("favorite_tags")),
    }


def public_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "display_name": str(user["display_name"]),
        "is_admin": bool(user["is_admin"]),
    }


def admin_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(user["id"]),
        "username": str(user["username"]),
        "display_name": str(user["display_name"]),
        "is_admin": bool(user["is_admin"]),
        "is_active": bool(user["is_active"]),
        "approval_status": str(user["approval_status"]),
        "signup_note": user.get("signup_note"),
        "reviewed_at": user.get("reviewed_at"),
        "reviewed_by_user_id": user.get("reviewed_by_user_id"),
        "created_at": str(user["created_at"]),
        "updated_at": str(user["updated_at"]),
    }


def admin_password_change_request_payload(
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": int(request_payload["id"]),
        "user_id": int(request_payload["user_id"]),
        "username": str(request_payload["username"]),
        "display_name": str(request_payload["display_name"]),
        "note": request_payload.get("note"),
        "status": str(request_payload["status"]),
        "created_at": str(request_payload["created_at"]),
        "expires_at": str(request_payload["expires_at"]),
        "resolved_at": request_payload.get("resolved_at"),
        "resolved_by_user_id": request_payload.get("resolved_by_user_id"),
    }
