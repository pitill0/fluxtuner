import pytest

from fluxtuner.players.base import PlayerError
from fluxtuner.players.ogg123 import Ogg123Controller


def test_ogg123_play_uses_resolved_executable(monkeypatch) -> None:
    created_commands = []

    class FakePopen:
        pid = 123

        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    monkeypatch.setattr(
        "fluxtuner.players.ogg123.resolve_executable", lambda _name: "/usr/bin/ogg123"
    )
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    controller = Ogg123Controller()
    controller.play("https://example.com/live.ogg")

    assert created_commands
    assert created_commands[0] == ["/usr/bin/ogg123", "-q", "https://example.com/live.ogg"]


def test_ogg123_play_rejects_invalid_stream_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "fluxtuner.players.ogg123.resolve_executable", lambda _name: "/usr/bin/ogg123"
    )

    with pytest.raises(PlayerError):
        Ogg123Controller().play("file:///tmp/test.ogg")


def test_ogg123_capabilities_are_specialized() -> None:
    capabilities = Ogg123Controller.capabilities()

    assert capabilities.general_purpose is False
    assert capabilities.supports_volume is False
