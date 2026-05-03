from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlayerError(RuntimeError):
    """Raised when a player backend cannot be used."""


class PlayerAdapter(ABC):
    """Common interface implemented by all playback backends."""

    @abstractmethod
    def play(self, url: str) -> None:
        """Start playback for a stream URL."""

    @abstractmethod
    def stop(self) -> None:
        """Stop playback."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Return True when the backend has an active playback process/session."""

    @abstractmethod
    def toggle_pause(self) -> None:
        """Toggle pause/resume."""

    @abstractmethod
    def toggle_mute(self) -> None:
        """Toggle mute/unmute."""

    @abstractmethod
    def volume_up(self) -> None:
        """Increase playback volume."""

    @abstractmethod
    def volume_down(self) -> None:
        """Decrease playback volume."""

    @abstractmethod
    def set_volume(self, volume: int | float) -> None:
        """Set playback volume to an absolute value."""

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """Set mute to an absolute value."""

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Return a compact playback state snapshot."""
