# ffplay backend for FluxTuner.

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from contextlib import suppress
from typing import Any

from fluxtuner.players.base import PlayerAdapter


class FfplayController(PlayerAdapter):
    name = "ffplay"

    def __init__(self) -> None:
        self.process: subprocess.Popen[Any] | None = None
        self.volume = 50
        self.muted = False

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ffplay") is not None

    def play(self, url: str) -> None:
        with suppress(Exception):
            self.stop()

        volume = 0 if self.muted else max(0, min(100, int(self.volume)))

        command = [
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "warning",
            "-volume",
            str(volume),
            url,
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def stop(self) -> None:
        if self.process is None:
            return

        process = self.process

        try:
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=3)
                except Exception:
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:
                        process.kill()
                    process.wait(timeout=3)
        finally:
            self.process = None

    def set_volume(self, volume: int | float) -> None:
        """Store volume for the next ffplay process start."""
        self.volume = max(0, min(100, int(round(volume))))

    def set_mute(self, muted: bool) -> None:
        """Store mute preference for the next ffplay process start."""
        self.muted = bool(muted)

    def is_playing(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_state(self) -> dict[str, Any]:
        return {
            "playing": self.is_playing(),
            "paused": False,
            "muted": self.muted,
            "volume": self.volume,
        }

    def supports_pause(self) -> bool:
        return False

    def supports_volume(self) -> bool:
        return False

    def supports_mute(self) -> bool:
        return False


def test_ffplay_play_continues_when_previous_stop_fails(monkeypatch) -> None:
    controller = FfplayController()

    class StopFailingProcess:
        pid = 123

        def poll(self):
            return None

        def wait(self, timeout=None):
            raise RuntimeError("wait failed")

        def kill(self):
            pass

    created_commands = []

    class FakePopen:
        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    controller.process = StopFailingProcess()  # type: ignore[assignment]

    monkeypatch.setattr("os.getpgid", lambda _pid: 123)
    monkeypatch.setattr("os.killpg", lambda _pgid, _signal: None)
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    controller.play("https://example.com/stream")

    assert created_commands
    assert created_commands[0][-1] == "https://example.com/stream"
    assert isinstance(controller.process, FakePopen)
