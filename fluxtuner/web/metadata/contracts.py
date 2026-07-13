# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class NetworkAddressScope(StrEnum):
    """Security classification assigned to a resolved network address."""

    GLOBAL = "global"
    LOOPBACK = "loopback"
    PRIVATE = "private"
    SHARED = "shared"
    LINK_LOCAL = "link_local"
    MULTICAST = "multicast"
    UNSPECIFIED = "unspecified"
    RESERVED = "reserved"


class DestinationDecision(StrEnum):
    """Outcome of validating one stream destination."""

    ALLOW = "allow"
    BLOCK = "block"


class RedirectDecision(StrEnum):
    """Outcome of applying the redirect security policy."""

    ALLOW = "allow"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class MetadataFetchPolicy:
    """Immutable limits that every future metadata fetch must enforce."""

    allowed_schemes: frozenset[str] = field(default_factory=lambda: frozenset({"http", "https"}))
    max_url_length: int = 2048
    max_redirects: int = 3
    allow_https_to_http_redirect: bool = False
    require_all_resolved_addresses_global: bool = True
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 2.0
    total_timeout_seconds: float = 5.0
    max_response_header_bytes: int = 32 * 1024
    max_icy_metadata_interval_bytes: int = 1024 * 1024
    max_icy_metadata_block_bytes: int = 255 * 16


@dataclass(frozen=True, slots=True)
class NormalizedStreamTarget:
    """Canonical stream target produced before DNS resolution."""

    url: str
    scheme: str
    hostname: str
    port: int


@dataclass(frozen=True, slots=True)
class ResolvedAddress:
    """One DNS result together with its security classification."""

    hostname: str
    port: int
    family: socket.AddressFamily
    address: str
    scope: NetworkAddressScope

    @property
    def decision(self) -> DestinationDecision:
        if self.scope is NetworkAddressScope.GLOBAL:
            return DestinationDecision.ALLOW
        return DestinationDecision.BLOCK


class StreamTargetResolver(Protocol):
    """Injectable DNS boundary used by later network-policy work."""

    def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]: ...
