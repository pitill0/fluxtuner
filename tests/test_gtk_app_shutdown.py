from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui import app


def _run_tray_quit_scenario(
    monkeypatch,
    scenario,
    *,
    ready=True,
    activate=True,
    platform="linux",
    tray_available=True,
):
    application = Mock()
    window = Mock()
    window.shutdown.return_value = ready
    tray = Mock()
    tray.start.return_value = tray_available
    handlers = {}
    callbacks = {}
    create_window = Mock(return_value=window)
    quit_action = Mock()

    def connect_action(signal, callback):
        assert signal == "activate"
        callbacks["menu_quit"] = lambda: callback(quit_action, None)

    quit_action.connect.side_effect = connect_action

    def install_module(name, **attributes):
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)

    install_module("gi", require_version=Mock())
    install_module(
        "gi.repository",
        Gtk=SimpleNamespace(Application=Mock(return_value=application)),
        Gio=SimpleNamespace(
            ApplicationFlags=SimpleNamespace(NON_UNIQUE=object()),
            SimpleAction=SimpleNamespace(new=Mock(return_value=quit_action)),
        ),
        Gdk=SimpleNamespace(Display=SimpleNamespace(get_default=lambda: None)),
    )
    install_module("fluxtuner.gui.window", MainWindow=create_window)
    install_module("fluxtuner.gui.appearance", GtkAppearanceManager=Mock())

    def create_tray(**kwargs):
        callbacks.update(kwargs)
        return tray

    install_module(
        "fluxtuner.gui.tray.linux_sni",
        LinuxStatusNotifierItem=create_tray,
    )
    monkeypatch.setattr(app.sys, "platform", platform)

    def connect(signal, callback):
        handlers[signal] = callback

    def run():
        if activate:
            handlers["activate"](application)
        scenario(application, window, callbacks)

    application.connect.side_effect = connect
    application.run.side_effect = run

    app.run_gui()

    application.add_action.assert_called_once_with(quit_action)
    application.set_accels_for_action.assert_called_once_with("app.quit", ["<Primary>q"])

    if platform.startswith("linux") and tray_available:
        application.hold.assert_called_once_with()
        tray.stop.assert_called_once_with()
    else:
        application.hold.assert_not_called()
        tray.stop.assert_not_called()
    if not activate:
        create_window.assert_not_called()


@pytest.mark.parametrize("ready", [True, False])
def test_gtk_app_tray_quit_respects_shutdown_readiness(monkeypatch, ready) -> None:
    def scenario(application, window, callbacks):
        pending = []
        initial_tray_mode = window.close_to_tray

        def request_quit(*, on_complete):
            if ready:
                on_complete()
            else:
                pending.append(on_complete)

        window.request_quit.side_effect = request_quit

        callbacks["on_quit"]()

        window.request_quit.assert_called_once()
        window.shutdown.assert_not_called()
        assert window.close_to_tray is initial_tray_mode

        if not ready:
            application.release.assert_not_called()
            application.quit.assert_not_called()
            assert len(pending) == 1
            pending[0]()

        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=ready)


def test_gtk_app_tray_quit_finishes_once_after_repeated_requests(monkeypatch) -> None:
    def scenario(application, window, callbacks):
        pending = []
        window.request_quit.side_effect = lambda *, on_complete: pending.append(on_complete)

        callbacks["on_quit"]()
        callbacks["on_quit"]()

        assert len(pending) == 2
        window.shutdown.assert_not_called()
        application.release.assert_not_called()
        application.quit.assert_not_called()

        pending[0]()
        pending[0]()
        pending[1]()
        callbacks["on_quit"]()

        assert window.request_quit.call_count == 2
        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=False)


def test_gtk_app_tray_quit_before_window_activation(monkeypatch) -> None:
    def scenario(application, window, callbacks):
        callbacks["on_quit"]()

        window.request_quit.assert_not_called()
        window.shutdown.assert_not_called()
        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, activate=False)


@pytest.mark.parametrize(
    ("platform", "tray_available"),
    [("linux", True), ("linux", False), ("darwin", False)],
)
@pytest.mark.parametrize("ready", [True, False])
def test_menu_quit_waits_for_shutdown_with_or_without_tray(
    monkeypatch, platform, tray_available, ready
) -> None:
    def scenario(application, window, callbacks):
        pending = []
        initial_tray_mode = window.close_to_tray

        def request_quit(*, on_complete):
            if ready:
                on_complete()
            else:
                pending.append(on_complete)

        window.request_quit.side_effect = request_quit

        callbacks["menu_quit"]()

        window.request_quit.assert_called_once()
        window.shutdown.assert_not_called()
        assert window.close_to_tray is initial_tray_mode

        if not ready:
            application.quit.assert_not_called()
            application.release.assert_not_called()
            assert len(pending) == 1
            pending[0]()

        application.quit.assert_called_once_with()
        if platform == "linux" and tray_available:
            application.release.assert_called_once_with()
        else:
            application.release.assert_not_called()

        completion = window.request_quit.call_args.kwargs["on_complete"]
        completion()
        callbacks["menu_quit"]()
        window.request_quit.assert_called_once()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(
        monkeypatch,
        scenario,
        ready=ready,
        platform=platform,
        tray_available=tray_available,
    )


def test_gtk_app_quit_delegates_confirmation_to_window(monkeypatch) -> None:
    """A Quit request must not start shutdown before window approval."""

    def scenario(application, window, callbacks):
        callbacks["menu_quit"]()

        window.request_quit.assert_called_once()
        completion = window.request_quit.call_args.kwargs["on_complete"]
        assert callable(completion)

        window.shutdown.assert_not_called()
        application.quit.assert_not_called()
        application.release.assert_not_called()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=False)


def test_gtk_app_quit_finishes_once_after_window_approval(monkeypatch) -> None:
    """The window approval callback owns the actual application exit."""

    def scenario(application, window, callbacks):
        approved = []

        def request_quit(*, on_complete):
            approved.append(on_complete)

        window.request_quit.side_effect = request_quit

        callbacks["menu_quit"]()

        assert len(approved) == 1
        window.shutdown.assert_not_called()
        application.quit.assert_not_called()

        approved[0]()
        approved[0]()
        callbacks["menu_quit"]()

        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=False)
