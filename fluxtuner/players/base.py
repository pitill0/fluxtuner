from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlayerError(RuntimeError):
    """Raised when a player backend cannot be used."""


class PlayerAdapter(ABC):
    """Common interface implemented by all playback backends."""

    @abstractmethod
    def play(self, url: str) -> None: ...
        """Start playback for a stream URL."""

    @abstractmethod
    def stop(self) -> None: ...
        """Stop playback."""

    @abstractmethod
    def is_playing(self) -> bool: ...
        """Return True when the backend has an active playback."""

    def toggle_pause(self) -> None:
        raise PlayerError("Pause is not supported by this backend.")
        """Toggle pause/resume."""

    def toggle_mute(self) -> None:
        raise PlayerError("Mute is not supported by this backend.")
        """Toggle mute/unmute."""

    def volume_up(self) -> None:
        raise PlayerError("Volume control is not supported by this backend.")
        """Increase playback volume."""

    def volume_down(self) -> None:
        raise PlayerError("Volume control is not supported by this backend.")
        """Decrease playback volume."""

    def set_volume(self, volume: int | float) -> None:
        raise PlayerError("Volume control is not supported by this backend.")
        """Set playback volume to an absolute value."""

    def set_mute(self, muted: bool) -> None:
        raise PlayerError("Mute is not supported by this backend.")
        """Set mute to an absolute value."""
    
    def supports_pause(self) -> bool:
        return False

    def supports_volume(self) -> bool:
        return False

    def supports_mute(self) -> bool:
        return False

    def get_state(self) -> dict[str, Any]:
        return {"playing": self.is_playing()}
        """Return a compact playback state snapshot."""
