"""Persistent playlist picker coordination without GTK imports."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from fluxtuner.core.favorites import add_favorite
from fluxtuner.core.manual_playlists import (
    add_station_to_playlist,
    get_playlist,
    load_playlists,
)
from fluxtuner.core.stations import station_key


@dataclass(frozen=True)
class PlaylistPicker:
    """Capture the profile, station and offered playlists for one dialog."""

    names: tuple[str, ...]
    _profile_id: int
    _station: dict[str, Any]

    def add(self, name: str) -> bool:
        if name not in self.names:
            raise ValueError("Choose one of the offered playlists.")
        if get_playlist(name, profile_id=self._profile_id) is None:
            raise ValueError("This playlist no longer exists. Reopen the picker.")

        # Persistent playlist contents resolve through profile favorites,
        # matching the existing web flow.
        station = deepcopy(self._station)
        add_favorite(station, profile_id=self._profile_id)
        return add_station_to_playlist(name, station, profile_id=self._profile_id)


def create_playlist_picker(station: dict[str, Any], *, profile_id: int) -> PlaylistPicker:
    if isinstance(profile_id, bool) or not isinstance(profile_id, int) or profile_id <= 0:
        raise ValueError("A persistent profile ID is required.")
    captured_station = deepcopy(station)
    if not station_key(captured_station):
        raise ValueError("A station URL is required.")

    names = tuple(item["name"] for item in load_playlists(profile_id=profile_id))
    return PlaylistPicker(names, profile_id, captured_station)
