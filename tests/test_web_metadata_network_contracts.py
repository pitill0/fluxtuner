from __future__ import annotations

import socket
from dataclasses import FrozenInstanceError

import pytest

from fluxtuner.web.metadata.contracts import (
    DestinationDecision,
    MetadataFetchPolicy,
    NetworkAddressScope,
    NormalizedStreamTarget,
    RedirectDecision,
    ResolvedAddress,
    StreamTargetResolver,
)


def test_metadata_fetch_policy_defines_conservative_network_limits() -> None:
    policy = MetadataFetchPolicy()

    assert policy.allowed_schemes == frozenset({"http", "https"})
    assert policy.max_url_length == 2048
    assert policy.max_redirects == 3
    assert policy.allow_https_to_http_redirect is False
    assert policy.require_all_resolved_addresses_global is True
    assert policy.connect_timeout_seconds == 2.0
    assert policy.read_timeout_seconds == 2.0
    assert policy.total_timeout_seconds == 5.0
    assert policy.max_response_header_bytes == 32 * 1024
    assert policy.max_icy_metadata_interval_bytes == 1024 * 1024
    assert policy.max_icy_metadata_block_bytes == 4080


def test_metadata_fetch_policy_is_immutable() -> None:
    policy = MetadataFetchPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_redirects = 4  # type: ignore[misc]


def test_only_global_addresses_are_allowed_by_contract() -> None:
    for scope in NetworkAddressScope:
        address = ResolvedAddress(
            hostname="radio.example",
            port=443,
            family=socket.AddressFamily.AF_INET,
            address="8.8.8.8",
            scope=scope,
        )

        expected = (
            DestinationDecision.ALLOW
            if scope is NetworkAddressScope.GLOBAL
            else DestinationDecision.BLOCK
        )
        assert address.decision is expected


def test_network_address_scope_names_are_stable_api_values() -> None:
    assert {scope.value for scope in NetworkAddressScope} == {
        "global",
        "loopback",
        "private",
        "shared",
        "link_local",
        "multicast",
        "unspecified",
        "reserved",
    }


def test_redirect_contract_rejects_or_allows_explicitly() -> None:
    assert RedirectDecision.ALLOW.value == "allow"
    assert RedirectDecision.REJECT.value == "reject"


def test_normalized_target_keeps_connection_identity_explicit() -> None:
    target = NormalizedStreamTarget(
        url="https://radio.example:8443/live",
        scheme="https",
        hostname="radio.example",
        port=8443,
    )

    assert target.url == "https://radio.example:8443/live"
    assert target.scheme == "https"
    assert target.hostname == "radio.example"
    assert target.port == 8443


def test_resolver_contract_returns_classified_addresses() -> None:
    class FakeResolver:
        def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
            return (
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AddressFamily.AF_INET6,
                    address="2001:4860:4860::8888",
                    scope=NetworkAddressScope.GLOBAL,
                ),
            )

    resolver: StreamTargetResolver = FakeResolver()
    results = resolver.resolve("radio.example", 443)

    assert len(results) == 1
    assert results[0].hostname == "radio.example"
    assert results[0].decision is DestinationDecision.ALLOW
