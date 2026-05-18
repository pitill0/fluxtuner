import json
import sys
import types
from pathlib import Path

import pytest

from fluxtuner import __main__ as main_module


def patch_default_config(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "get_config_value", lambda _key, default: default)


def patch_selected_player(monkeypatch, player_name: str = "mpv") -> None:
    monkeypatch.setattr(main_module, "selected_player_name", lambda _name: player_name)


def run_main(monkeypatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["fluxtuner", *args])
    main_module.main()


def test_main_list_players_accepts_player_auto(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "available_players", lambda: ["mpv"])
    monkeypatch.setattr(main_module, "selected_player_name", lambda _name=None: "mpv")

    run_main(monkeypatch, "--player", "auto", "--list-players")


def test_main_list_players_handles_no_available_backends(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "available_players", lambda: [])

    run_main(monkeypatch, "--list-players")


def test_main_clear_cache_calls_cache_clear(monkeypatch) -> None:
    called = False

    def fake_clear_search_cache() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "clear_search_cache", fake_clear_search_cache)

    run_main(monkeypatch, "--clear-cache")

    assert called is True


def test_main_version_exits_successfully(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["fluxtuner", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code == 0


def test_main_export_favorites_writes_json_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    export_path = tmp_path / "favorites.json"

    monkeypatch.setattr(
        main_module,
        "load_favorites",
        lambda: [{"name": "Test Radio", "url": "https://example.com/stream"}],
    )

    run_main(monkeypatch, "--export-favs", str(export_path))

    assert json.loads(export_path.read_text(encoding="utf-8")) == [
        {"name": "Test Radio", "url": "https://example.com/stream"}
    ]


def test_main_import_favorites_reads_json_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import_path = tmp_path / "favorites.json"
    import_path.write_text(
        json.dumps([{"name": "Imported Radio", "url": "https://example.com/imported"}]),
        encoding="utf-8",
    )

    saved = []

    def fake_save_favorites(items: list[dict[str, object]]) -> None:
        saved.extend(items)

    monkeypatch.setattr(main_module, "save_favorites", fake_save_favorites)

    run_main(monkeypatch, "--import-favs", str(import_path))

    assert saved == [{"name": "Imported Radio", "url": "https://example.com/imported"}]


def test_main_import_favorites_rejects_non_list_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import_path = tmp_path / "favorites.json"
    import_path.write_text(json.dumps({"name": "Not a list"}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        run_main(monkeypatch, "--import-favs", str(import_path))

    assert exc_info.value.code == 1


def test_main_export_playlists_writes_json_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    export_path = tmp_path / "playlists.json"

    monkeypatch.setattr(
        main_module,
        "load_playlists",
        lambda: [{"name": "Morning", "station_keys": ["https://example.com/stream"]}],
    )

    run_main(monkeypatch, "--export-playlists", str(export_path))

    assert json.loads(export_path.read_text(encoding="utf-8")) == [
        {"name": "Morning", "station_keys": ["https://example.com/stream"]}
    ]


def test_main_import_playlists_reads_json_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import_path = tmp_path / "playlists.json"
    import_path.write_text(
        json.dumps([{"name": "Imported", "station_keys": ["https://example.com/imported"]}]),
        encoding="utf-8",
    )

    saved = []

    def fake_save_playlists(items: list[dict[str, object]]) -> None:
        saved.extend(items)

    monkeypatch.setattr(main_module, "save_playlists", fake_save_playlists)

    run_main(monkeypatch, "--import-playlists", str(import_path))

    assert saved == [{"name": "Imported", "station_keys": ["https://example.com/imported"]}]


def test_main_import_playlists_rejects_non_list_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import_path = tmp_path / "playlists.json"
    import_path.write_text(json.dumps({"name": "Not a list"}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        run_main(monkeypatch, "--import-playlists", str(import_path))

    assert exc_info.value.code == 1


def patch_run_tui(monkeypatch) -> dict[str, str]:
    captured = {}

    fake_tui_module = types.SimpleNamespace(
        run_tui=lambda *, theme, player_name: captured.update(
            {"theme": theme, "player_name": player_name}
        )
    )

    monkeypatch.setitem(sys.modules, "fluxtuner.tui", fake_tui_module)

    return captured


def test_main_save_theme_persists_known_theme(monkeypatch) -> None:
    saved = {}
    captured = patch_run_tui(monkeypatch)
    patch_default_config(monkeypatch)
    patch_selected_player(monkeypatch)

    def fake_set_config_value(key: str, value: str) -> None:
        saved[key] = value

    monkeypatch.setattr(main_module, "theme_exists", lambda theme: theme == "nord")
    monkeypatch.setattr(main_module, "set_config_value", fake_set_config_value)

    run_main(monkeypatch, "--save-theme", "nord")

    assert saved == {"theme": "nord"}
    assert captured == {"theme": "nord", "player_name": "mpv"}


def test_main_unknown_theme_falls_back_to_default(monkeypatch) -> None:
    captured = patch_run_tui(monkeypatch)
    patch_default_config(monkeypatch)
    patch_selected_player(monkeypatch)

    monkeypatch.setattr(main_module, "theme_exists", lambda _theme: False)

    run_main(monkeypatch, "--theme", "missing")

    assert captured == {"theme": main_module.DEFAULT_THEME, "player_name": "mpv"}


def test_main_save_theme_rejects_unknown_theme(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "theme_exists", lambda _theme: False)

    with pytest.raises(SystemExit) as exc_info:
        run_main(monkeypatch, "--save-theme", "missing")

    assert exc_info.value.code == 2


def test_main_save_theme_uses_theme_argument_when_no_value_is_passed(monkeypatch) -> None:
    saved = {}
    captured = patch_run_tui(monkeypatch)
    patch_default_config(monkeypatch)
    patch_selected_player(monkeypatch)

    def fake_set_config_value(key: str, value: str) -> None:
        saved[key] = value

    monkeypatch.setattr(main_module, "theme_exists", lambda theme: theme == "nord")
    monkeypatch.setattr(main_module, "set_config_value", fake_set_config_value)

    run_main(monkeypatch, "--theme", "nord", "--save-theme")

    assert saved == {"theme": "nord"}
    assert captured == {"theme": "nord", "player_name": "mpv"}


def test_main_rejects_unknown_player_before_launching_tui(monkeypatch) -> None:
    patch_run_tui(monkeypatch)
    patch_default_config(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        run_main(monkeypatch, "--player", "unknown")

    assert exc_info.value.code == 2


def test_main_resolves_player_before_launching_tui(monkeypatch) -> None:
    captured = patch_run_tui(monkeypatch)
    patch_default_config(monkeypatch)

    monkeypatch.setattr(main_module, "selected_player_name", lambda _name: "mpv")

    run_main(monkeypatch, "--player", "auto")

    assert captured == {"theme": main_module.DEFAULT_THEME, "player_name": "mpv"}


def test_play_station_prefers_resolved_url() -> None:
    played = {}

    class FakePlayer:
        def play(self, url: str) -> None:
            played["url"] = url

    fake_player = FakePlayer()

    result = main_module.play_station(
        {
            "name": "Test Radio",
            "url": "https://example.com/raw",
            "url_resolved": "https://example.com/resolved",
        },
        player=fake_player,
    )

    assert result is fake_player
    assert played == {"url": "https://example.com/resolved"}


def test_play_station_rejects_station_without_playable_url() -> None:
    assert main_module.play_station({"name": "Broken Radio", "url": "   "}) is None


def test_print_station_table_handles_minimal_station_data() -> None:
    main_module.print_station_table(
        [
            {
                "name": "Minimal Radio",
                "url": "https://example.com/stream",
            }
        ]
    )


def test_print_station_table_handles_list_tags() -> None:
    main_module.print_station_table(
        [
            {
                "name": "Tagged Radio",
                "url": "https://example.com/stream",
                "tags": [" rock ", "pop"],
                "bitrate": "128",
            }
        ]
    )


def test_choose_station_returns_selected_station(monkeypatch) -> None:
    stations = [
        {"name": "First Radio", "url": "https://example.com/first"},
        {"name": "Second Radio", "url": "https://example.com/second"},
    ]

    monkeypatch.setattr("builtins.input", lambda _prompt: "1")

    assert main_module.choose_station(stations) == stations[1]


def test_choose_station_returns_none_for_non_numeric_input(monkeypatch) -> None:
    stations = [{"name": "Test Radio", "url": "https://example.com/stream"}]

    monkeypatch.setattr("builtins.input", lambda _prompt: "abc")

    assert main_module.choose_station(stations) is None


def test_choose_station_returns_none_for_out_of_range_index(monkeypatch) -> None:
    stations = [{"name": "Test Radio", "url": "https://example.com/stream"}]

    monkeypatch.setattr("builtins.input", lambda _prompt: "9")

    assert main_module.choose_station(stations) is None


def test_choose_station_returns_none_for_empty_station_list() -> None:
    assert main_module.choose_station([]) is None


def test_search_flow_returns_none_for_empty_query(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert main_module.search_flow("mpv") is None


def test_search_flow_plays_selected_station_without_saving(monkeypatch) -> None:
    inputs = iter(["rock", "n"])

    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(
        main_module,
        "search_stations",
        lambda **_kwargs: [
            {
                "name": "Raw Radio",
                "url": "https://example.com/raw",
            }
        ],
    )
    monkeypatch.setattr(
        main_module,
        "choose_station",
        lambda stations: stations[0],
    )

    played = {}

    def fake_play_station(station, player_name=None, player=None):
        played["station"] = station
        played["player_name"] = player_name
        played["player"] = player
        return "player-instance"

    monkeypatch.setattr(main_module, "play_station", fake_play_station)

    saved = []

    def fake_add_favorite(station):
        saved.append(station)
        return True

    monkeypatch.setattr(main_module, "add_favorite", fake_add_favorite)

    result = main_module.search_flow("mpv")

    assert result == "player-instance"
    assert played["station"]["name"] == "Raw Radio"
    assert played["player_name"] == "mpv"
    assert saved == []


def test_search_flow_saves_selected_station_when_requested(monkeypatch) -> None:
    inputs = iter(["rock", "y"])

    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(
        main_module,
        "search_stations",
        lambda **_kwargs: [
            {
                "name": "Raw Radio",
                "url": "https://example.com/raw",
            }
        ],
    )
    monkeypatch.setattr(main_module, "choose_station", lambda stations: stations[0])
    monkeypatch.setattr(
        main_module,
        "play_station",
        lambda station, player_name=None, player=None: "player-instance",
    )

    saved = []

    def fake_add_favorite(station):
        saved.append(station)
        return True

    monkeypatch.setattr(main_module, "add_favorite", fake_add_favorite)

    result = main_module.search_flow("mpv")

    assert result == "player-instance"
    assert saved == [
        {
            "name": "Raw Radio",
            "url": "https://example.com/raw",
            "url_resolved": "https://example.com/raw",
            "country": "Unknown",
            "countrycode": "",
            "tags": "",
            "codec": "",
            "bitrate": 0,
            "homepage": "",
            "language": "",
        }
    ]


def test_search_flow_returns_none_when_search_fails(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "rock")

    def fake_search_stations(**_kwargs):
        raise RuntimeError("network failed")

    monkeypatch.setattr(main_module, "search_stations", fake_search_stations)

    assert main_module.search_flow("mpv") is None


def test_search_flow_returns_none_when_no_station_is_selected(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "rock")
    monkeypatch.setattr(
        main_module,
        "search_stations",
        lambda **_kwargs: [{"name": "Raw Radio", "url": "https://example.com/raw"}],
    )
    monkeypatch.setattr(main_module, "choose_station", lambda _stations: None)

    assert main_module.search_flow("mpv") is None


def test_favorites_flow_returns_none_when_no_station_is_selected(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "load_favorites",
        lambda: [{"name": "Test Radio", "url": "https://example.com/stream"}],
    )
    monkeypatch.setattr(main_module, "choose_station", lambda _stations: None)

    assert main_module.favorites_flow("mpv") is None


def test_favorites_flow_plays_selected_favorite(monkeypatch) -> None:
    station = {"name": "Test Radio", "url": "https://example.com/stream"}

    monkeypatch.setattr(main_module, "load_favorites", lambda: [station])
    monkeypatch.setattr(main_module, "choose_station", lambda stations: stations[0])
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")

    played = {}

    def fake_play_station(selected_station, player_name=None, player=None):
        played["station"] = selected_station
        played["player_name"] = player_name
        played["player"] = player
        return "player-instance"

    monkeypatch.setattr(main_module, "play_station", fake_play_station)

    result = main_module.favorites_flow("mpv", player="existing-player")

    assert result == "player-instance"
    assert played == {
        "station": station,
        "player_name": "mpv",
        "player": "existing-player",
    }


def test_favorites_flow_removes_selected_favorite(monkeypatch) -> None:
    station = {"name": "Test Radio", "url": "https://example.com/stream"}

    monkeypatch.setattr(main_module, "load_favorites", lambda: [station])
    monkeypatch.setattr(main_module, "choose_station", lambda stations: stations[0])
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")

    removed = []

    def fake_remove_favorite(url: str) -> bool:
        removed.append(url)
        return True

    monkeypatch.setattr(main_module, "remove_favorite", fake_remove_favorite)

    result = main_module.favorites_flow("mpv", player="existing-player")

    assert result == "existing-player"
    assert removed == ["https://example.com/stream"]


def test_favorites_flow_unknown_choice_returns_existing_player(monkeypatch) -> None:
    station = {"name": "Test Radio", "url": "https://example.com/stream"}

    monkeypatch.setattr(main_module, "load_favorites", lambda: [station])
    monkeypatch.setattr(main_module, "choose_station", lambda stations: stations[0])
    monkeypatch.setattr("builtins.input", lambda _prompt: "unknown")

    result = main_module.favorites_flow("mpv", player="existing-player")

    assert result == "existing-player"
