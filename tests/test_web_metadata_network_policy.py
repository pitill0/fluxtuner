from __future__ import annotations

import socket

import pytest

from fluxtuner.web.metadata.contracts import (
    MetadataFetchPolicy,
    NetworkAddressScope,
    ResolvedAddress,
)
from fluxtuner.web.metadata.network_policy import (
    StreamTargetBlockedError,
    StreamTargetResolutionError,
    SystemStreamTargetResolver,
    classify_network_address,
    validate_resolved_target,
)
from fluxtuner.web.metadata.urls import (
    StreamTargetValidationError,
    normalize_stream_target,
)


@pytest.mark.parametrize(
    ("raw_url", "expected_url", "hostname", "port"),
    [
        ("HTTP://Radio.Example", "http://radio.example/", "radio.example", 80),
        ("https://radio.example:443/live", "https://radio.example/live", "radio.example", 443),
        (
            "http://radio.example:8000/live?x=1",
            "http://radio.example:8000/live?x=1",
            "radio.example",
            8000,
        ),
        (
            "https://[2001:4860:4860::8888]/live",
            "https://[2001:4860:4860::8888]/live",
            "2001:4860:4860::8888",
            443,
        ),
        (
            "https://RÁDIO.example/live",
            "https://xn--rdio-5na.example/live",
            "xn--rdio-5na.example",
            443,
        ),
    ],
)
def test_normalize_stream_target_is_conservative(
    raw_url: str,
    expected_url: str,
    hostname: str,
    port: int,
) -> None:
    target = normalize_stream_target(raw_url)

    assert target.url == expected_url
    assert target.hostname == hostname
    assert target.port == port


@pytest.mark.parametrize(
    "raw_url",
    [
        "",
        "ftp://radio.example/live",
        "https://user:pass@radio.example/live",
        "https://radio.example/live#fragment",
        "https://radio.example:99999/live",
        "https://[fe80::1%25eth0]/live",
        "https://-radio.example/live",
        "https://radio..example/live",
        "https://radio_example/live",
        "https://radio example/live",
        "https://radio.example/\nstream",
    ],
)
def test_normalize_stream_target_rejects_unsafe_urls(raw_url: str) -> None:
    with pytest.raises(StreamTargetValidationError):
        normalize_stream_target(raw_url)


def test_normalize_stream_target_enforces_configured_length() -> None:
    policy = MetadataFetchPolicy(max_url_length=30)

    with pytest.raises(StreamTargetValidationError):
        normalize_stream_target("https://radio.example/very-long-stream-path", policy)


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("8.8.8.8", NetworkAddressScope.GLOBAL),
        ("2001:4860:4860::8888", NetworkAddressScope.GLOBAL),
        ("127.0.0.1", NetworkAddressScope.LOOPBACK),
        ("::1", NetworkAddressScope.LOOPBACK),
        ("10.0.0.1", NetworkAddressScope.PRIVATE),
        ("fc00::1", NetworkAddressScope.PRIVATE),
        ("100.64.0.1", NetworkAddressScope.SHARED),
        ("169.254.1.1", NetworkAddressScope.LINK_LOCAL),
        ("fe80::1", NetworkAddressScope.LINK_LOCAL),
        ("224.0.0.1", NetworkAddressScope.MULTICAST),
        ("ff02::1", NetworkAddressScope.MULTICAST),
        ("0.0.0.0", NetworkAddressScope.UNSPECIFIED),
        ("::", NetworkAddressScope.UNSPECIFIED),
        ("192.0.2.1", NetworkAddressScope.RESERVED),
        ("::ffff:127.0.0.1", NetworkAddressScope.LOOPBACK),
    ],
)
def test_classify_network_address_covers_security_scopes(
    address: str,
    expected: NetworkAddressScope,
) -> None:
    assert classify_network_address(address) is expected


def test_validate_resolved_target_allows_only_all_global_candidates() -> None:
    target = normalize_stream_target("https://radio.example/live")

    class Resolver:
        def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
            return (
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AddressFamily.AF_INET,
                    address="8.8.8.8",
                    scope=NetworkAddressScope.GLOBAL,
                ),
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AddressFamily.AF_INET6,
                    address="2001:4860:4860::8888",
                    scope=NetworkAddressScope.GLOBAL,
                ),
            )

    addresses = validate_resolved_target(target, Resolver())
    assert len(addresses) == 2


def test_validate_resolved_target_rejects_mixed_dns_answers() -> None:
    target = normalize_stream_target("https://radio.example/live")

    class Resolver:
        def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
            return (
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AddressFamily.AF_INET,
                    address="8.8.8.8",
                    scope=NetworkAddressScope.GLOBAL,
                ),
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AddressFamily.AF_INET,
                    address="127.0.0.1",
                    scope=NetworkAddressScope.LOOPBACK,
                ),
            )

    with pytest.raises(StreamTargetBlockedError):
        validate_resolved_target(target, Resolver())


def test_validate_resolved_target_rejects_empty_resolution() -> None:
    target = normalize_stream_target("https://radio.example/live")

    class Resolver:
        def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
            return ()

    with pytest.raises(StreamTargetResolutionError):
        validate_resolved_target(target, Resolver())


def test_system_resolver_classifies_and_deduplicates_without_opening_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_getaddrinfo(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
        calls.append((*args, kwargs))
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("::1", 443, 0, 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    addresses = SystemStreamTargetResolver().resolve("radio.example", 443)

    assert calls
    assert [(address.address, address.scope) for address in addresses] == [
        ("8.8.8.8", NetworkAddressScope.GLOBAL),
        ("::1", NetworkAddressScope.LOOPBACK),
    ]
