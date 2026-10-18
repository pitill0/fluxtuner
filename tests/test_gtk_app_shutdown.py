from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui import app


def _run_tray_quit_scenario(monkeypatch, scenario, *, ready=True, activate=True):
    application = Mock()
    window = Mock()
    window.shutdown.return_value = ready
    tray = Mock()
    tray.start.return_value = True
    handlers = {}
    callbacks = {}
    create_window = Mock(return_value=window)

    def install_module(name, **attributes):
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)

    install_module("gi", require_version=Mock())
    install_module(
        "gi.repository",
        Gtk=SimpleNamespace(Application=Mock(return_value=application)),
        Gio=SimpleNamespace(ApplicationFlags=SimpleNamespace(NON_UNIQUE=object())),
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
    monkeypatch.setattr(app.sys, "platform", "linux")

    def connect(signal, callback):
        handlers[signal] = callback

    def run():
        if activate:
            handlers["activate"](application)
        scenario(application, window, callbacks)

    application.connect.side_effect = connect
    application.run.side_effect = run

    app.run_gui()

    application.hold.assert_called_once_with()
    tray.stop.assert_called_once_with()
    if not activate:
        create_window.assert_not_called()


@pytest.mark.parametrize("ready", [True, False])
def test_gtk_app_tray_quit_respects_shutdown_readiness(monkeypatch, ready) -> None:
    def scenario(application, window, callbacks):
        callbacks["on_quit"]()

        assert window.close_to_tray is False
        window.shutdown.assert_called_once()
        completion = window.shutdown.call_args.kwargs.get("on_complete")
        assert callable(completion)
        if not ready:
            application.release.assert_not_called()
            application.quit.assert_not_called()
            completion()
        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=ready)


def test_gtk_app_tray_quit_finishes_once_after_repeated_requests(monkeypatch) -> None:
    def scenario(application, window, callbacks):
        callbacks["on_quit"]()
        callbacks["on_quit"]()
        application.release.assert_not_called()
        application.quit.assert_not_called()

        completion = window.shutdown.call_args.kwargs["on_complete"]
        completion()
        completion()
        callbacks["on_quit"]()

        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, ready=False)


def test_gtk_app_tray_quit_before_window_activation(monkeypatch) -> None:
    def scenario(application, window, callbacks):
        callbacks["on_quit"]()

        window.shutdown.assert_not_called()
        application.release.assert_called_once_with()
        application.quit.assert_called_once_with()

    _run_tray_quit_scenario(monkeypatch, scenario, activate=False)
