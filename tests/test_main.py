import json
from pathlib import Path

import pytest

from fluxtuner import __main__ as main_module


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
