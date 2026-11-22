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
        "stationuuid": str(station.get("stationuuid") or ""),
        "favicon": str(station.get("favicon") or ""),
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


WEB_STATION_FIELD_LIMITS = {
    "name": 200,
    "url": 4096,
    "url_resolved": 4096,
    "stationuuid": 100,
    "favicon": 2048,
    "country": 100,
    "countrycode": 16,
    "tags": 500,
    "codec": 50,
    "homepage": 2048,
    "language": 100,
    "custom_name": 200,
    "last_played_at": 64,
}


def station_input_payload(station: dict[str, Any]) -> dict[str, Any]:
    """Bound untrusted Web station data and protect shared records."""
    if not isinstance(station, dict):
        raise ValueError("Invalid station payload.")

    for field, limit in WEB_STATION_FIELD_LIMITS.items():
        value = station.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Station metadata exceeds allowed limits.")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Station metadata contains control characters.")

    favorite_tags = station.get("favorite_tags")
    if favorite_tags is not None:
        if not isinstance(favorite_tags, list) or len(favorite_tags) > 32:
            raise ValueError("Favorite tags exceed allowed limits.")
        if any(
            not isinstance(item, str)
            or len(item) > 100
            or any(ord(char) < 32 or ord(char) == 127 for char in item)
            for item in favorite_tags
        ):
            raise ValueError("Favorite tags contain invalid values.")

    result = station_payload(station)
    result["stationuuid"] = ""
    result["_web_untrusted"] = True
    return result
