from fluxtuner import tui_details


def test_empty_station_details_text_mentions_no_station_selected() -> None:
    text = tui_details.empty_station_details_text()

    assert "Station details" in text
    assert "No station selected" in text


def test_favorite_tags_text_returns_fallback_without_favorite() -> None:
    assert tui_details.favorite_tags_text(None) == "-"


def test_favorite_tags_text_formats_string_tags() -> None:
    assert tui_details.favorite_tags_text({"favorite_tags": "jazz"}) == "jazz"


def test_favorite_tags_text_formats_list_tags() -> None:
    assert tui_details.favorite_tags_text({"favorite_tags": ["jazz", "night"]}) == "jazz, night"


def test_favorite_status_text_without_favorite() -> None:
    assert tui_details.favorite_status_text(None) == "No"


def test_favorite_status_text_with_custom_name() -> None:
    assert tui_details.favorite_status_text({"favorite_name": "Late Night Radio"}) == (
        "Yes · Late Night Radio"
    )


def test_favorite_hint_text_for_favorite() -> None:
    assert tui_details.favorite_hint_text({"name": "Saved"}) == (
        "Favorite actions: e rename · g edit tags · d remove"
    )


def test_station_details_text_includes_station_and_favorite_metadata() -> None:
    station = {
        "name": "Test Radio",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": 128,
        "tags": "jazz",
    }
    favorite = {
        "favorite_name": "My Radio",
        "favorite_tags": ["night", "work"],
    }

    text = tui_details.station_details_text(station, favorite=favorite)

    assert "My Radio" in text
    assert "Country: Spain" in text
    assert "Codec: MP3" in text
    assert "Bitrate: 128 kbps" in text
    assert "Genre/tags: jazz" in text
    assert "Favorite: Yes · My Radio" in text
    assert "Favorite tags: night, work" in text


def test_theme_details_text_marks_active_theme() -> None:
    text = tui_details.theme_details_text(
        "default",
        active_theme="default",
        previewed_theme=None,
        path="/tmp/default.tcss",
    )

    assert "Status: active" in text
    assert "File: default.tcss" in text


def test_theme_details_text_marks_previewed_theme() -> None:
    text = tui_details.theme_details_text(
        "solarized",
        active_theme="default",
        previewed_theme="solarized",
        path="/tmp/solarized.tcss",
    )

    assert "Status: preview" in text


def test_dynamic_playlist_details_text_includes_preview_and_extra_count() -> None:
    text = tui_details.dynamic_playlist_details_text(
        "jazz",
        count=8,
        preview_names=["One", "Two"],
        total_count=8,
    )

    assert "[b]#jazz[/b]" in text
    assert "Stations: 8" in text
    assert "• One" in text
    assert "• Two" in text
    assert "… and 6 more" in text


def test_persistent_playlist_details_text_includes_preview() -> None:
    text = tui_details.persistent_playlist_details_text(
        "Morning",
        count=3,
        preview="• Station A\n• Station B",
    )

    assert "[b]Morning[/b]" in text
    assert "Stations: 3" in text
    assert "• Station A" in text
