# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Bounded collection downloads through the existing validated Web network boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin

from fluxtuner.core.m3u_import import MAX_FILE_BYTES, M3UPreview, parse_station_collection
from fluxtuner.network.contracts import MetadataFetchPolicy, StreamTargetResolver
from fluxtuner.network.network_policy import validate_resolved_target
from fluxtuner.network.transport import ProtectedHTTPTransport
from fluxtuner.network.urls import normalize_stream_target


class RemoteCollectionError(ValueError):
    """A remote collection could not be downloaded within the safety contract."""


def _read_line(body: object, remaining: list[int]) -> bytes:
    """Read one CRLF-framed line, with a total wire-byte budget."""
    line = bytearray()
    while True:
        if remaining[0] <= 0:
            raise RemoteCollectionError("Remote response exceeds the transfer limit.")
        chunk = body.read(1)  # type: ignore[attr-defined]
        if not chunk:
            raise RemoteCollectionError("Remote response ended before chunk framing completed.")
        remaining[0] -= 1
        line.extend(chunk)
        if line.endswith(b"\r\n"):
            return bytes(line[:-2])
        if len(line) > 8192:
            raise RemoteCollectionError("Remote response framing is too long.")


def _read_exact(body: object, size: int, remaining: list[int]) -> bytes:
    if size > remaining[0]:
        raise RemoteCollectionError("Remote response exceeds the transfer limit.")
    out = bytearray()
    while len(out) < size:
        chunk = body.read(min(65536, size - len(out)))  # type: ignore[attr-defined]
        if not chunk:
            raise RemoteCollectionError("Remote response ended before its declared length.")
        out.extend(chunk)
        remaining[0] -= len(chunk)
    return bytes(out)


def _read_body(body: object, headers: dict[str, str]) -> bytes:  # noqa: C901 - reviewed ceiling 17; see docs/complexity-baseline.json
    if headers.get("content-encoding", "identity").strip().lower() not in ("", "identity"):
        raise RemoteCollectionError("Compressed remote collections are not supported.")

    transfer = headers.get("transfer-encoding", "").strip().lower()
    declared = headers.get("content-length")
    if transfer:
        if transfer != "chunked" or declared is not None:
            raise RemoteCollectionError("Unsupported remote response framing.")
        # Allow a bounded amount of wire framing overhead, not an unlimited transfer.
        remaining = [MAX_FILE_BYTES + 65536]
        output = bytearray()
        while True:
            raw = _read_line(body, remaining)
            token = raw.split(b";", 1)[0].strip()
            try:
                if not token or any(c not in b"0123456789abcdefABCDEF" for c in token):
                    raise ValueError
                size = int(token, 16)
            except ValueError as exc:
                raise RemoteCollectionError("Invalid chunk length.") from exc
            if size == 0:
                # Reject trailers to avoid ambiguous or unbounded trailer processing.
                if _read_line(body, remaining):
                    raise RemoteCollectionError("Remote response trailers are not supported.")
                return bytes(output)
            if size > MAX_FILE_BYTES - len(output):
                raise RemoteCollectionError("Remote collection exceeds 1 MiB.")
            output.extend(_read_exact(body, size, remaining))
            if _read_exact(body, 2, remaining) != b"\r\n":
                raise RemoteCollectionError("Invalid chunk terminator.")

    if declared is not None:
        if not declared.isascii() or not declared.isdecimal():
            raise RemoteCollectionError("Invalid Content-Length header.")
        count = int(declared)
        if count > MAX_FILE_BYTES:
            raise RemoteCollectionError("Remote collection exceeds 1 MiB.")
        return _read_exact(body, count, [MAX_FILE_BYTES + 1])

    data = bytearray()
    while True:
        chunk = body.read(min(65536, MAX_FILE_BYTES + 1 - len(data)))  # type: ignore[attr-defined]
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > MAX_FILE_BYTES:
            raise RemoteCollectionError("Remote collection exceeds 1 MiB.")


def fetch_remote_station_collection(
    url: str,
    resolver: StreamTargetResolver,
    *,
    policy: MetadataFetchPolicy | None = None,
    transport: ProtectedHTTPTransport | None = None,
) -> bytes:
    """Fetch one immutable bounded snapshot, never persisting it or fetching twice."""
    active_policy = policy or MetadataFetchPolicy()
    active_transport = transport or ProtectedHTTPTransport()
    start = time.monotonic()
    target = normalize_stream_target(url, active_policy)

    for redirect_index in range(active_policy.max_redirects + 1):
        addresses = validate_resolved_target(target, resolver, active_policy)
        remaining = active_policy.total_timeout_seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise RemoteCollectionError("Remote download timed out.")
        response = active_transport.request(target, addresses[0], active_policy, remaining)
        try:
            if 300 <= response.status < 400:
                location = response.headers.get("location")
                if not location or redirect_index >= active_policy.max_redirects:
                    raise RemoteCollectionError("Remote redirect missing or limit exceeded.")
                redirect = normalize_stream_target(urljoin(target.url, location), active_policy)
                if (
                    target.scheme == "https"
                    and redirect.scheme == "http"
                    and not active_policy.allow_https_to_http_redirect
                ):
                    raise RemoteCollectionError("HTTPS-to-HTTP redirect is not allowed.")
                target = redirect
                continue
            if not 200 <= response.status < 300:
                raise RemoteCollectionError(f"Remote collection returned HTTP {response.status}.")
            data = _read_body(response.body, response.headers)
            if not data:
                raise RemoteCollectionError("Remote collection is empty.")
            # Only supported station collections are accepted; an HTML response is not enough.
            preview = parse_station_collection(data)
            if not preview.entries:
                raise RemoteCollectionError("Remote collection contains no valid stations.")
            return data
        finally:
            response.close()
    raise RemoteCollectionError("Remote redirect limit exceeded.")


@dataclass(frozen=True, slots=True)
class ConditionalCollectionResult:
    """A complete HTTP 200 snapshot, or a validated HTTP 304 result."""

    status: int
    data: bytes | None
    etag: str | None = None
    last_modified: str | None = None


def _safe_cache_validator(value: str | None) -> str | None:
    """Never persist unbounded or unsafe remote cache metadata."""
    if not isinstance(value, str):
        return None
    if not 1 <= len(value) <= 512:
        return None
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        return None
    return value


def fetch_conditional_remote_station_collection(
    url: str,
    resolver: StreamTargetResolver,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
    policy: MetadataFetchPolicy | None = None,
    transport: ProtectedHTTPTransport | None = None,
) -> ConditionalCollectionResult:
    """Fetch or revalidate a catalog over the existing protected transport.

    Validators apply only to the original resource. Redirects are revalidated
    as usual, but receive neither the origin validators nor their cache state.
    """
    active_policy = policy or MetadataFetchPolicy()
    active_transport = transport or ProtectedHTTPTransport()
    start = time.monotonic()
    target = normalize_stream_target(url, active_policy)

    conditional_etag = _safe_cache_validator(etag)
    conditional_date = _safe_cache_validator(last_modified)
    if etag is not None and conditional_etag is None:
        raise RemoteCollectionError("Invalid stored ETag.")
    if last_modified is not None and conditional_date is None:
        raise RemoteCollectionError("Invalid stored Last-Modified.")

    redirected = False
    for redirect_index in range(active_policy.max_redirects + 1):
        addresses = validate_resolved_target(target, resolver, active_policy)
        remaining = active_policy.total_timeout_seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise RemoteCollectionError("Remote download timed out.")

        # Do not leak validators to a redirect destination.
        response = active_transport.request(
            target,
            addresses[0],
            active_policy,
            remaining,
            if_none_match=None if redirected else conditional_etag,
            if_modified_since=None if redirected else conditional_date,
        )
        try:
            if response.status == 304:
                if redirected or not (conditional_etag or conditional_date):
                    raise RemoteCollectionError(
                        "Unexpected HTTP 304 without a matching cache request."
                    )
                return ConditionalCollectionResult(
                    status=304,
                    data=None,
                )

            if 300 <= response.status < 400:
                location = response.headers.get("location")
                if not location or redirect_index >= active_policy.max_redirects:
                    raise RemoteCollectionError("Remote redirect missing or limit exceeded.")
                redirect = normalize_stream_target(
                    urljoin(target.url, location),
                    active_policy,
                )
                if (
                    target.scheme == "https"
                    and redirect.scheme == "http"
                    and not active_policy.allow_https_to_http_redirect
                ):
                    raise RemoteCollectionError("HTTPS-to-HTTP redirect is not allowed.")
                target = redirect
                redirected = True
                continue

            if not 200 <= response.status < 300:
                raise RemoteCollectionError(f"Remote collection returned HTTP {response.status}.")

            data = _read_body(response.body, response.headers)
            if not data:
                raise RemoteCollectionError("Remote collection is empty.")

            preview = parse_station_collection(data)
            if not preview.entries or preview.issues:
                raise RemoteCollectionError("Remote collection has no complete valid snapshot.")

            # A redirected response's validators belong to its target,
            # not necessarily to the original subscribed URL.
            return ConditionalCollectionResult(
                status=200,
                data=data,
                etag=(None if redirected else _safe_cache_validator(response.headers.get("etag"))),
                last_modified=(
                    None
                    if redirected
                    else _safe_cache_validator(response.headers.get("last-modified"))
                ),
            )
        finally:
            response.close()

    raise RemoteCollectionError("Remote redirect limit exceeded.")


def preview_remote_station_collection(
    url: str,
    resolver: StreamTargetResolver,
    *,
    policy: MetadataFetchPolicy | None = None,
    transport: ProtectedHTTPTransport | None = None,
) -> tuple[bytes, M3UPreview]:
    """Return bytes and parsed preview from the same single download."""
    data = fetch_remote_station_collection(url, resolver, policy=policy, transport=transport)
    return data, parse_station_collection(data)
