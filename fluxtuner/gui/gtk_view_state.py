from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ViewState:
    """Own the logical GTK station-list view and playlist filter."""

    current_view: str = "search"
    active_playlist_tag: str | None = None

    def show_search(self) -> None:
        self.current_view = "search"
        self.active_playlist_tag = None

    def show_favorites(self) -> None:
        self.current_view = "favorites"
        self.active_playlist_tag = None

    def show_history(self) -> None:
        self.current_view = "history"
        self.active_playlist_tag = None

    def show_tag_playlist(self, tag: str) -> None:
        self.current_view = "tag_playlist"
        self.active_playlist_tag = tag
