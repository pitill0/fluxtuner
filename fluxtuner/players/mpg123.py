from __future__ import annotations

import os
import signal
import subprocess
from contextlib import suppress
from typing import Any

from fluxtuner.logging_config import get_logger
from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.capabilities import PlayerCapabilities
from fluxtuner.players.security import resolve_executable, validate_stream_url

logger = get_logger(__name__)


class Mpg123Controller(PlayerAdapter):
    """Lightweight mpg123 backend for MP3/MPEG streams."""

    name = "mpg123"

    def __init__(self) -> None:
        self.process: subprocess.Popen[Any] | None = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            resolve_executable("mpg123")
            return True
        except PlayerError:
            logger.debug("mpg123 backend is not available")
            return False

    @classmethod
    def capabilities(cls) -> PlayerCapabilities:
        return PlayerCapabilities(
            general_purpose=False,
            supports_pause=False,
            supports_volume=False,
            supports_mute=False,
            supported_codecs=frozenset({"mp3", "mpeg"}),
            supported_mime_types=frozenset({"audio/mpeg", "audio/x-mpeg", "audio/mp3"}),
        )

    def play(self, url: str) -> None:
        player_path = resolve_executable("mpg123")
        safe_url = validate_stream_url(url)

        try:
            self.stop()
        except Exception:  # noqa: BLE001
            logger.debug("Ignoring mpg123 stop error before starting new playback", exc_info=True)

        logger.debug("Starting mpg123 playback")
        self.process = subprocess.Popen(  # noqa: S603
            [player_path, "-q", safe_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.debug("mpg123 playback process started")

    def stop(self) -> None:
        if self.process is None:
            logger.debug("mpg123 stop requested without active process")
            return

        process = self.process
        try:
            if process.poll() is None:
                logger.debug("Stopping mpg123 playback process")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Graceful mpg123 stop failed; killing process group", exc_info=True
                    )
                    with suppress(Exception):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait(timeout=3)
        finally:
            self.process = None
            logger.debug("mpg123 playback process stopped")

    def is_playing(self) -> bool:
        return self.process is not None and self.process.poll() is None
