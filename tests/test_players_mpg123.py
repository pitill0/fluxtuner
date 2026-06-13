import pytest

from fluxtuner.players.base import PlayerError
from fluxtuner.players.mpg123 import Mpg123Controller


def test_mpg123_play_uses_resolved_executable(monkeypatch) -> None:
    created_commands = []

    class FakePopen:
        pid = 123

        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    monkeypatch.setattr(
        "fluxtuner.players.mpg123.resolve_executable", lambda _name: "/usr/bin/mpg123"
    )
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    controller = Mpg123Controller()
    controller.play("https://example.com/live.mp3")

    assert created_commands
    assert created_commands[0] == ["/usr/bin/mpg123", "-q", "https://example.com/live.mp3"]


def test_mpg123_play_rejects_invalid_stream_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "fluxtuner.players.mpg123.resolve_executable", lambda _name: "/usr/bin/mpg123"
    )

    with pytest.raises(PlayerError):
        Mpg123Controller().play("file:///tmp/test.mp3")


def test_mpg123_capabilities_are_specialized() -> None:
    capabilities = Mpg123Controller.capabilities()

    assert capabilities.general_purpose is False
    assert capabilities.supports_volume is False
