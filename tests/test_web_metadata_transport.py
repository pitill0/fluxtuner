from __future__ import annotations

import socket
from io import BytesIO
from typing import Any

import pytest

from fluxtuner.web.metadata.client import (
    MetadataRedirectError,
    fetch_protected_stream_metadata,
)
from fluxtuner.web.metadata.contracts import (
    MetadataFetchPolicy,
    NetworkAddressScope,
    ResolvedAddress,
)
from fluxtuner.web.metadata.transport import (
    MetadataResponseError,
    MetadataTransportError,
    ProtectedHTTPResponse,
    ProtectedHTTPTransport,
    SystemStreamSocketFactory,
)
from fluxtuner.web.metadata.urls import normalize_stream_target


class FakeResolver:
    def __init__(self, addresses: dict[str, str]) -> None:
        self.addresses = addresses
        self.calls: list[tuple[str, int]] = []

    def resolve(self, hostname: str, port: int) -> tuple[ResolvedAddress, ...]:
        self.calls.append((hostname, port))
        return (
            ResolvedAddress(
                hostname=hostname,
                port=port,
                family=socket.AddressFamily.AF_INET,
                address=self.addresses[hostname],
                scope=NetworkAddressScope.GLOBAL,
            ),
        )


class FakeTransport:
    def __init__(self, responses: list[ProtectedHTTPResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, float]] = []

    def request(
        self,
        target: Any,
        address: ResolvedAddress,
        policy: MetadataFetchPolicy,
        timeout: float,
    ) -> ProtectedHTTPResponse:
        self.calls.append((target.url, address.address, timeout))
        return self.responses.pop(0)


class FakeConnectedStream:
    def __init__(self, response: bytes, *, max_chunk_size: int | None = None) -> None:
        self.response = bytearray(response)
        self.max_chunk_size = max_chunk_size
        self.sent = bytearray()
        self.timeout: float | None = None
        self.closed = False

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, size: int) -> bytes:
        if self.max_chunk_size is not None:
            size = min(size, self.max_chunk_size)
        chunk = bytes(self.response[:size])
        del self.response[:size]
        return chunk

    def settimeout(self, value: float | None) -> None:
        self.timeout = value

    def close(self) -> None:
        self.closed = True


class FakeSocketFactory:
    def __init__(self, stream: FakeConnectedStream) -> None:
        self.stream = stream
        self.calls: list[tuple[str, str, int, float]] = []

    def open(
        self,
        target: Any,
        address: ResolvedAddress,
        timeout: float,
    ) -> FakeConnectedStream:
        self.calls.append((target.hostname, address.address, target.port, timeout))
        return self.stream


def icy_body(title: str, metaint: int = 4) -> bytes:
    metadata = f"StreamTitle='{title}';".encode()
    blocks = (len(metadata) + 15) // 16
    return b"a" * metaint + bytes([blocks]) + metadata.ljust(blocks * 16, b"\0")


def response(
    status: int,
    headers: dict[str, str],
    body: bytes = b"",
) -> ProtectedHTTPResponse:
    return ProtectedHTTPResponse(status=status, headers=headers, body=BytesIO(body))


def test_transport_connects_to_validated_address_and_preserves_host() -> None:
    stream = FakeConnectedStream(
        b"HTTP/1.1 200 OK\r\nicy-metaint: 4\r\n\r\n" + icy_body("Artist - Song")
    )
    factory = FakeSocketFactory(stream)
    transport = ProtectedHTTPTransport(factory)
    resolver = FakeResolver({"radio.example": "8.8.8.8"})

    result = fetch_protected_stream_metadata(
        "https://radio.example/live?x=1",
        resolver,
        transport=transport,
    )

    assert result == {
        "raw": "Artist - Song",
        "artist": "Artist",
        "title": "Song",
        "source": "icy",
    }
    assert factory.calls[0][0:3] == ("radio.example", "8.8.8.8", 443)
    assert b"GET /live?x=1 HTTP/1.1\r\n" in stream.sent
    assert b"Host: radio.example\r\n" in stream.sent
    assert b"Icy-MetaData: 1\r\n" in stream.sent
    assert stream.closed is True


def test_transport_percent_encodes_unicode_request_target() -> None:
    stream = FakeConnectedStream(
        b"HTTP/1.1 200 OK\r\nicy-metaint: 4\r\n\r\n" + icy_body("Artist - Song")
    )
    factory = FakeSocketFactory(stream)
    transport = ProtectedHTTPTransport(factory)
    resolver = FakeResolver({"radio.example": "8.8.8.8"})

    result = fetch_protected_stream_metadata(
        "https://radio.example/canción?q=señal",
        resolver,
        transport=transport,
    )

    assert result is not None
    assert b"GET /canci%C3%B3n?q=se%C3%B1al HTTP/1.1\r\n" in stream.sent


def test_system_socket_factory_closes_tcp_stream_when_tls_wrap_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = FakeConnectedStream(b"")

    class FailingSSLContext:
        def wrap_socket(
            self,
            connected_stream: FakeConnectedStream,
            *,
            server_hostname: str,
        ) -> FakeConnectedStream:
            assert connected_stream is stream
            assert server_hostname == "radio.example"
            raise OSError("TLS handshake failed")

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: stream,
    )
    factory = SystemStreamSocketFactory(
        ssl_context=FailingSSLContext(),  # type: ignore[arg-type]
    )
    target = normalize_stream_target("https://radio.example/live")
    address = ResolvedAddress(
        hostname="radio.example",
        port=443,
        family=socket.AddressFamily.AF_INET,
        address="8.8.8.8",
        scope=NetworkAddressScope.GLOBAL,
    )

    with pytest.raises(MetadataTransportError, match="connection failed"):
        factory.open(target, address, 1.0)

    assert stream.closed is True


def test_redirect_is_revalidated_and_uses_new_validated_address() -> None:
    resolver = FakeResolver(
        {
            "radio.example": "8.8.8.8",
            "cdn.example": "1.1.1.1",
        }
    )
    transport = FakeTransport(
        [
            response(302, {"location": "https://cdn.example/live"}),
            response(200, {"icy-metaint": "4"}, icy_body("Artist - Song")),
        ]
    )

    result = fetch_protected_stream_metadata(
        "https://radio.example/start",
        resolver,
        transport=transport,  # type: ignore[arg-type]
    )

    assert result is not None
    assert resolver.calls == [("radio.example", 443), ("cdn.example", 443)]
    assert [call[1] for call in transport.calls] == ["8.8.8.8", "1.1.1.1"]


def test_https_to_http_redirect_is_rejected() -> None:
    resolver = FakeResolver({"radio.example": "8.8.8.8"})
    transport = FakeTransport([response(302, {"location": "http://radio.example/live"})])

    with pytest.raises(MetadataRedirectError, match="HTTPS-to-HTTP"):
        fetch_protected_stream_metadata(
            "https://radio.example/start",
            resolver,
            transport=transport,  # type: ignore[arg-type]
        )


def test_redirect_limit_is_enforced() -> None:
    resolver = FakeResolver({"radio.example": "8.8.8.8"})
    transport = FakeTransport(
        [
            response(302, {"location": "/one"}),
            response(302, {"location": "/two"}),
        ]
    )
    policy = MetadataFetchPolicy(max_redirects=1)

    with pytest.raises(MetadataRedirectError, match="limit"):
        fetch_protected_stream_metadata(
            "https://radio.example/start",
            resolver,
            policy=policy,
            transport=transport,  # type: ignore[arg-type]
        )


def test_missing_icy_metadata_returns_none() -> None:
    resolver = FakeResolver({"radio.example": "8.8.8.8"})
    transport = FakeTransport([response(200, {})])

    assert (
        fetch_protected_stream_metadata(
            "https://radio.example/live",
            resolver,
            transport=transport,  # type: ignore[arg-type]
        )
        is None
    )


def test_total_budget_is_enforced_across_multiple_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = -1.0

    def monotonic() -> float:
        nonlocal current
        current += 1.0
        return current

    monkeypatch.setattr(
        "fluxtuner.web.metadata.transport.time.monotonic",
        monotonic,
    )
    stream = FakeConnectedStream(
        b"HTTP/1.1 200 OK\r\nicy-metaint: 4\r\n\r\n" + icy_body("Artist - Song"),
        max_chunk_size=1,
    )
    factory = FakeSocketFactory(stream)
    transport = ProtectedHTTPTransport(factory)
    resolver = FakeResolver({"radio.example": "8.8.8.8"})
    policy = MetadataFetchPolicy(total_timeout_seconds=5.0)

    with pytest.raises(MetadataTransportError, match="budget"):
        fetch_protected_stream_metadata(
            "http://radio.example/live",
            resolver,
            policy=policy,
            transport=transport,
        )

    assert stream.closed is True


def test_transport_rejects_oversized_headers() -> None:
    policy = MetadataFetchPolicy(max_response_header_bytes=64)
    stream = FakeConnectedStream(b"HTTP/1.1 200 OK\r\nX-Test: " + b"a" * 80 + b"\r\n\r\n")
    factory = FakeSocketFactory(stream)
    transport = ProtectedHTTPTransport(factory)
    resolver = FakeResolver({"radio.example": "8.8.8.8"})

    with pytest.raises(MetadataResponseError, match="headers"):
        fetch_protected_stream_metadata(
            "http://radio.example/live",
            resolver,
            policy=policy,
            transport=transport,
        )
    assert stream.closed is True


def test_unexpected_status_is_rejected() -> None:
    resolver = FakeResolver({"radio.example": "8.8.8.8"})
    transport = FakeTransport([response(500, {})])

    with pytest.raises(MetadataResponseError, match="unexpected status"):
        fetch_protected_stream_metadata(
            "https://radio.example/live",
            resolver,
            transport=transport,  # type: ignore[arg-type]
        )
