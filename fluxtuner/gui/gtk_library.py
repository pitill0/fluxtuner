"""Profile-scoped GTK library storage and favorite-cache ownership, without GTK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fluxtuner.core import db, manual_playlists
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.favorites import (
    add_favorite,
    all_favorite_tags,
    filter_favorites_by_tag,
    load_favorites,
    remove_favorite,
    update_favorite,
)
from fluxtuner.core.history import load_history
from fluxtuner.core.profiles import get_profile_by_name
from fluxtuner.core.stations import favorite_tags, station_key, station_tags
from fluxtuner.gui.gtk_playlists import PlaylistPicker, create_playlist_picker


class LibraryController:
    """Own library persistence access and its one favorite URL cache.

    ViewState and the station selection remain shared with the station view;
    this controller neither retains widgets nor duplicates those states.
    """

    def __init__(self, *, profile_name: Callable[[], str | None]) -> None:
        self._profile_name = profile_name
        self.favorite_urls: set[str] = set()

    @property
    def profile_name(self) -> str | None:
        return self._profile_name()

    def load_favorites(self) -> list[dict[str, Any]]:
        return load_favorites(profile_name=self.profile_name)

    def load_history(self) -> list[dict[str, Any]]:
        return load_history(profile_name=self.profile_name)

    def add_favorite(self, station: dict[str, Any]) -> bool:
        return add_favorite(station, profile_name=self.profile_name)

    def remove_favorite(self, key: str) -> bool:
        return remove_favorite(key, profile_name=self.profile_name)

    def update_favorite(self, key: str, *, custom_name: str, favorite_tags: list[str]) -> bool:
        return update_favorite(
            key,
            custom_name=custom_name,
            favorite_tags=favorite_tags,
            profile_name=self.profile_name,
        )

    def load_playlists(self, *, profile_id: int) -> list[dict[str, Any]]:
        return manual_playlists.load_playlists(profile_id=profile_id)

    def get_playlist(self, name: str, *, profile_id: int) -> dict[str, Any] | None:
        return manual_playlists.get_playlist(name, profile_id=profile_id)

    def get_playlist_stations(self, name: str, *, profile_id: int) -> list[dict[str, Any]]:
        return manual_playlists.get_playlist_stations(name, profile_id=profile_id)

    def create_playlist(self, name: str, *, profile_id: int) -> bool:
        return manual_playlists.create_playlist(name, profile_id=profile_id)

    def delete_playlist(self, name: str, *, profile_id: int) -> bool:
        return manual_playlists.delete_playlist(name, profile_id=profile_id)

    def remove_station_from_playlist(
        self, name: str, station: dict[str, Any], *, profile_id: int
    ) -> bool:
        return manual_playlists.remove_station_from_playlist(name, station, profile_id=profile_id)

    def create_playlist_picker(self, station: dict[str, Any], *, profile_id: int) -> PlaylistPicker:
        return create_playlist_picker(station, profile_id=profile_id)

    def add_custom_station(self, *, profile_id: int, name: str, url: str) -> bool:
        with db.connect() as conn:
            added = add_custom_station(
                conn, profile_id=profile_id, name=name, url=url, record_manual_provenance=True
            )
            conn.commit()
        return added

    def favorites_matching_favorite_tag(self, tag: str) -> list[dict[str, Any]]:
        return filter_favorites_by_tag(tag)

    def all_favorite_playlist_tags(self) -> list[str]:
        return all_favorite_tags()

    def playlist_profile_id(self) -> int:
        name = self.profile_name
        if name is None:
            name = db.DEFAULT_PROFILE_NAME
        with db.connect() as conn:
            profile = get_profile_by_name(conn, name)
        if profile is None:
            raise ValueError("The current profile is unavailable.")
        return int(profile["id"])

    def favorite_url_set(self) -> set[str]:
        return {
            key
            for item in load_favorites(profile_name=self.profile_name)
            if (key := station_key(item))
        }

    def is_favorite_station(self, station: dict[str, Any]) -> bool:
        key = station_key(station)
        return bool(key and key in self.favorite_urls)

    def refresh_favorite_cache(self) -> None:
        self.favorite_urls = self.favorite_url_set()


def library_tags_text(station: dict[str, Any] | None, fallback: str = "No tags") -> str:
    """Display stream genres and personal favorite tags without duplicate labels.

    Keep the two stored fields independent: filtering, import and metadata retain
    their original inputs. Preserve the stream's spelling/order in the display.
    """
    labels = []
    seen = set()
    for tag in (*station_tags(station), *favorite_tags(station)):
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            labels.append(tag)
    return ", ".join(labels) if labels else fallback
