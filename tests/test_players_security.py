import pytest

from fluxtuner.players.base import PlayerError
from fluxtuner.players.security import (
    is_supported_stream_url,
    resolve_executable,
    validate_stream_url,
)


def test_is_supported_stream_url_accepts_http_and_https() -> None:
    assert is_supported_stream_url("http://example.com/stream")
    assert is_supported_stream_url("https://example.com/stream")


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        None,
        "file:///tmp/test.mp3",
        "javascript:alert(1)",
        "/tmp/test.mp3",
        "example.com/stream",
    ],
)
def test_is_supported_stream_url_rejects_unsupported_values(url) -> None:
    assert not is_supported_stream_url(url)


def test_validate_stream_url_returns_stripped_url() -> None:
    assert validate_stream_url(" https://example.com/stream ") == "https://example.com/stream"


def test_validate_stream_url_rejects_invalid_url() -> None:
    with pytest.raises(PlayerError):
        validate_stream_url("file:///tmp/test.mp3")


def test_resolve_executable_returns_resolved_path(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    assert resolve_executable("mpv") == "/usr/bin/mpv"


def test_resolve_executable_raises_when_missing(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(PlayerError):
        resolve_executable("mpv")
