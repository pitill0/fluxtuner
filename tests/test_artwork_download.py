"""Offline artwork security, redirect, and framing contracts."""

from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from pathlib import Path

import pytest

from fluxtuner.core.artwork_download import ArtworkDownloadError, download_artwork
from fluxtuner.core.artwork_validation import MAX_ARTWORK_BYTES
from fluxtuner.network.contracts import ResolvedAddress
from fluxtuner.network.network_policy import classify_network_address

JPEG = (Path(__file__).parent / "fixtures" / "artwork" / "sample.jpg").read_bytes()


class Response:
    def __init__(
        self, status: int = 200, headers: dict[str, str] | None = None, data: bytes = JPEG
    ):
        self.status = status
        self.headers = headers or {}
        self.body = BytesIO(data)
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.body.close()


class Transport:
    def __init__(self, *responses: Response):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, bool]] = []

    def request(self, target, address, policy, timeout, *, icy_metadata=True):
        self.calls.append((target.hostname, address.address, icy_metadata))
        return self.responses.pop(0)


class Resolver:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def resolve(self, hostname, port):
        self.calls.append((hostname, port))
        try:
            address = str(ipaddress.ip_address(hostname))
        except ValueError:
            address = "8.8.8.8" if hostname == "radio.example" else "1.1.1.1"
        return (
            ResolvedAddress(
                hostname=hostname,
                port=port,
                family=socket.AF_INET,
                address=address,
                scope=classify_network_address(address),
            ),
        )


def test_artwork_download_without_icy_header() -> None:
    transport = Transport(Response(headers={"content-type": "image/jpeg"}))
    result = download_artwork("https://radio.example/logo", Resolver(), transport=transport)
    assert result.data == JPEG
    assert result.mime_type == "image/jpeg"
    assert transport.calls == [("radio.example", "8.8.8.8", False)]


def test_redirect_revalidated_and_connection_pinned() -> None:
    resolver = Resolver()
    transport = Transport(Response(302, {"location": "https://cdn.example/logo"}), Response())
    assert (
        download_artwork("https://radio.example/logo", resolver, transport=transport).data == JPEG
    )
    assert resolver.calls == [("radio.example", 443), ("cdn.example", 443)]
    assert [call[1] for call in transport.calls] == ["8.8.8.8", "1.1.1.1"]


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "192.168.1.1", "::1"])
def test_private_destinations_blocked_before_connect(address: str) -> None:
    transport = Transport()
    with pytest.raises(ValueError, match="blocked destination"):
        download_artwork(
            f"http://[{address}]/logo" if ":" in address else f"http://{address}/logo",
            Resolver(),
            transport=transport,
        )
    assert not transport.calls


def test_https_downgrade_blocked() -> None:
    transport = Transport(Response(302, {"location": "http://cdn.example/logo"}))
    with pytest.raises(ArtworkDownloadError, match="HTTPS-to-HTTP"):
        download_artwork("https://radio.example/logo", Resolver(), transport=transport)
    assert len(transport.calls) == 1


def test_mixed_public_and_private_dns_results_are_blocked() -> None:
    class MixedResolver:
        def resolve(self, hostname, port):
            return tuple(
                ResolvedAddress(
                    hostname=hostname,
                    port=port,
                    family=socket.AF_INET,
                    address=address,
                    scope=classify_network_address(address),
                )
                for address in ("8.8.8.8", "127.0.0.1")
            )

    transport = Transport()
    with pytest.raises(ValueError, match="blocked destination"):
        download_artwork("https://radio.example/logo", MixedResolver(), transport=transport)
    assert not transport.calls


@pytest.mark.parametrize(
    "headers", [{"content-type": "text/html"}, {"content-type": "image/svg+xml"}]
)
def test_active_content_type_blocked(headers: dict[str, str]) -> None:
    with pytest.raises(ArtworkDownloadError, match="Content-Type"):
        download_artwork(
            "https://radio.example/logo", Resolver(), transport=Transport(Response(headers=headers))
        )


def test_mismatched_mime_rejected() -> None:
    with pytest.raises(ArtworkDownloadError, match="mismatched"):
        download_artwork(
            "https://radio.example/logo",
            Resolver(),
            transport=Transport(Response(headers={"content-type": "image/png"})),
        )


def test_content_length_over_limit_rejected_before_read() -> None:
    transport = Transport(Response(headers={"content-length": str(MAX_ARTWORK_BYTES + 1)}))
    with pytest.raises(ArtworkDownloadError, match="maximum size"):
        download_artwork("https://radio.example/logo", Resolver(), transport=transport)


def test_truncated_content_length_rejected() -> None:
    transport = Transport(Response(headers={"content-length": str(len(JPEG) + 1)}))
    with pytest.raises(ArtworkDownloadError, match="prematurely"):
        download_artwork("https://radio.example/logo", Resolver(), transport=transport)


def test_chunked_artwork_decoded() -> None:
    framed = f"{len(JPEG):x}\r\n".encode() + JPEG + b"\r\n0\r\n\r\n"
    transport = Transport(Response(headers={"transfer-encoding": "chunked"}, data=framed))
    assert (
        download_artwork("https://radio.example/logo", Resolver(), transport=transport).data == JPEG
    )


@pytest.mark.parametrize(
    "headers,data",
    [
        ({"transfer-encoding": "chunked"}, b"xyz\r\n"),
        ({"transfer-encoding": "chunked", "content-length": "25"}, JPEG),
        ({"content-encoding": "gzip"}, JPEG),
    ],
)
def test_bad_framing_or_encoding_rejected(headers: dict[str, str], data: bytes) -> None:
    with pytest.raises(ArtworkDownloadError):
        download_artwork(
            "https://radio.example/logo",
            Resolver(),
            transport=Transport(Response(headers=headers, data=data)),
        )


def test_non_image_payload_rejected() -> None:
    with pytest.raises(ArtworkDownloadError, match="Invalid"):
        download_artwork(
            "https://radio.example/logo",
            Resolver(),
            transport=Transport(Response(data=b"<html>oops</html>")),
        )


def test_response_closed_on_failure() -> None:
    response = Response(headers={"content-type": "text/html"})
    with pytest.raises(ArtworkDownloadError):
        download_artwork("https://radio.example/logo", Resolver(), transport=Transport(response))
    assert response.closed
