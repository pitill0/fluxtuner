# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

from fluxtuner.core.stream_metadata import (
    parse_icy_metadata_block,
    parse_icy_metaint,
    read_icy_metadata_block,
)

from .contracts import MetadataFetchPolicy, StreamTargetResolver
from .network_policy import validate_resolved_target
from .transport import MetadataResponseError, MetadataTransportError, ProtectedHTTPTransport
from .urls import normalize_stream_target


class MetadataRedirectError(RuntimeError):
    """Raised when a metadata redirect violates policy or exceeds its budget."""


def _remaining_budget(started_at: float, policy: MetadataFetchPolicy) -> float:
    return policy.total_timeout_seconds - (time.monotonic() - started_at)


def fetch_protected_stream_metadata(
    raw_url: str,
    resolver: StreamTargetResolver,
    *,
    policy: MetadataFetchPolicy | None = None,
    transport: ProtectedHTTPTransport | None = None,
) -> dict[str, Any] | None:
    """Fetch one ICY metadata block through the protected Web network boundary."""
    active_policy = policy or MetadataFetchPolicy()
    active_transport = transport or ProtectedHTTPTransport()
    started_at = time.monotonic()
    target = normalize_stream_target(raw_url, active_policy)

    for redirect_count in range(active_policy.max_redirects + 1):
        addresses = validate_resolved_target(target, resolver, active_policy)
        address = addresses[0]
        remaining = _remaining_budget(started_at, active_policy)
        if remaining <= 0:
            raise MetadataTransportError("Metadata request budget is exhausted.")

        response = active_transport.request(
            target,
            address,
            active_policy,
            remaining,
        )
        try:
            if 300 <= response.status < 400:
                location = response.headers.get("location")
                if not location:
                    raise MetadataRedirectError("Metadata redirect has no location.")
                if redirect_count >= active_policy.max_redirects:
                    raise MetadataRedirectError("Metadata redirect limit exceeded.")

                redirected = normalize_stream_target(
                    urljoin(target.url, location),
                    active_policy,
                )
                if (
                    target.scheme == "https"
                    and redirected.scheme == "http"
                    and not active_policy.allow_https_to_http_redirect
                ):
                    raise MetadataRedirectError("HTTPS-to-HTTP metadata redirect is not allowed.")
                target = redirected
                continue

            if response.status < 200 or response.status >= 300:
                raise MetadataResponseError("Remote stream returned an unexpected status.")

            metaint = parse_icy_metaint(response.headers.get("icy-metaint"))
            if metaint is None:
                return None
            if metaint > active_policy.max_icy_metadata_interval_bytes:
                raise MetadataResponseError("ICY metadata interval exceeds the safety limit.")

            metadata = read_icy_metadata_block(response.body, metaint)
            if metadata is None:
                return None
            if len(metadata) > active_policy.max_icy_metadata_block_bytes:
                raise MetadataResponseError("ICY metadata block exceeds the safety limit.")
            return parse_icy_metadata_block(metadata)
        finally:
            response.close()

    raise MetadataRedirectError("Metadata redirect limit exceeded.")
