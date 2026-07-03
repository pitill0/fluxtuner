# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def text_too_long(value: str | None, max_length: int) -> bool:
    return value is not None and len(value) > max_length


def is_supported_web_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def station_stream_url(station_data: dict[str, Any]) -> str:
    return str(station_data.get("url_resolved") or station_data.get("url") or "").strip()


def playlist_name(payload: dict[str, Any]) -> str:
    return str(payload.get("name") or "").strip()


def playlist_name_too_long(name: str, *, max_length: int = 120) -> bool:
    return len(name) > max_length
