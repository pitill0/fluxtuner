from io import BytesIO
from typing import Any

from fluxtuner.core import stream_metadata


class FakeResponse:
    def __init__(self, headers: dict[str, str], raw: BytesIO) -> None:
        self.headers = headers
        self.raw = raw
        self.closed = False

    def close(self) -> None:
        self.closed = True


def icy_payload(title: str, metaint: int = 4) -> bytes:
    audio_prefix = b"a" * metaint
    metadata = f"StreamTitle='{title}';".encode()
    blocks = (len(metadata) + 15) // 16
    padded_metadata = metadata.ljust(blocks * 16, b"\0")
    return audio_prefix + bytes([blocks]) + padded_metadata


def test_parse_stream_title_splits_artist_and_title() -> None:
    assert stream_metadata._parse_stream_title("Artist - Song") == {
        "raw": "Artist - Song",
        "artist": "Artist",
        "title": "Song",
    }


def test_parse_stream_title_uses_raw_title_without_artist() -> None:
    assert stream_metadata._parse_stream_title("Song Only") == {
        "raw": "Song Only",
        "artist": "",
        "title": "Song Only",
    }


def test_fetch_stream_metadata_reads_icy_title(monkeypatch) -> None:
    response = FakeResponse(
        headers={"icy-metaint": "4"},
        raw=BytesIO(icy_payload("Artist - Song", metaint=4)),
    )

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return response

    monkeypatch.setattr(stream_metadata.requests, "get", fake_get)

    assert stream_metadata.fetch_stream_metadata("https://example.com/stream") == {
        "raw": "Artist - Song",
        "artist": "Artist",
        "title": "Song",
        "source": "icy",
    }
    assert response.closed is True


def test_fetch_stream_metadata_returns_none_without_metaint(monkeypatch) -> None:
    response = FakeResponse(headers={}, raw=BytesIO(b""))

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return response

    monkeypatch.setattr(stream_metadata.requests, "get", fake_get)

    assert stream_metadata.fetch_stream_metadata("https://example.com/stream") is None


def test_fetch_stream_metadata_returns_none_for_invalid_metaint(monkeypatch) -> None:
    response = FakeResponse(headers={"icy-metaint": "invalid"}, raw=BytesIO(b""))

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return response

    monkeypatch.setattr(stream_metadata.requests, "get", fake_get)

    assert stream_metadata.fetch_stream_metadata("https://example.com/stream") is None


def test_fetch_stream_metadata_returns_none_for_empty_metadata(monkeypatch) -> None:
    response = FakeResponse(
        headers={"icy-metaint": "4"},
        raw=BytesIO(b"a" * 4 + b"\0"),
    )

    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        return response

    monkeypatch.setattr(stream_metadata.requests, "get", fake_get)

    assert stream_metadata.fetch_stream_metadata("https://example.com/stream") is None


def test_fetch_stream_metadata_returns_none_on_request_error(monkeypatch) -> None:
    def fake_get(*_args: Any, **_kwargs: Any) -> FakeResponse:
        raise RuntimeError("network failed")

    monkeypatch.setattr(stream_metadata.requests, "get", fake_get)

    assert stream_metadata.fetch_stream_metadata("https://example.com/stream") is None
