from __future__ import annotations

from typing import Any

from textual.widgets import DataTable

from fluxtuner.core.stations import station_tags_text

STATION_TABLE_COLUMNS = [
    ("", "marker", 2),
    ("Name", "name", 42),
    ("ID", "id", 10),
    ("Country", "country", 16),
    ("Genre / tags", "tags", 34),
    ("Codec", "codec", 8),
    ("kbps", "bitrate", 6),
    ("Custom tags", "custom_tags", 24),
]

PLAYLIST_TABLE_COLUMNS = ("Type", "Name", "Count / Status", "Description")


def reset_table_state() -> tuple[dict[str, tuple[str, Any]], int]:
    return {}, 0


def next_table_key(prefix: str, counter: int) -> tuple[str, int]:
    next_counter = counter + 1
    return f"{prefix}-{next_counter}", next_counter


def row_key_to_string(row_key: Any) -> str:
    value = getattr(row_key, "value", row_key)
    return str(value)


def add_station_columns(table: DataTable) -> None:
    for label, key, width in STATION_TABLE_COLUMNS:
        table.add_column(label, key=key, width=width)


def add_playlist_columns(table: DataTable) -> None:
    table.add_columns(*PLAYLIST_TABLE_COLUMNS)


def ellipsize(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"


def station_genre_tags(station: dict[str, Any], max_length: int = 42) -> str:
    return ellipsize(station_tags_text(station, fallback="-"), max_length)


def station_custom_tags(station: dict[str, Any], max_length: int = 28) -> str:
    tags = station.get("favorite_tags") or station.get("tags_custom") or []
    value = tags if isinstance(tags, str) else ", ".join(str(tag) for tag in tags)
    return ellipsize(value if value else "-", max_length)
