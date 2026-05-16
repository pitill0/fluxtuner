# ffplay backend for FluxTuner.

from __future__ import annotations

import os
import shutil
import signal
import subprocess
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

        if self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    self.process.kill()
                self.process.wait(timeout=3)

        self.process = None

    def set_volume(self, volume: int | float) -> None:
        """Store volume for the next ffplay process start."""
        self.volume = max(0, min(100, int(round(volume))))

    def set_mute(self, muted: bool) -> None:
        """Store mute preference for the next ffplay process start."""
        self.muted = bool(muted)

    def toggle_mute(self) -> None:
        """Toggle mute preference for the next ffplay process start."""
        self.set_mute(not self.muted)

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
