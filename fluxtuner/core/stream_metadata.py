from __future__ import annotations

import re
from typing import Any

import requests

ICY_HEADER = {"Icy-MetaData": "1"}


def _parse_stream_title(raw_title: str) -> dict[str, str]:
    cleaned = raw_title.strip()

    if " - " in cleaned:
        artist, title = cleaned.split(" - ", 1)
        return {
            "raw": cleaned,
            "artist": artist.strip(),
            "title": title.strip(),
        }

    return {
        "raw": cleaned,
        "artist": "",
        "title": cleaned,
    }


def fetch_stream_metadata(
    url: str,
    timeout: int = 8,
) -> dict[str, Any] | None:
    try:
        response = requests.get(
            url,
            headers=ICY_HEADER,
            stream=True,
            timeout=timeout,
        )
    except Exception:
        return None

    metaint_header = response.headers.get("icy-metaint")
    if not metaint_header:
        return None

    try:
        metaint = int(metaint_header)
    except ValueError:
        return None

    stream = response.raw

    try:
        stream.read(metaint)

        metadata_length = stream.read(1)
        if not metadata_length:
            return None

        metadata_size = metadata_length[0] * 16
        if metadata_size <= 0:
            return None

        metadata = stream.read(metadata_size)
        metadata_text = metadata.decode("utf-8", errors="ignore")

    except Exception:
        return None
    finally:
        response.close()

    match = re.search(r"StreamTitle='([^']*)';", metadata_text)
    if not match:
        return None

    raw_title = match.group(1).strip()
    if not raw_title:
        return None

    parsed = _parse_stream_title(raw_title)
    parsed["source"] = "icy"

    return parsed
