"""Tests for the independent GTK application menu model."""

from __future__ import annotations

from types import SimpleNamespace

from fluxtuner.gui.gtk_application_menu import build_application_menu_model


class FakeMenu:
    def __init__(self) -> None:
        self.items: list[tuple[str, object, object]] = []

    def append(self, label: str, action: str) -> None:
        self.items.append(("action", label, action))

    def append_submenu(self, label: str, submenu: FakeMenu) -> None:
        self.items.append(("submenu", label, submenu))

    def append_section(self, label: str | None, section: FakeMenu) -> None:
        self.items.append(("section", label, section))


def test_application_menu_has_native_stations_submenu() -> None:
    root = build_application_menu_model(SimpleNamespace(Menu=FakeMenu))

    kind, label, stations = root.items[0]
    assert (kind, label) == ("submenu", "Stations")
    assert isinstance(stations, FakeMenu)
    assert stations.items == [
        ("action", "Add station…", "win.station-add"),
        ("action", "Import stations…", "win.station-import"),
        ("action", "Import stations from URL…", "win.station-import-url"),
    ]


def test_application_actions_remain_at_top_level() -> None:
    root = build_application_menu_model(SimpleNamespace(Menu=FakeMenu))

    kind, label, section = root.items[1]
    assert (kind, label) == ("section", None)
    assert isinstance(section, FakeMenu)
    assert section.items == [
        ("action", "Preferences…", "win.preferences"),
        ("action", "About FluxTuner", "win.about"),
    ]

    assert root.items[2] == ("action", "Quit", "app.quit")


def test_menu_actions_are_unique() -> None:
    root = build_application_menu_model(SimpleNamespace(Menu=FakeMenu))

    actions: list[str] = []

    def collect(menu: FakeMenu) -> None:
        for kind, _label, value in menu.items:
            if kind == "action":
                assert isinstance(value, str)
                actions.append(value)
            else:
                assert isinstance(value, FakeMenu)
                collect(value)

    collect(root)

    assert len(actions) == 6
    assert len(actions) == len(set(actions))
    assert actions.count("app.quit") == 1
