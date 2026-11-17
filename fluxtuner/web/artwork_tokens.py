# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Short-lived artwork references signed with a server-only secret.

The browser's session cookie is *not* a signing key. Only trusted server code
may issue these references; receiving an arbitrary URL is not an issuance API.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from urllib.parse import urlsplit

ARTWORK_TOKEN_TTL_SECONDS = 300
MAX_ARTWORK_TOKEN_TTL_SECONDS = 900
MAX_ARTWORK_URL_LENGTH = 2048
_VERSION = "v1"


def _allowed_url(url: str) -> bool:
    if not url or len(url) > MAX_ARTWORK_URL_LENGTH or any(ord(char) < 33 for char in url):
        return False
    try:
        parts = urlsplit(url)
        return (
            parts.scheme in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and parts.fragment == ""
            and parts.port != 0
        )
    except ValueError:
        return False


def _signature(url: str, expires_at: int, session_token: str, signing_key: bytes) -> str:
    session_digest = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
    message = f"fluxtuner-artwork-{_VERSION}\n{expires_at}\n{session_digest}\n{url}"
    return hmac.new(signing_key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _valid_key(signing_key: bytes) -> bool:
    return isinstance(signing_key, bytes) and len(signing_key) >= 32


def issue_artwork_reference(
    url: str,
    session_token: str,
    signing_key: bytes,
    *,
    now: int | None = None,
    ttl_seconds: int = ARTWORK_TOKEN_TTL_SECONDS,
) -> str:
    """Issue a reference from trusted server-side station metadata only."""
    if not _valid_key(signing_key) or not session_token or not _allowed_url(url):
        raise ValueError("Invalid artwork reference inputs.")
    if not 1 <= ttl_seconds <= MAX_ARTWORK_TOKEN_TTL_SECONDS:
        raise ValueError("Invalid artwork reference lifetime.")
    expires_at = int(time.time()) if now is None else int(now)
    expires_at += ttl_seconds
    encoded_url = base64.urlsafe_b64encode(url.encode("utf-8")).rstrip(b"=").decode("ascii")
    digest = _signature(url, expires_at, session_token, signing_key)
    return f"{_VERSION}.{expires_at}.{encoded_url}.{digest}"


def verify_artwork_reference(
    reference: str,
    session_token: str,
    signing_key: bytes,
    *,
    now: int | None = None,
) -> str | None:
    """Return the authorized source URL, or None on any invalid reference."""
    if (
        not _valid_key(signing_key)
        or not session_token
        or not isinstance(reference, str)
        or len(reference) > 4096
    ):
        return None
    try:
        version, expiry, encoded_url, supplied_digest = reference.split(".")
        if version != _VERSION or not expiry.isascii() or not expiry.isdecimal():
            return None
        expires_at = int(expiry)
        current_time = int(time.time()) if now is None else int(now)
        if not current_time <= expires_at <= current_time + MAX_ARTWORK_TOKEN_TTL_SECONDS:
            return None
        if not encoded_url or any(
            char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for char in encoded_url
        ):
            return None
        padding = "=" * (-len(encoded_url) % 4)
        url = base64.urlsafe_b64decode(encoded_url + padding).decode("utf-8")
        if not _allowed_url(url):
            return None
        expected = _signature(url, expires_at, session_token, signing_key)
        if not hmac.compare_digest(supplied_digest, expected):
            return None
        return url
    except (binascii.Error, UnicodeError, ValueError):
        return None
