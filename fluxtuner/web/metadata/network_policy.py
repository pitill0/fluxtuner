# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import ipaddress
import socket

from .contracts import (
    DestinationDecision,
    MetadataFetchPolicy,
    NetworkAddressScope,
    NormalizedStreamTarget,
    ResolvedAddress,
    StreamTargetResolver,
)

_SHARED_IPV4_NETWORK = ipaddress.ip_network("100.64.0.0/10")
_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
)


class StreamTargetResolutionError(RuntimeError):
    """Raised when a stream hostname cannot be resolved safely."""


class StreamTargetBlockedError(ValueError):
    """Raised when any resolved destination violates the Web network policy."""


class SystemStreamTargetResolver:
    """Resolve stream targets through the system resolver without opening sockets."""

    def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
        try:
            results = socket.getaddrinfo(
                hostname,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except socket.gaierror as exc:
            raise StreamTargetResolutionError("Stream hostname resolution failed.") from exc

        addresses: list[ResolvedAddress] = []
        seen: set[tuple[socket.AddressFamily, str]] = set()
        for family_value, _socktype, _proto, _canonname, sockaddr in results:
            family = socket.AddressFamily(family_value)
            if family not in {socket.AddressFamily.AF_INET, socket.AddressFamily.AF_INET6}:
                continue
            address = str(sockaddr[0])
            key = (family, address)
            if key in seen:
                continue
            seen.add(key)
            addresses.append(
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=family,
                    address=address,
                    scope=classify_network_address(address),
                )
            )

        if not addresses:
            raise StreamTargetResolutionError("Stream hostname returned no usable addresses.")
        return tuple(addresses)


def classify_network_address(value: str) -> NetworkAddressScope:
    """Classify one IPv4 or IPv6 address for the Web metadata SSRF policy."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise StreamTargetResolutionError("Resolver returned an invalid IP address.") from exc

    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped

    if isinstance(address, ipaddress.IPv4Address) and address in _SHARED_IPV4_NETWORK:
        return NetworkAddressScope.SHARED
    if address.is_unspecified:
        return NetworkAddressScope.UNSPECIFIED
    if address.is_loopback:
        return NetworkAddressScope.LOOPBACK
    if address.is_link_local:
        return NetworkAddressScope.LINK_LOCAL
    if address.is_multicast:
        return NetworkAddressScope.MULTICAST
    if any(address in network for network in _DOCUMENTATION_NETWORKS):
        return NetworkAddressScope.RESERVED
    if address.is_private:
        return NetworkAddressScope.PRIVATE
    if address.is_reserved or not address.is_global:
        return NetworkAddressScope.RESERVED
    return NetworkAddressScope.GLOBAL


def validate_resolved_target(
    target: NormalizedStreamTarget,
    resolver: StreamTargetResolver,
    policy: MetadataFetchPolicy | None = None,
) -> tuple[ResolvedAddress, ...]:
    """Resolve a normalized target and require every candidate to be global."""
    active_policy = policy or MetadataFetchPolicy()
    addresses = resolver.resolve(target.hostname, target.port)
    if not addresses:
        raise StreamTargetResolutionError("Stream hostname returned no addresses.")

    if active_policy.require_all_resolved_addresses_global:
        blocked = [
            address for address in addresses if address.decision is DestinationDecision.BLOCK
        ]
        if blocked:
            raise StreamTargetBlockedError("Stream hostname resolves to a blocked destination.")

    return addresses
