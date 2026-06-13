# ffplay backend for FluxTuner.

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any

from fluxtuner.logging_config import get_logger
from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.capabilities import PlayerCapabilities
from fluxtuner.players.security import resolve_executable, validate_stream_url

logger = get_logger(__name__)


class FfplayController(PlayerAdapter):
    name = "ffplay"

    def __init__(self) -> None:
        self.process: subprocess.Popen[Any] | None = None
        self.volume = 50
        self.muted = False

    @classmethod
    def is_available(cls) -> bool:
        try:
            resolve_executable("ffplay")
            return True
        except PlayerError:
            logger.debug("ffplay backend is not available")
            return False

    @classmethod
    def capabilities(cls) -> PlayerCapabilities:
        return PlayerCapabilities(
            general_purpose=True,
            supports_pause=False,
            supports_volume=False,
            supports_mute=False,
        )

    def play(self, url: str) -> None:
        ffplay_path = resolve_executable("ffplay")
        safe_url = validate_stream_url(url)

        try:
            self.stop()
        except Exception:  # noqa: BLE001
            logger.debug("Ignoring ffplay stop error before starting new playback", exc_info=True)

        volume = 0 if self.muted else max(0, min(100, int(self.volume)))

        command = [
            ffplay_path,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "warning",
            "-volume",
            str(volume),
            safe_url,
        ]

        logger.debug("Starting ffplay playback")
        self.process = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.debug("ffplay playback process started")

    def stop(self) -> None:
        if self.process is None:
            logger.debug("ffplay stop requested without active process")
            return

        process = self.process

        try:
            if process.poll() is None:
                logger.debug("Stopping ffplay playback process")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Graceful ffplay stop failed; killing process group", exc_info=True
                    )
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:  # noqa: BLE001
                        logger.debug(
                            "Could not kill ffplay process group; killing process", exc_info=True
                        )
                        process.kill()
                    process.wait(timeout=3)
        finally:
            self.process = None
            logger.debug("ffplay playback process stopped")

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
