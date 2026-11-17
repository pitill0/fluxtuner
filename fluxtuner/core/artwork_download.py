"""Bounded station artwork downloads through the validated network boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import urljoin

from fluxtuner.core.artwork_validation import MAX_ARTWORK_BYTES, detect_artwork_type
from fluxtuner.network.contracts import MetadataFetchPolicy, StreamTargetResolver
from fluxtuner.network.network_policy import validate_resolved_target
from fluxtuner.network.transport import ProtectedHTTPTransport
from fluxtuner.network.urls import normalize_stream_target

_MAX_WIRE_OVERHEAD = 65536
_ALLOWED_CONTENT_TYPES = frozenset(
    {"", "application/octet-stream", "image/png", "image/jpeg", "image/webp"}
)


class ArtworkDownloadError(ValueError):
    """A remote image violated the artwork download contract."""


@dataclass(frozen=True, slots=True)
class DownloadedArtwork:
    data: bytes
    mime_type: str


def _read_exact(body: BinaryIO, size: int, budget: list[int]) -> bytes:
    if size > budget[0]:
        raise ArtworkDownloadError("Artwork transfer exceeds its byte budget.")
    result = bytearray()
    while len(result) < size:
        chunk = body.read(min(65536, size - len(result)))
        if not chunk:
            raise ArtworkDownloadError("Artwork response ended prematurely.")
        result.extend(chunk)
        budget[0] -= len(chunk)
    return bytes(result)


def _read_line(body: BinaryIO, budget: list[int]) -> bytes:
    line = bytearray()
    while len(line) <= 8192:
        if budget[0] <= 0:
            raise ArtworkDownloadError("Artwork transfer exceeds its byte budget.")
        character = body.read(1)
        if not character:
            raise ArtworkDownloadError("Incomplete artwork chunk framing.")
        budget[0] -= 1
        line.extend(character)
        if line.endswith(b"\r\n"):
            return bytes(line[:-2])
    raise ArtworkDownloadError("Oversized artwork chunk header.")


def _read_chunked(body: BinaryIO) -> bytes:
    budget = [MAX_ARTWORK_BYTES + _MAX_WIRE_OVERHEAD]
    result = bytearray()
    while True:
        raw = _read_line(body, budget)
        size_text = raw.split(b";", 1)[0].strip()
        if not size_text or any(char not in b"0123456789abcdefABCDEF" for char in size_text):
            raise ArtworkDownloadError("Invalid artwork chunk length.")
        chunk_size = int(size_text, 16)
        if chunk_size == 0:
            if _read_line(body, budget):
                raise ArtworkDownloadError("Artwork response trailers are not supported.")
            return bytes(result)
        if chunk_size > MAX_ARTWORK_BYTES - len(result):
            raise ArtworkDownloadError("Artwork exceeds the maximum size.")
        result.extend(_read_exact(body, chunk_size, budget))
        if _read_exact(body, 2, budget) != b"\r\n":
            raise ArtworkDownloadError("Invalid artwork chunk terminator.")


def _read_artwork_body(body: BinaryIO, headers: dict[str, str]) -> bytes:
    if headers.get("content-encoding", "identity").strip().lower() not in {"", "identity"}:
        raise ArtworkDownloadError("Compressed artwork responses are not supported.")

    transfer = headers.get("transfer-encoding", "").strip().lower()
    declared = headers.get("content-length")
    if transfer:
        if transfer != "chunked" or declared is not None:
            raise ArtworkDownloadError("Ambiguous artwork response framing.")
        return _read_chunked(body)

    if declared is not None:
        if not declared.isascii() or not declared.isdecimal():
            raise ArtworkDownloadError("Invalid artwork Content-Length.")
        count = int(declared)
        if count > MAX_ARTWORK_BYTES:
            raise ArtworkDownloadError("Artwork exceeds the maximum size.")
        return _read_exact(body, count, [MAX_ARTWORK_BYTES + 1])

    result = bytearray()
    while len(result) <= MAX_ARTWORK_BYTES:
        chunk = body.read(min(65536, MAX_ARTWORK_BYTES + 1 - len(result)))
        if not chunk:
            return bytes(result)
        result.extend(chunk)
    raise ArtworkDownloadError("Artwork exceeds the maximum size.")


def download_artwork(
    url: str,
    resolver: StreamTargetResolver,
    *,
    policy: MetadataFetchPolicy | None = None,
    transport: ProtectedHTTPTransport | None = None,
) -> DownloadedArtwork:
    """Download an image without DNS rebinding or unbounded reads.

    The caller decides whether to cache it and must never block playback on failure.
    """
    active_policy = policy or MetadataFetchPolicy()
    active_transport = transport or ProtectedHTTPTransport()
    start = time.monotonic()
    target = normalize_stream_target(url, active_policy)

    for redirect_index in range(active_policy.max_redirects + 1):
        addresses = validate_resolved_target(target, resolver, active_policy)
        remaining = active_policy.total_timeout_seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise ArtworkDownloadError("Artwork download timed out.")
        response = active_transport.request(
            target, addresses[0], active_policy, remaining, icy_metadata=False
        )
        try:
            if 300 <= response.status < 400:
                location = response.headers.get("location")
                if not location or redirect_index >= active_policy.max_redirects:
                    raise ArtworkDownloadError("Artwork redirect missing or limit exceeded.")
                redirect = normalize_stream_target(urljoin(target.url, location), active_policy)
                if (
                    target.scheme == "https"
                    and redirect.scheme == "http"
                    and not active_policy.allow_https_to_http_redirect
                ):
                    raise ArtworkDownloadError("HTTPS-to-HTTP artwork redirect is forbidden.")
                target = redirect
                continue

            if response.status != 200:
                raise ArtworkDownloadError(f"Artwork returned HTTP {response.status}.")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise ArtworkDownloadError("Unsupported artwork Content-Type.")
            data = _read_artwork_body(response.body, response.headers)
            detected_type = detect_artwork_type(data)
            if detected_type is None or (
                content_type.startswith("image/") and content_type != detected_type
            ):
                raise ArtworkDownloadError("Invalid or mismatched artwork content.")
            return DownloadedArtwork(data=data, mime_type=detected_type)
        finally:
            response.close()
    raise ArtworkDownloadError("Artwork redirect limit exceeded.")
