"""Regression tests for untrusted Rich markup in TUI details."""

import pytest
from rich.text import Text

from fluxtuner.tui_details import (
    dynamic_playlist_details_text,
    persistent_playlist_details_text,
    station_details_text,
)


def rendered(value: str) -> str:
    """Interpret application markup as Textual would."""
    return Text.from_markup(value).plain


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "Rock FM [/]"),
        ("name", "Radio [bold red] Live"),
        ("country", "Spain [/]"),
        ("codec", "MP3 [bold red]"),
        ("tags", "rock, [link=https://example.org]live[/link]"),
    ],
)
def test_station_details_render_external_values_literally(
    field: str,
    value: str,
) -> None:
    station = {
        "name": "Safe Radio",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": 128,
        "tags": "rock",
    }
    station[field] = value

    actual = rendered(station_details_text(station))

    assert value in actual
    assert "Station details" in actual


def test_station_details_render_persisted_favorite_metadata_literally() -> None:
    station = {
        "name": "Original station",
        "country": "Spain",
        "codec": "MP3",
        "tags": "rock",
    }
    station["favorite_name"] = "Saved [/] radio"

    favorite = {
        "favorite_name": "Saved [/] radio",
        "favorite_tags": ["[bold red]", "night [/]"],
    }

    actual = rendered(station_details_text(station, favorite=favorite))

    assert "Saved [/] radio" in actual
    assert "[bold red]" in actual
    assert "night [/]" in actual


def test_dynamic_playlist_render_tag_and_station_names_literally() -> None:
    actual = rendered(
        dynamic_playlist_details_text(
            "rock [/]",
            count=2,
            preview_names=["Radio [bold red]", "Saved [/] station"],
            total_count=2,
        )
    )

    assert "#rock [/]" in actual
    assert "Radio [bold red]" in actual
    assert "Saved [/] station" in actual


def test_persistent_playlist_render_name_and_preview_literally() -> None:
    actual = rendered(
        persistent_playlist_details_text(
            "Morning [/]",
            count=2,
            preview="• Rock [bold red]\n• Radio [/]",
        )
    )

    assert "Morning [/]" in actual
    assert "Rock [bold red]" in actual
    assert "Radio [/]" in actual


def test_station_table_cells_use_literal_text() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fluxtuner.tui import FluxTunerTUI

    table = Mock()
    station = {
        "name": "Rock FM [/]",
        "country": "Spain [bold red]",
        "codec": "MP3 [link=https://example.org]codec[/link]",
        "tags": "rock [/]",
        "favorite_tags": ["night [/]"],
        "bitrate": 128,
    }
    harness = SimpleNamespace(
        next_table_key=Mock(return_value="station-1"),
        add_table_payload=Mock(),
        station_marker=Mock(return_value=""),
        station_short_id=Mock(return_value="123"),
        station_genre_tags=Mock(return_value="rock [/]"),
        station_custom_tags=Mock(return_value="night [/]"),
    )

    FluxTunerTUI.add_station_table_row(harness, table, station)

    cells = table.add_row.call_args.args
    for index, expected in (
        (1, "Rock FM [/]"),
        (3, "Spain [bold r…"),
        (4, "rock [/]"),
        (5, "MP3 [link=https://example.org]codec[/link]"),
        (7, "night [/]"),
    ):
        assert isinstance(cells[index], Text)
        assert cells[index].plain == expected

    harness.add_table_payload.assert_called_once_with("station-1", "station", station)


@pytest.mark.parametrize(
    ("method_name", "selector", "value"),
    [
        ("set_status", "#status", "Playing Rock FM [/]"),
        ("update_mode_title", "#mode-title", "Favorites · tag: [bold red]"),
    ],
)
def test_dynamic_plain_text_widgets_keep_markup_literal(
    method_name: str, selector: str, value: str
) -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fluxtuner.tui import FluxTunerTUI

    widget = Mock()
    harness = SimpleNamespace(query_one=Mock(return_value=widget))

    getattr(FluxTunerTUI, method_name)(harness, value)

    assert harness.query_one.call_args.args[0] == selector
    result = widget.update.call_args.args[0]
    assert isinstance(result, Text)
    assert result.plain == value


def test_now_playing_untrusted_station_values_render_literally() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fluxtuner.tui import FluxTunerTUI

    widget = Mock()
    harness = SimpleNamespace(
        playing_station={
            "name": "Rock FM [/]",
            "country": "Spain [bold red]",
            "codec": "MP3 [link=https://example.org]codec[/link]",
            "bitrate": 128,
        },
        query_one=Mock(return_value=widget),
        _maybe_fetch_metadata=Mock(),
        _update_usage_display=Mock(),
        _update_player_state_display=Mock(),
    )

    FluxTunerTUI.update_now_playing(harness)
    value = widget.update.call_args.args[0]

    actual = value.plain if isinstance(value, Text) else rendered(value)
    assert "Rock FM [/]" in actual
    assert "Spain [bold red]" in actual
    assert "MP3 [link=https://example.org]codec[/link]" in actual
    assert "Now Playing" in actual


def test_icy_metadata_markup_is_rendered_literally(monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fluxtuner import tui
    from fluxtuner.tui import FluxTunerTUI

    async def immediate(function, *args):
        return function(*args)

    artist = "Artist [/]"
    track = "Song [bold red] [link=https://example.org]link[/link]"
    widget = Mock()
    lifecycle = Mock()
    lifecycle.accept.return_value = SimpleNamespace(
        artist=artist,
        track=track,
    )
    harness = SimpleNamespace(
        playing_station={"name": "Radio"},
        station_url=Mock(return_value="https://example.org/radio"),
        metadata_lifecycle=lifecycle,
        current_artist="",
        current_track="",
        is_running=True,
        query_one=Mock(return_value=widget),
    )

    monkeypatch.setattr(asyncio, "to_thread", immediate)
    monkeypatch.setattr(
        tui,
        "fetch_stream_metadata",
        lambda _url: {"artist": artist, "title": track, "raw": track},
    )

    asyncio.run(FluxTunerTUI._fetch_metadata(harness, "https://example.org/radio", 1))

    value = widget.update.call_args.args[0]
    actual = value.plain if isinstance(value, Text) else rendered(value)

    assert f"Artist: {artist}" in actual
    assert f"Track: {track}" in actual
    assert actual.startswith("Metadata\n")
    lifecycle.accept.assert_called_once()


def test_persisted_playlist_table_cells_are_literal(monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock

    from fluxtuner import tui
    from fluxtuner.tui import FluxTunerTUI

    playlist_name = "Morning [/]"
    tag_name = "rock [bold red]"
    monkeypatch.setattr(tui, "playlist_counts", lambda **_kwargs: [(playlist_name, 2)])
    monkeypatch.setattr(tui, "get_tag_counts", lambda **_kwargs: [(tag_name, 3)])

    table = Mock()
    counter = iter(["playlist-1", "tag-2"])
    payloads = {}
    harness = SimpleNamespace(
        profile_name="default",
        restore_active_theme_if_previewing=Mock(),
        _enter_playlists_view=Mock(),
        update_mode_title=Mock(),
        reset_playlist_table=Mock(return_value=table),
        _clear_view_selection=Mock(),
        next_table_key=lambda _prefix: next(counter),
        add_table_payload=lambda key, kind, payload: payloads.update({key: (kind, payload)}),
        table_items=payloads,
        _select_playlist=Mock(),
        update_persistent_playlist_details=Mock(),
        _select_tag=Mock(),
        update_playlist_details=Mock(),
        set_status=Mock(),
    )

    asyncio.run(FluxTunerTUI.show_playlists(harness))

    calls = table.add_row.call_args_list
    assert len(calls) == 2
    assert isinstance(calls[0].args[1], Text)
    assert calls[0].args[1].plain == playlist_name
    assert isinstance(calls[1].args[1], Text)
    assert calls[1].args[1].plain == f"#{tag_name}"
    assert payloads["playlist-1"][1]["name"] == playlist_name
    assert payloads["tag-2"][1]["tag"] == tag_name
