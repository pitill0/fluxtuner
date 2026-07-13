from __future__ import annotations

import re
from typing import Any, BinaryIO

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


def _parse_icy_metaint_with_reason(value: str | None) -> tuple[int | None, str]:
    if not value:
        return None, "missing"

    try:
        metaint = int(value)
    except ValueError:
        return None, "invalid"

    if metaint <= 0 or metaint > MAX_METAINT:
        return None, "outside-range"

    return metaint, ""


def parse_icy_metaint(value: str | None) -> int | None:
    """Return a bounded ICY metadata interval without performing network access."""
    metaint, _reason = _parse_icy_metaint_with_reason(value)
    return metaint


def _read_icy_metadata_block_with_reason(
    stream: BinaryIO,
    metaint: int,
) -> tuple[bytes | None, str]:
    if metaint <= 0 or metaint > MAX_METAINT:
        return None, "outside-range"

    stream.read(metaint)

    metadata_length = stream.read(1)
    if not metadata_length:
        return None, "missing-length"

    metadata_size = metadata_length[0] * 16
    if metadata_size <= 0:
        return None, "empty"

    if metadata_size > MAX_METADATA_SIZE:
        return None, "exceeds-limit"

    return stream.read(metadata_size), ""


def read_icy_metadata_block(stream: BinaryIO, metaint: int) -> bytes | None:
    """Read one bounded ICY metadata block from an already-open binary stream."""
    metadata, _reason = _read_icy_metadata_block_with_reason(stream, metaint)
    return metadata


def _parse_icy_metadata_block_with_reason(
    metadata: bytes,
) -> tuple[dict[str, str] | None, str]:
    metadata_text = metadata.decode("utf-8", errors="ignore")
    match = re.search(r"StreamTitle='([^']*)';", metadata_text)
    if not match:
        return None, "missing-title"

    raw_title = match.group(1).strip()
    if not raw_title:
        return None, "empty-title"

    parsed = _parse_stream_title(raw_title)
    parsed["source"] = "icy"
    return parsed, ""


def parse_icy_metadata_block(metadata: bytes) -> dict[str, str] | None:
    """Parse one ICY metadata block without performing network access."""
    parsed, _reason = _parse_icy_metadata_block_with_reason(metadata)
    return parsed


def fetch_stream_metadata(
    url: str,
    timeout: int = 8,
) -> dict[str, Any] | None:
    """Fetch ICY metadata for trusted local-interface callers.

    Web/server callers must use the future protected Web transport rather than
    passing user-controlled URLs to this compatibility wrapper.
    """
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
        metaint, metaint_reason = _parse_icy_metaint_with_reason(
            response.headers.get("icy-metaint")
        )
        if metaint is None:
            if metaint_reason == "missing":
                logger.debug("ICY metadata unavailable: missing icy-metaint header")
            elif metaint_reason == "invalid":
                logger.debug("ICY metadata unavailable: invalid icy-metaint header")
            else:
                logger.debug("ICY metadata unavailable: icy-metaint outside allowed range")
            return None

        metadata, metadata_reason = _read_icy_metadata_block_with_reason(response.raw, metaint)
        if metadata is None:
            if metadata_reason == "missing-length":
                logger.debug("ICY metadata unavailable: missing metadata length byte")
            elif metadata_reason == "empty":
                logger.debug("ICY metadata unavailable: empty metadata block")
            elif metadata_reason == "exceeds-limit":
                logger.debug("ICY metadata unavailable: metadata block exceeds size limit")
            else:
                logger.debug("ICY metadata unavailable: icy-metaint outside allowed range")
            return None

        parsed, parse_reason = _parse_icy_metadata_block_with_reason(metadata)
        if parsed is None:
            if parse_reason == "empty-title":
                logger.debug("ICY metadata unavailable: empty StreamTitle")
            else:
                logger.debug("ICY metadata unavailable: missing StreamTitle")
            return None

    except Exception:
        logger.debug("ICY metadata parsing failed", exc_info=True)
        return None
    finally:
        response.close()

    logger.debug("ICY metadata parsed successfully")
    return parsed
