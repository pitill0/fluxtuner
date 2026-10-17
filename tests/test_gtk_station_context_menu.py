from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


def _import_window_module():
    try:
        from fluxtuner.gui import window
    except ImportError as exc:
        if exc.name != "gi":
            raise

        gi = ModuleType("gi")
        gi.require_version = lambda *_args: None  # type: ignore[attr-defined]

        repository = ModuleType("gi.repository")

        class ApplicationWindow:
            pass

        gtk = SimpleNamespace(ApplicationWindow=ApplicationWindow)
        repository.GLib = SimpleNamespace()  # type: ignore[attr-defined]
        repository.Gtk = gtk  # type: ignore[attr-defined]
        repository.Pango = SimpleNamespace()  # type: ignore[attr-defined]

        sys.modules["gi"] = gi
        sys.modules["gi.repository"] = repository

        from fluxtuner.gui import window

    return window


window = _import_window_module()


def _context_harness() -> SimpleNamespace:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    return SimpleNamespace(
        selected_station=selected_station,
        status_label=Mock(),
        _station_url=lambda station: station.get("url_resolved"),
        _station_display_name=lambda station: station.get("name", ""),
        _clipboard_set_text=Mock(),
    )


def test_gtk_station_context_targets_clicked_row() -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }
    harness = SimpleNamespace(selected_station=selected_station)
    row = SimpleNamespace(station=clicked_station)

    resolved = window.MainWindow._station_from_context_row(harness, row)

    assert resolved is clicked_station
    assert harness.selected_station is selected_station


def test_gtk_context_copy_url_uses_clicked_station() -> None:
    harness = _context_harness()
    selected_station = harness.selected_station
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    window.MainWindow.copy_station_url(harness, Mock(), clicked_station)

    harness._clipboard_set_text.assert_called_once_with(
        "https://radio.example/clicked"
    )
    assert harness.selected_station is selected_station


def test_gtk_context_copy_name_uses_clicked_station() -> None:
    harness = _context_harness()
    selected_station = harness.selected_station
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    window.MainWindow.copy_station_name(harness, Mock(), clicked_station)

    harness._clipboard_set_text.assert_called_once_with("Clicked FM")
    assert harness.selected_station is selected_station


def test_gtk_context_copy_url_rejects_missing_url() -> None:
    harness = _context_harness()
    clicked_station = {"name": "Missing URL FM"}

    window.MainWindow.copy_station_url(harness, Mock(), clicked_station)

    harness._clipboard_set_text.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Station has no stream URL to copy."
    )


def test_gtk_context_actions_do_not_replace_selected_station() -> None:
    harness = _context_harness()
    selected_station = harness.selected_station
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    window.MainWindow.copy_station_url(harness, Mock(), clicked_station)
    window.MainWindow.copy_station_name(harness, Mock(), clicked_station)

    assert harness.selected_station is selected_station


def test_gtk_secondary_click_opens_context_for_clicked_row() -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    row = SimpleNamespace(station=clicked_station)
    harness = SimpleNamespace(
        selected_station=selected_station,
        _station_from_context_row=Mock(return_value=clicked_station),
        _show_station_context_menu=Mock(),
    )

    window.MainWindow.on_row_context_click(
        harness,
        Mock(),
        1,
        12.0,
        24.0,
        row,
    )

    harness._station_from_context_row.assert_called_once_with(row)
    harness._show_station_context_menu.assert_called_once_with(
        row,
        clicked_station,
        12.0,
        24.0,
    )
    assert harness.selected_station is selected_station


def test_gtk_non_secondary_context_callback_does_nothing() -> None:
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    row = SimpleNamespace(station=clicked_station)
    harness = SimpleNamespace(
        _station_from_context_row=Mock(),
        _show_station_context_menu=Mock(),
    )

    window.MainWindow.on_row_context_click(
        harness,
        Mock(),
        0,
        12.0,
        24.0,
        row,
    )

    harness._station_from_context_row.assert_not_called()
    harness._show_station_context_menu.assert_not_called()


def test_gtk_context_click_ignores_row_without_station() -> None:
    row = SimpleNamespace()
    harness = SimpleNamespace(
        _station_from_context_row=Mock(return_value=None),
        _show_station_context_menu=Mock(),
    )

    window.MainWindow.on_row_context_click(
        harness,
        Mock(),
        1,
        12.0,
        24.0,
        row,
    )

    harness._station_from_context_row.assert_called_once_with(row)
    harness._show_station_context_menu.assert_not_called()


def test_gtk_station_row_adds_secondary_click_context_gesture(monkeypatch) -> None:
    class FakeGestureClick:
        instances = []

        def __init__(self) -> None:
            self.button = None
            self.connections = []
            FakeGestureClick.instances.append(self)

        def set_button(self, button: int) -> None:
            self.button = button

        def connect(self, signal: str, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeRow:
        def __init__(self) -> None:
            self.station = None
            self.controllers = []
            self.child = None

        def add_css_class(self, _name: str) -> None:
            pass

        def add_controller(self, controller) -> None:
            self.controllers.append(controller)

        def set_child(self, child) -> None:
            self.child = child

    class FakeBox:
        def __init__(self, *args, **kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value: int) -> None:
            pass

        def set_margin_bottom(self, _value: int) -> None:
            pass

        def set_margin_start(self, _value: int) -> None:
            pass

        def set_margin_end(self, _value: int) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    monkeypatch.setattr(
        window.Gtk,
        "GestureClick",
        FakeGestureClick,
        raising=False,
    )
    monkeypatch.setattr(
        window.Gtk,
        "ListBoxRow",
        FakeRow,
        raising=False,
    )
    monkeypatch.setattr(
        window.Gtk,
        "Box",
        FakeBox,
        raising=False,
    )
    monkeypatch.setattr(
        window.Gtk,
        "Orientation",
        SimpleNamespace(HORIZONTAL=object()),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        current_station=None,
        player_capabilities=object(),
        on_row_double_click=Mock(),
        on_row_context_click=Mock(),
        _is_current_station=Mock(return_value=False),
        _append_cell=Mock(),
        _station_marker=Mock(return_value=""),
        _station_display_name=Mock(return_value="Clicked FM"),
    )

    monkeypatch.setattr(window, "station_country", Mock(return_value="Spain"))
    monkeypatch.setattr(window, "station_tags_text", Mock(return_value="rock"))
    monkeypatch.setattr(window, "station_codec", Mock(return_value="MP3"))
    monkeypatch.setattr(window, "station_bitrate", Mock(return_value=128))

    row = window.MainWindow._build_station_row(harness, station)

    assert row.station is station
    assert len(FakeGestureClick.instances) == 2

    double_click, context_click = FakeGestureClick.instances

    assert double_click.button == 0
    assert double_click.connections == [
        ("pressed", harness.on_row_double_click, (row,))
    ]

    assert context_click.button == 3
    assert context_click.connections == [
        ("pressed", harness.on_row_context_click, (row,))
    ]

    assert row.controllers == [double_click, context_click]


def test_gtk_station_context_gesture_is_independent_from_selection(monkeypatch) -> None:
    class FakeGestureClick:
        instances = []

        def __init__(self) -> None:
            self.button = None
            self.connections = []
            FakeGestureClick.instances.append(self)

        def set_button(self, button: int) -> None:
            self.button = button

        def connect(self, signal: str, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeRow:
        def __init__(self) -> None:
            self.controllers = []
            self.station = None

        def add_css_class(self, _name: str) -> None:
            pass

        def add_controller(self, controller) -> None:
            self.controllers.append(controller)

        def set_child(self, _child) -> None:
            pass

    class FakeBox:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def set_margin_top(self, _value: int) -> None:
            pass

        def set_margin_bottom(self, _value: int) -> None:
            pass

        def set_margin_start(self, _value: int) -> None:
            pass

        def set_margin_end(self, _value: int) -> None:
            pass

        def append(self, _child) -> None:
            pass

    monkeypatch.setattr(window.Gtk, "GestureClick", FakeGestureClick, raising=False)
    monkeypatch.setattr(window.Gtk, "ListBoxRow", FakeRow, raising=False)
    monkeypatch.setattr(window.Gtk, "Box", FakeBox, raising=False)
    monkeypatch.setattr(
        window.Gtk,
        "Orientation",
        SimpleNamespace(HORIZONTAL=object()),
        raising=False,
    )

    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        selected_station=selected_station,
        current_station=None,
        player_capabilities=object(),
        on_row_double_click=Mock(),
        on_row_context_click=Mock(),
        _is_current_station=Mock(return_value=False),
        _append_cell=Mock(),
        _station_marker=Mock(return_value=""),
        _station_display_name=Mock(return_value="Clicked FM"),
    )

    monkeypatch.setattr(window, "station_country", Mock(return_value="Spain"))
    monkeypatch.setattr(window, "station_tags_text", Mock(return_value="rock"))
    monkeypatch.setattr(window, "station_codec", Mock(return_value="MP3"))
    monkeypatch.setattr(window, "station_bitrate", Mock(return_value=128))

    window.MainWindow._build_station_row(harness, clicked_station)

    assert harness.selected_station is selected_station


def test_gtk_context_menu_builds_copy_actions_for_clicked_station(monkeypatch) -> None:
    class FakePopover:
        instances = []

        def __init__(self) -> None:
            self.parent = None
            self.child = None
            self.pointing_to = None
            self.popup_calls = 0
            self.connections = []
            FakePopover.instances.append(self)

        def connect(self, signal: str, callback) -> None:
            self.connections.append((signal, callback))

        def set_parent(self, parent) -> None:
            self.parent = parent

        def set_child(self, child) -> None:
            self.child = child

        def set_pointing_to(self, rectangle) -> None:
            self.pointing_to = rectangle

        def popup(self) -> None:
            self.popup_calls += 1

    class FakeBox:
        def __init__(self, *args, **kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value: int) -> None:
            pass

        def set_margin_bottom(self, _value: int) -> None:
            pass

        def set_margin_start(self, _value: int) -> None:
            pass

        def set_margin_end(self, _value: int) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal: str, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeRectangle:
        def __init__(self, x: int, y: int, width: int, height: int) -> None:
            self.x = x
            self.y = y
            self.width = width
            self.height = height

    monkeypatch.setattr(window.Gtk, "Popover", FakePopover, raising=False)
    monkeypatch.setattr(window.Gtk, "Box", FakeBox, raising=False)
    monkeypatch.setattr(window.Gtk, "Button", FakeButton, raising=False)
    monkeypatch.setattr(
        window.Gtk,
        "Orientation",
        SimpleNamespace(VERTICAL=object()),
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=FakeRectangle),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }
    row = object()

    harness = SimpleNamespace(
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _on_station_context_menu_closed=lambda popover: popover.unparent(),
        selected_station={
            "name": "Selected FM",
            "url_resolved": "https://radio.example/selected",
        },
    )
    selected_station = harness.selected_station

    window.MainWindow._show_station_context_menu(
        harness,
        row,
        station,
        12.4,
        24.8,
    )

    assert len(FakePopover.instances) == 1
    popover = FakePopover.instances[0]
    assert popover.parent is row
    assert popover.popup_calls == 1
    assert popover.pointing_to.x == 12
    assert popover.pointing_to.y == 24
    assert popover.pointing_to.width == 1
    assert popover.pointing_to.height == 1

    assert [button.label for button in popover.child.children] == [
        "Copy stream URL",
        "Copy station name",
    ]

    copy_url_button, copy_name_button = popover.child.children
    assert copy_url_button.connections == [
        ("clicked", harness.copy_station_url, (station,))
    ]
    assert copy_name_button.connections == [
        ("clicked", harness.copy_station_name, (station,))
    ]

    assert harness.selected_station is selected_station


def test_gtk_context_menu_button_callbacks_use_gtk_clicked_signature(
    monkeypatch,
) -> None:
    class FakePopover:
        def __init__(self) -> None:
            self.child = None
            self.connections = []

        def set_parent(self, _parent) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def connect(self, signal: str, callback) -> None:
            self.connections.append((signal, callback))

        def popup(self) -> None:
            pass

    class FakeBox:
        def __init__(self, *args, **kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value: int) -> None:
            pass

        def set_margin_bottom(self, _value: int) -> None:
            pass

        def set_margin_start(self, _value: int) -> None:
            pass

        def set_margin_end(self, _value: int) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakeButton:
        instances = []

        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []
            FakeButton.instances.append(self)

        def connect(self, signal: str, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    monkeypatch.setattr(window.Gtk, "Popover", FakePopover, raising=False)
    monkeypatch.setattr(window.Gtk, "Box", FakeBox, raising=False)
    monkeypatch.setattr(window.Gtk, "Button", FakeButton, raising=False)
    monkeypatch.setattr(
        window.Gtk,
        "Orientation",
        SimpleNamespace(VERTICAL=object()),
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=FakeRectangle),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        copy_station_url=lambda _button, target: target,
        copy_station_name=lambda _button, target: target,
        _on_station_context_menu_closed=lambda popover: popover.unparent(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    for button in FakeButton.instances:
        _, callback, callback_args = button.connections[0]
        callback(button, *callback_args)


def test_gtk_context_menu_unparents_popover_when_closed(monkeypatch) -> None:
    class FakePopover:
        instances = []

        def __init__(self) -> None:
            self.connections = []
            self.unparent_calls = 0
            FakePopover.instances.append(self)

        def set_parent(self, _parent) -> None:
            pass

        def set_child(self, _child) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def connect(self, signal: str, callback) -> None:
            self.connections.append((signal, callback))

        def unparent(self) -> None:
            self.unparent_calls += 1

        def popup(self) -> None:
            pass

    class FakeBox:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def set_margin_top(self, _value: int) -> None:
            pass

        def set_margin_bottom(self, _value: int) -> None:
            pass

        def set_margin_start(self, _value: int) -> None:
            pass

        def set_margin_end(self, _value: int) -> None:
            pass

        def append(self, _child) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            pass

        def connect(self, _signal: str, _callback, *_args) -> None:
            pass

    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    monkeypatch.setattr(window.Gtk, "Popover", FakePopover, raising=False)
    monkeypatch.setattr(window.Gtk, "Box", FakeBox, raising=False)
    monkeypatch.setattr(window.Gtk, "Button", FakeButton, raising=False)
    monkeypatch.setattr(
        window.Gtk,
        "Orientation",
        SimpleNamespace(VERTICAL=object()),
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=FakeRectangle),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _on_station_context_menu_closed=lambda popover: popover.unparent(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    popover = FakePopover.instances[0]

    assert len(popover.connections) == 1
    signal, callback = popover.connections[0]
    assert signal == "closed"

    callback(popover)

    assert popover.unparent_calls == 1



def test_gtk_clipboard_set_text_uses_text_api() -> None:
    clipboard = Mock()
    display = Mock()
    display.get_clipboard.return_value = clipboard

    harness = SimpleNamespace(
        get_display=Mock(return_value=display),
    )

    window.MainWindow._clipboard_set_text(harness, "Clicked FM")

    display.get_clipboard.assert_called_once_with()
    clipboard.set_text.assert_called_once_with("Clicked FM")
    clipboard.set.assert_not_called()
