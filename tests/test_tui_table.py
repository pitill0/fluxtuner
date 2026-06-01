from fluxtuner import tui_table


class FakeRowKey:
    def __init__(self, value: str) -> None:
        self.value = value


def test_next_table_key_increments_counter() -> None:
    key, counter = tui_table.next_table_key("station", 0)

    assert key == "station-1"
    assert counter == 1


def test_row_key_to_string_uses_value_attribute_when_available() -> None:
    assert tui_table.row_key_to_string(FakeRowKey("row-1")) == "row-1"


def test_row_key_to_string_falls_back_to_string_conversion() -> None:
    assert tui_table.row_key_to_string(123) == "123"


def test_ellipsize_returns_short_values_unchanged() -> None:
    assert tui_table.ellipsize("short", 10) == "short"


def test_ellipsize_truncates_long_values() -> None:
    assert tui_table.ellipsize("abcdefghij", 6) == "abcde…"


def test_station_genre_tags_uses_fallback_for_missing_tags() -> None:
    assert tui_table.station_genre_tags({}, max_length=10) == "-"


def test_station_custom_tags_formats_list_values() -> None:
    station = {"favorite_tags": ["morning", "jazz"]}

    assert tui_table.station_custom_tags(station, max_length=20) == "morning, jazz"


def test_station_custom_tags_formats_string_values() -> None:
    station = {"favorite_tags": "ambient"}

    assert tui_table.station_custom_tags(station, max_length=20) == "ambient"


def test_station_custom_tags_uses_fallback_for_empty_values() -> None:
    assert tui_table.station_custom_tags({}, max_length=20) == "-"
