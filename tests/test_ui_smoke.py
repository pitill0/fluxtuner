import importlib
import os

import pytest


def test_tui_module_imports() -> None:
    module = importlib.import_module("fluxtuner.tui")

    assert hasattr(module, "FluxTunerTUI")


def test_tui_app_can_be_constructed_with_mocked_runtime_dependencies(monkeypatch) -> None:
    from fluxtuner import tui

    class FakePlayer:
        def supports_mute(self) -> bool:
            return True

        def supports_volume(self) -> bool:
            return True

        def supports_pause(self) -> bool:
            return True

        def get_state(self) -> dict[str, object]:
            return {"playing": False}

    monkeypatch.setattr(tui, "selected_player_name", lambda _name: "mpv")
    monkeypatch.setattr(tui, "create_player", lambda _name: FakePlayer())
    monkeypatch.setattr(tui, "get_theme_path", lambda _theme: "fluxtuner/themes/default.tcss")

    app = tui.FluxTunerTUI(theme="default", player_name="auto")

    assert app.player_backend_name == "mpv"
    assert app.active_theme == "default"


def test_gui_module_imports_and_sets_default_renderer(monkeypatch) -> None:
    monkeypatch.delenv("GSK_RENDERER", raising=False)

    module = importlib.import_module("fluxtuner.gui.app")

    assert module is not None
    assert os.environ["GSK_RENDERER"] == "cairo"


def test_gui_module_does_not_override_existing_renderer(monkeypatch) -> None:
    monkeypatch.setenv("GSK_RENDERER", "ngl")

    module = importlib.reload(importlib.import_module("fluxtuner.gui.app"))

    assert module is not None
    assert os.environ["GSK_RENDERER"] == "ngl"


def test_run_gui_reports_missing_gtk_dependencies(monkeypatch) -> None:
    gui_app = importlib.import_module("fluxtuner.gui.app")

    def fake_import(name, *args, **kwargs):
        if name == "gi":
            raise ImportError("missing gi")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="GTK GUI dependencies are not available"):
        gui_app.run_gui()
