# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Offline security and framing contracts for remote playlist downloads."""

from __future__ import annotations

from io import BytesIO

import pytest

from fluxtuner.web import remote_station_collection as remote

M3U = b"#EXTM3U\n#EXTINF:-1,Example\nhttps://radio.example/stream\n"
PLS = b"[playlist]\nNumberOfEntries=1\nFile1=https://radio.example/stream\nTitle1=Example\n"


class Response:
    def __init__(self, status=200, headers=None, data=M3U):
        self.status = status
        self.headers = headers or {}
        self.body = BytesIO(data)
        self.closed = False

    def close(self):
        self.closed = True
        self.body.close()


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, target, address, policy, timeout):
        self.calls.append((target.hostname, address.address, timeout))
        return self.responses.pop(0)


class Resolver:
    def __init__(self):
        self.calls = []

    def resolve(self, hostname, port):
        self.calls.append((hostname, port))
        # Use the already-tested network-policy classification; never open a socket.
        import ipaddress
        import socket

        from fluxtuner.web.metadata.contracts import ResolvedAddress
        from fluxtuner.web.metadata.network_policy import classify_network_address

        try:
            addr = str(ipaddress.ip_address(hostname))
        except ValueError:
            addr = "8.8.8.8" if hostname == "radio.example" else "1.1.1.1"
        return (
            ResolvedAddress(
                hostname=hostname,
                port=port,
                family=socket.AF_INET,
                address=addr,
                scope=classify_network_address(addr),
            ),
        )


@pytest.mark.parametrize("payload", [M3U, PLS])
def test_valid_snapshot_downloaded_once(payload):
    transport = Transport(Response(data=payload))
    data, preview = remote.preview_remote_station_collection(
        "https://radio.example/list", Resolver(), transport=transport
    )
    assert data == payload
    assert len(preview.entries) == 1
    assert len(transport.calls) == 1


def test_redirect_is_revalidated_and_reconnected_to_new_ip():
    resolver = Resolver()
    transport = Transport(Response(302, {"location": "https://cdn.example/list"}), Response())
    assert (
        remote.fetch_remote_station_collection(
            "https://radio.example/list", resolver, transport=transport
        )
        == M3U
    )
    assert resolver.calls == [("radio.example", 443), ("cdn.example", 443)]
    assert [call[1] for call in transport.calls] == ["8.8.8.8", "1.1.1.1"]


def test_https_downgrade_rejected():
    transport = Transport(Response(302, {"location": "http://cdn.example/list"}))
    with pytest.raises(remote.RemoteCollectionError, match="HTTPS-to-HTTP"):
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )


def test_private_literal_ip_rejected_without_transport():
    transport = Transport()
    with pytest.raises(ValueError):
        remote.fetch_remote_station_collection(
            "http://127.0.0.1/list", Resolver(), transport=transport
        )
    assert not transport.calls


def test_oversized_content_length_rejected():
    transport = Transport(Response(headers={"content-length": "1048577"}))
    with pytest.raises(remote.RemoteCollectionError, match="1 MiB"):
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )


def test_truncated_declared_body_rejected():
    transport = Transport(Response(headers={"content-length": "99"}))
    with pytest.raises(remote.RemoteCollectionError, match="declared length"):
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )


def test_chunked_playlist_decoded():
    framed = f"{len(PLS):x}\r\n".encode() + PLS + b"\r\n0\r\n\r\n"
    transport = Transport(Response(headers={"transfer-encoding": "chunked"}, data=framed))
    assert (
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )
        == PLS
    )


def test_invalid_chunk_framing_rejected():
    transport = Transport(Response(headers={"transfer-encoding": "chunked"}, data=b"xyz\r\n"))
    with pytest.raises(remote.RemoteCollectionError, match="chunk length"):
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )


def test_html_without_stations_rejected():
    transport = Transport(Response(data=b"<!doctype html><html>no stations</html>"))
    with pytest.raises(remote.RemoteCollectionError, match="no valid stations"):
        remote.fetch_remote_station_collection(
            "https://radio.example/list", Resolver(), transport=transport
        )


def test_mixed_dns_addresses_are_rejected_before_connect():
    import socket

    from fluxtuner.web.metadata.contracts import ResolvedAddress
    from fluxtuner.web.metadata.network_policy import classify_network_address

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
        remote.fetch_remote_station_collection(
            "https://radio.example/list",
            MixedResolver(),
            transport=transport,
        )
    assert transport.calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"content-length": str(len(M3U))},
        {},
    ],
)
def test_complete_http_body_preserved(headers):
    transport = Transport(Response(headers=headers, data=M3U))
    result = remote.fetch_remote_station_collection(
        "https://radio.example/list",
        Resolver(),
        transport=transport,
    )
    assert result == M3U
    assert len(transport.calls) == 1
