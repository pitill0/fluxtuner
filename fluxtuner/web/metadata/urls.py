# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import ipaddress
import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .contracts import MetadataFetchPolicy, NormalizedStreamTarget


class StreamTargetValidationError(ValueError):
    """Raised when a stream URL cannot enter the Web metadata network boundary."""


def _contains_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _normalized_hostname(hostname: str) -> str:
    clean_hostname = hostname.rstrip(".").lower()
    if not clean_hostname:
        raise StreamTargetValidationError("Stream URL hostname is required.")
    if "%" in clean_hostname:
        raise StreamTargetValidationError("IPv6 zone identifiers are not allowed.")

    try:
        address = ipaddress.ip_address(clean_hostname)
    except ValueError:
        try:
            ascii_hostname = clean_hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise StreamTargetValidationError("Stream URL hostname is invalid.") from exc
    else:
        return address.compressed

    if len(ascii_hostname) > 253:
        raise StreamTargetValidationError("Stream URL hostname is too long.")
    labels = ascii_hostname.split(".")
    if any(not label or len(label) > 63 for label in labels):
        raise StreamTargetValidationError("Stream URL hostname is invalid.")
    if any(not re.fullmatch(r"[a-z0-9-]+", label) for label in labels):
        raise StreamTargetValidationError("Stream URL hostname is invalid.")
    if any(label.startswith("-") or label.endswith("-") for label in labels):
        raise StreamTargetValidationError("Stream URL hostname is invalid.")
    return ascii_hostname


def _normalized_netloc(hostname: str, port: int, scheme: str) -> str:
    display_hostname = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    if port == default_port:
        return display_hostname
    return f"{display_hostname}:{port}"


def normalize_stream_target(
    value: str,
    policy: MetadataFetchPolicy | None = None,
) -> NormalizedStreamTarget:
    """Validate and conservatively normalize one Web metadata stream target."""
    active_policy = policy or MetadataFetchPolicy()

    if not isinstance(value, str):
        raise StreamTargetValidationError("Stream URL must be text.")

    candidate = value.strip()
    if not candidate:
        raise StreamTargetValidationError("Stream URL is required.")
    if len(candidate) > active_policy.max_url_length:
        raise StreamTargetValidationError("Stream URL exceeds the allowed length.")
    if _contains_control_characters(candidate):
        raise StreamTargetValidationError("Stream URL contains control characters.")

    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise StreamTargetValidationError("Stream URL is malformed.") from exc

    scheme = parsed.scheme.lower()
    if scheme not in active_policy.allowed_schemes:
        raise StreamTargetValidationError("Stream URL scheme is not allowed.")
    if parsed.username is not None or parsed.password is not None:
        raise StreamTargetValidationError("Stream URL credentials are not allowed.")
    if parsed.fragment:
        raise StreamTargetValidationError("Stream URL fragments are not allowed.")
    if not parsed.hostname:
        raise StreamTargetValidationError("Stream URL hostname is required.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise StreamTargetValidationError("Stream URL port is invalid.") from exc

    if port is None:
        port = 443 if scheme == "https" else 80
    if port <= 0 or port > 65535:
        raise StreamTargetValidationError("Stream URL port is invalid.")

    hostname = _normalized_hostname(parsed.hostname)
    path = parsed.path or "/"
    normalized = SplitResult(
        scheme=scheme,
        netloc=_normalized_netloc(hostname, port, scheme),
        path=path,
        query=parsed.query,
        fragment="",
    )
    normalized_url = urlunsplit(normalized)

    if len(normalized_url) > active_policy.max_url_length:
        raise StreamTargetValidationError("Normalized stream URL exceeds the allowed length.")

    return NormalizedStreamTarget(
        url=normalized_url,
        scheme=scheme,
        hostname=hostname,
        port=port,
    )
