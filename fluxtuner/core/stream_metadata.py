from __future__ import annotations

import re
from typing import Any

import requests

from fluxtuner.logging_config import get_logger

ICY_HEADER = {"Icy-MetaData": "1"}

MAX_METAINT = 512_000
MAX_METADATA_SIZE = 2048

logger = get_logger(__name__)


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
    logger.debug("Fetching ICY stream metadata")

    try:
        response = requests.get(
            url,
            headers=ICY_HEADER,
            stream=True,
            timeout=timeout,
        )
    except requests.RequestException:
        logger.debug("ICY metadata request failed", exc_info=True)
        return None

    try:
        metaint_header = response.headers.get("icy-metaint")
        if not metaint_header:
            logger.debug("ICY metadata unavailable: missing icy-metaint header")
            return None

        try:
            metaint = int(metaint_header)
        except ValueError:
            logger.debug("ICY metadata unavailable: invalid icy-metaint header")
            return None

        if metaint <= 0 or metaint > MAX_METAINT:
            logger.debug("ICY metadata unavailable: icy-metaint outside allowed range")
            return None

        stream = response.raw

        stream.read(metaint)

        metadata_length = stream.read(1)
        if not metadata_length:
            logger.debug("ICY metadata unavailable: missing metadata length byte")
            return None

        metadata_size = metadata_length[0] * 16
        if metadata_size <= 0:
            logger.debug("ICY metadata unavailable: empty metadata block")
            return None

        if metadata_size > MAX_METADATA_SIZE:
            logger.debug("ICY metadata unavailable: metadata block exceeds size limit")
            return None

        metadata = stream.read(metadata_size)
        metadata_text = metadata.decode("utf-8", errors="ignore")

    except Exception:
        logger.debug("ICY metadata parsing failed", exc_info=True)
        return None
    finally:
        response.close()

    match = re.search(r"StreamTitle='([^']*)';", metadata_text)
    if not match:
        logger.debug("ICY metadata unavailable: missing StreamTitle")
        return None

    raw_title = match.group(1).strip()
    if not raw_title:
        logger.debug("ICY metadata unavailable: empty StreamTitle")
        return None

    parsed = _parse_stream_title(raw_title)
    parsed["source"] = "icy"

    logger.debug("ICY metadata parsed successfully")

    return parsed
