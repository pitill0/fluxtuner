from __future__ import annotations

import shutil
import subprocess


class PlayerError(RuntimeError):
    """Raised when the external audio player cannot be used."""


def is_mpv_available() -> bool:
    """Return True when mpv is installed and available in PATH."""
    return shutil.which("mpv") is not None


def ensure_mpv_available() -> None:
    """Fail early if mpv is not installed or not available in PATH."""
    if not is_mpv_available():
        raise PlayerError(
            "mpv is required but was not found in PATH. "
            "Please install mpv and try again."
        )


def play_stream(url: str) -> None:
    """Play a stream URL using mpv."""
    ensure_mpv_available()

    try:
        subprocess.run(["mpv", "--no-video", url], check=False)
    except KeyboardInterrupt:
        pass
