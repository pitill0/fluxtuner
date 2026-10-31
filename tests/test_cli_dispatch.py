# SPDX-License-Identifier: MIT
"""Command precedence and interface selection through the public CLI entrypoint."""

from __future__ import annotations

import sys
import types

import pytest

from fluxtuner import __main__ as cli


@pytest.fixture
def isolated_cli(monkeypatch):
    monkeypatch.setattr(cli, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "resolve_effective_profile_name", lambda profile: profile)
    monkeypatch.setattr(cli, "get_config_value", lambda key, default: default)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--clear-active-profile", "--list-players"], "clear-profile"),
        (["--list-players", "--doctor"], "players"),
        (["--list-profiles", "--list-themes"], "profiles"),
        (["--clear-cache", "--export-favs", "unused.json"], "clear-cache"),
    ],
)
def test_terminal_command_priority_avoids_later_side_effects(
    isolated_cli, monkeypatch, arguments, expected
):
    events = []
    monkeypatch.setattr(cli, "clear_active_profile_name", lambda: events.append("clear-profile"))
    monkeypatch.setattr(cli, "print_player_backend_status", lambda: events.append("players"))
    monkeypatch.setattr(cli, "run_doctor", lambda: events.append("doctor"))
    monkeypatch.setattr(cli, "print_profiles", lambda: events.append("profiles"))
    monkeypatch.setattr(cli, "list_themes", lambda: events.append("themes") or ["default"])
    monkeypatch.setattr(cli, "clear_search_cache", lambda: events.append("clear-cache"))

    def unexpected(*args, **kwargs):
        pytest.fail("A lower-priority operation ran")

    monkeypatch.setattr(cli, "load_favorites", unexpected)
    monkeypatch.setattr(cli, "selected_player_name", unexpected)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", *arguments])
    cli.main()
    assert events == [expected]


def test_cli_mode_precedes_gui_and_uses_explicit_profile(isolated_cli, monkeypatch):
    events = []
    monkeypatch.setattr(cli, "selected_player_name", lambda player: "mpv")
    monkeypatch.setattr(
        cli, "run_cli", lambda player, *, profile_name: events.append((player, profile_name))
    )
    monkeypatch.setitem(sys.modules, "fluxtuner.gui.app", None)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "--cli", "--gui", "--profile", "work"])
    cli.main()
    assert events == [("mpv", "work")]


def test_gui_launch_preserves_backend_selection(isolated_cli, monkeypatch):
    events = []
    monkeypatch.setattr(cli, "selected_player_name", lambda player: "ffplay")
    fake_gui = types.ModuleType("fluxtuner.gui.app")
    fake_gui.run_gui = lambda *, player_name: events.append(player_name)
    monkeypatch.setitem(sys.modules, "fluxtuner.gui.app", fake_gui)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "--gui"])
    cli.main()
    assert events == ["ffplay"]


def test_missing_gui_dependency_keeps_exit_status(isolated_cli, monkeypatch):
    monkeypatch.setattr(cli, "selected_player_name", lambda player: "mpv")
    monkeypatch.setitem(sys.modules, "fluxtuner.gui.app", None)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "--gui"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1


def test_web_command_precedes_profile_and_diagnostic_flags(isolated_cli, monkeypatch):
    from fluxtuner.web import admin_cli

    events = []
    monkeypatch.setattr(
        admin_cli,
        "handle_web_user_command",
        lambda command, *, console: events.append(command) or True,
    )

    def unexpected(*args, **kwargs):
        pytest.fail("A lower-priority operation ran")

    monkeypatch.setattr(cli, "resolve_effective_profile_name", unexpected)
    monkeypatch.setattr(cli, "print_player_backend_status", unexpected)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "--list-players", "web-user", "list"])
    cli.main()
    assert events == [["web-user", "list"]]


def test_unrecognized_web_command_keeps_argparse_error(isolated_cli, monkeypatch, capsys):
    from fluxtuner.web import admin_cli

    monkeypatch.setattr(admin_cli, "handle_web_user_command", lambda command, *, console: False)
    monkeypatch.setattr(sys, "argv", ["fluxtuner", "not-a-command"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "unknown command: not-a-command" in capsys.readouterr().err
