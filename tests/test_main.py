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
