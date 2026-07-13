# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass
from io import RawIOBase
from typing import BinaryIO, Protocol, cast
from urllib.parse import quote, urlsplit

from .contracts import MetadataFetchPolicy, NormalizedStreamTarget, ResolvedAddress


class MetadataTransportError(RuntimeError):
    """Raised when a protected stream connection cannot be completed safely."""


class MetadataResponseError(RuntimeError):
    """Raised when a remote response violates the bounded HTTP contract."""


class ConnectedStream(Protocol):
    def sendall(self, data: bytes) -> None: ...

    def recv(self, size: int) -> bytes: ...

    def settimeout(self, value: float | None) -> None: ...

    def close(self) -> None: ...


class StreamSocketFactory(Protocol):
    def open(
        self,
        target: NormalizedStreamTarget,
        address: ResolvedAddress,
        timeout: float,
    ) -> ConnectedStream: ...


class SystemStreamSocketFactory:
    """Open a TCP/TLS stream to an exact previously validated address."""

    def __init__(self, ssl_context: ssl.SSLContext | None = None) -> None:
        self._ssl_context = ssl_context or ssl.create_default_context()

    def open(
        self,
        target: NormalizedStreamTarget,
        address: ResolvedAddress,
        timeout: float,
    ) -> ConnectedStream:
        stream: ConnectedStream | None = None
        try:
            stream = socket.create_connection(
                (address.address, target.port),
                timeout=timeout,
            )
            if target.scheme == "https":
                stream = self._ssl_context.wrap_socket(
                    stream,
                    server_hostname=target.hostname,
                )
            return stream
        except (OSError, ssl.SSLError) as exc:
            if stream is not None:
                stream.close()
            raise MetadataTransportError("Protected stream connection failed.") from exc


def _apply_remaining_timeout(
    stream: ConnectedStream,
    deadline: float,
    operation_limit: float,
) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise MetadataTransportError("Metadata request budget is exhausted.")
    stream.settimeout(min(remaining, operation_limit))


class _SocketBody(RawIOBase):
    def __init__(
        self,
        stream: ConnectedStream,
        initial: bytes,
        *,
        deadline: float,
        read_timeout: float,
    ) -> None:
        super().__init__()
        self._stream = stream
        self._buffer = bytearray(initial)
        self._deadline = deadline
        self._read_timeout = read_timeout

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            return b""
        if size is None or size < 0:
            raise ValueError("Unbounded reads are not allowed for metadata streams.")

        output = bytearray()
        if self._buffer:
            take = min(size, len(self._buffer))
            output.extend(self._buffer[:take])
            del self._buffer[:take]

        while len(output) < size:
            _apply_remaining_timeout(
                self._stream,
                self._deadline,
                self._read_timeout,
            )
            chunk = self._stream.recv(size - len(output))
            if not chunk:
                break
            output.extend(chunk)
        return bytes(output)

    def close(self) -> None:
        if not self.closed:
            self._stream.close()
        super().close()


@dataclass(slots=True)
class ProtectedHTTPResponse:
    status: int
    headers: dict[str, str]
    body: BinaryIO

    def close(self) -> None:
        self.body.close()


def _host_header(target: NormalizedStreamTarget) -> str:
    hostname = target.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"

    default_port = 443 if target.scheme == "https" else 80
    if target.port != default_port:
        return f"{hostname}:{target.port}"
    return hostname


def _request_target(target: NormalizedStreamTarget) -> str:
    parsed = urlsplit(target.url)
    path = quote(
        parsed.path or "/",
        safe="/:@!$&'()*+,;=-._~%",
    )
    if parsed.query:
        query = quote(
            parsed.query,
            safe="/?:@!$&'()*+,;=-._~%",
        )
        return f"{path}?{query}"
    return path


def _parse_response_head(
    payload: bytes,
    policy: MetadataFetchPolicy,
) -> tuple[int, dict[str, str], bytes]:
    marker = payload.find(b"\r\n\r\n")
    if marker < 0:
        raise MetadataResponseError("Remote response headers are incomplete.")
    if marker + 4 > policy.max_response_header_bytes:
        raise MetadataResponseError("Remote response headers exceed the safety limit.")

    head = payload[:marker].decode("iso-8859-1")
    body = payload[marker + 4 :]
    lines = head.split("\r\n")
    if not lines:
        raise MetadataResponseError("Remote response status line is missing.")

    status_parts = lines[0].split(" ", 2)
    if len(status_parts) < 2 or status_parts[0] not in {"HTTP/1.0", "HTTP/1.1", "ICY"}:
        raise MetadataResponseError("Remote response status line is invalid.")
    try:
        status = int(status_parts[1])
    except ValueError as exc:
        raise MetadataResponseError("Remote response status code is invalid.") from exc

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            raise MetadataResponseError("Remote response header is malformed.")
        name, value = line.split(":", 1)
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise MetadataResponseError("Remote response header name is empty.")
        normalized_value = value.strip()
        if normalized_name in headers:
            headers[normalized_name] = f"{headers[normalized_name]}, {normalized_value}"
        else:
            headers[normalized_name] = normalized_value

    return status, headers, body


class ProtectedHTTPTransport:
    """Perform one bounded request through an exact validated destination."""

    def __init__(self, socket_factory: StreamSocketFactory | None = None) -> None:
        self._socket_factory = socket_factory or SystemStreamSocketFactory()

    def request(
        self,
        target: NormalizedStreamTarget,
        address: ResolvedAddress,
        policy: MetadataFetchPolicy,
        timeout: float,
    ) -> ProtectedHTTPResponse:
        if timeout <= 0:
            raise MetadataTransportError("Metadata request budget is exhausted.")

        deadline = time.monotonic() + timeout
        connect_timeout = min(timeout, policy.connect_timeout_seconds)
        stream = self._socket_factory.open(target, address, connect_timeout)
        try:
            _apply_remaining_timeout(
                stream,
                deadline,
                policy.read_timeout_seconds,
            )
            request = (
                f"GET {_request_target(target)} HTTP/1.1\r\n"
                f"Host: {_host_header(target)}\r\n"
                "User-Agent: FluxTuner-Web/1\r\n"
                "Accept: */*\r\n"
                "Icy-MetaData: 1\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
            stream.sendall(request)

            received = bytearray()
            while b"\r\n\r\n" not in received:
                remaining = policy.max_response_header_bytes - len(received)
                if remaining <= 0:
                    raise MetadataResponseError("Remote response headers exceed the safety limit.")
                _apply_remaining_timeout(
                    stream,
                    deadline,
                    policy.read_timeout_seconds,
                )
                chunk = stream.recv(min(4096, remaining))
                if not chunk:
                    raise MetadataResponseError("Remote response ended before its headers.")
                received.extend(chunk)

            status, headers, initial_body = _parse_response_head(bytes(received), policy)
            return ProtectedHTTPResponse(
                status=status,
                headers=headers,
                body=cast(
                    BinaryIO,
                    _SocketBody(
                        stream,
                        initial_body,
                        deadline=deadline,
                        read_timeout=policy.read_timeout_seconds,
                    ),
                ),
            )
        except Exception:
            stream.close()
            raise
