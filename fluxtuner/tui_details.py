from __future__ import annotations

from pathlib import Path
from typing import Any

from fluxtuner.core.favorites import favorite_display_name
from fluxtuner.core.stations import (
    station_bitrate,
    station_codec,
    station_country,
    station_tags_text,
)
from fluxtuner.tui_themes import theme_status


def empty_station_details_text() -> str:
    return (
        "[b]Station details[/b]\n"
        "No station selected.\n\n"
        "Use search/favorites/playlists to select a station."
    )


def favorite_tags_text(favorite: dict[str, Any] | None) -> str:
    if not favorite:
        return "-"

    tags = favorite.get("favorite_tags") or []
    if isinstance(tags, str):
        return tags or "-"

    return ", ".join(str(tag) for tag in tags) if tags else "-"


def favorite_status_text(favorite: dict[str, Any] | None) -> str:
    if not favorite:
        return "No"

    custom_name = favorite.get("favorite_name")
    if custom_name:
        return f"Yes · {custom_name}"

    return "Yes"


def favorite_hint_text(favorite: dict[str, Any] | None) -> str:
    if favorite:
        return "Favorite actions: e rename · g edit tags · d remove"

    return "Favorite actions: a add selected station"


def station_details_text(
    station: dict[str, Any],
    *,
    favorite: dict[str, Any] | None = None,
) -> str:
    name = favorite_display_name(station)
    country = station_country(station)
    codec = station_codec(station)
    bitrate = station_bitrate(station) or "?"
    genre_tags = station_tags_text(station, fallback="-")

    return (
        "[b]Station details[/b]\n"
        f"{name}\n\n"
        f"Country: {country}\n"
        f"Codec: {codec}\n"
        f"Bitrate: {bitrate} kbps\n"
        f"Genre/tags: {genre_tags}\n\n"
        f"Favorite: {favorite_status_text(favorite)}\n"
        f"Favorite tags: {favorite_tags_text(favorite)}\n\n"
        f"{favorite_hint_text(favorite)}"
    )


def theme_details_text(
    theme_name: str,
    *,
    active_theme: str,
    previewed_theme: str | None,
    path: str | Path,
) -> str:
    status = theme_status(
        theme_name,
        active_theme=active_theme,
        previewed_theme=previewed_theme,
    )

    return (
        "[b]Theme Preview[/b]\n\n"
        f"[b]{theme_name}[/b]\n"
        f"Status: {status}\n"
        f"File: {Path(path).name}\n\n"
        "Highlight previews temporarily.\n"
        "Enter: apply selected theme.\n"
        "y: save active theme as default.\n"
        "Leaving the theme selector restores the last applied theme if you only previewed."
    )


def dynamic_playlist_details_text(
    tag: str,
    *,
    count: int,
    preview_names: list[str],
    total_count: int,
) -> str:
    preview = "\n".join(f"• {name}" for name in preview_names) if preview_names else "No stations."
    extra = (
        ""
        if total_count <= len(preview_names)
        else f"\n… and {total_count - len(preview_names)} more"
    )

    return (
        "[b]Dynamic Playlist[/b]\n\n"
        f"[b]#{tag}[/b]\n"
        f"Stations: {count}\n\n"
        "Enter / r: smart play random station\n"
        "f: show matching favorites\n\n"
        f"{preview}{extra}"
    )


def persistent_playlist_details_text(
    playlist_name: str,
    *,
    count: int,
    preview: str,
) -> str:
    return (
        "[b]Persistent Playlist[/b]\n\n"
        f"[b]{playlist_name}[/b]\n"
        f"Stations: {count}\n\n"
        "Enter / r: smart play random station\n"
        "f: show playlist stations\n"
        "d: delete this playlist\n"
        "b: add selected station to a playlist from other views\n\n"
        f"{preview}"
    )
