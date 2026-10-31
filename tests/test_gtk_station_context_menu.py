from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


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

    harness._clipboard_set_text.assert_called_once_with("https://radio.example/clicked")
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
    harness.status_label.set_text.assert_called_once_with("Station has no stream URL to copy.")


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
    assert double_click.connections == [("pressed", harness.on_row_double_click, (row,))]

    assert context_click.button == 3
    assert context_click.connections == [("pressed", harness.on_row_context_click, (row,))]

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


def test_gtk_context_menu_builds_copy_actions_for_clicked_station(monkeypatch) -> None:  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        _is_favorite_station=Mock(return_value=False),
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
        "Play",
        "Add to favorites",
        "Add to playlist…",
        "Copy stream URL",
        "Copy station name",
    ]

    (
        play_button,
        favorite_button,
        playlist_button,
        copy_url_button,
        copy_name_button,
    ) = popover.child.children

    assert play_button.connections == [("clicked", harness.on_context_play_clicked, (station,))]
    assert favorite_button.connections == [
        (
            "clicked",
            harness.on_context_add_favorite_clicked,
            (station,),
        )
    ]
    assert playlist_button.connections == [
        ("clicked", harness.on_context_add_playlist_clicked, (station,))
    ]
    assert copy_url_button.connections == [("clicked", harness.copy_station_url, (station,))]
    assert copy_name_button.connections == [("clicked", harness.copy_station_name, (station,))]

    assert harness.selected_station is selected_station


def test_gtk_context_menu_button_callbacks_use_gtk_clicked_signature(  # noqa: C901 - reviewed ceiling 17; see docs/complexity-baseline.json
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
        on_context_play_clicked=lambda _button, target: target,
        on_context_add_favorite_clicked=lambda _button, target: target,
        on_context_add_playlist_clicked=lambda _button, target: target,
        on_context_remove_favorite_clicked=lambda _button, target: target,
        _is_favorite_station=lambda _station: False,
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


def test_gtk_context_menu_unparents_popover_when_closed(monkeypatch) -> None:  # noqa: C901 - reviewed ceiling 17; see docs/complexity-baseline.json
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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        _is_favorite_station=Mock(return_value=False),
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


def test_gtk_clipboard_set_text_uses_gtk4_clipboard_api() -> None:
    clipboard = Mock()
    display = Mock()
    display.get_clipboard.return_value = clipboard

    harness = SimpleNamespace(
        get_display=Mock(return_value=display),
    )

    window.MainWindow._clipboard_set_text(harness, "Clicked FM")

    display.get_clipboard.assert_called_once_with()
    clipboard.set.assert_called_once_with("Clicked FM")
    clipboard.set_text.assert_not_called()


def test_gtk_context_play_targets_explicit_station_without_changing_selection(
    monkeypatch,
) -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    result = SimpleNamespace(
        success=True,
        station=clicked_station,
        status="Playing Clicked FM",
    )

    playback_start = Mock(return_value=result)
    monkeypatch.setattr(window, "coordinate_playback_start", playback_start)

    harness = SimpleNamespace(
        selected_station=selected_station,
        player=object(),
        player_backend_name="test",
        player_capabilities=object(),
        profile_name="default",
        restored_muted=False,
        status_label=Mock(),
        _station_url=Mock(),
        _apply_player_preferences_before_start=Mock(),
        _set_player_volume_from_scale=Mock(),
        _set_player_mute=Mock(),
        usage_tracker=object(),
        current_station=None,
        update_now_playing=Mock(),
        update_data_usage=Mock(),
        update_player_state=Mock(),
        _ensure_usage_timer=Mock(),
        _ensure_player_state_timer=Mock(),
        _update_play_stop_button=Mock(),
        _render_results=Mock(),
    )

    window.MainWindow.play_station(harness, clicked_station)

    assert playback_start.call_args.args[0] is clicked_station
    assert harness.current_station is clicked_station
    assert harness.selected_station is selected_station


def test_gtk_context_play_callback_uses_clicked_station() -> None:
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
        play_station=Mock(),
    )

    window.MainWindow.on_context_play_clicked(
        harness,
        Mock(),
        clicked_station,
    )

    harness.play_station.assert_called_once_with(clicked_station)
    assert harness.selected_station is selected_station


def test_gtk_add_explicit_station_to_favorites_without_changing_selection(
    monkeypatch,
) -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    add = Mock(return_value=True)
    monkeypatch.setattr(window, "add_favorite", add)

    harness = SimpleNamespace(
        selected_station=selected_station,
        profile_name="default",
        status_label=Mock(),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_favorite_buttons=Mock(),
    )

    window.MainWindow.add_station_to_favorites(
        harness,
        clicked_station,
    )

    add.assert_called_once_with(
        clicked_station,
        profile_name="default",
    )
    harness._refresh_favorite_cache.assert_called_once_with()
    harness._render_results.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with("Added to favorites.")
    assert harness.selected_station is selected_station


def test_gtk_remove_explicit_station_from_favorites_without_changing_selection(
    monkeypatch,
) -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    remove = Mock(return_value=True)
    monkeypatch.setattr(window, "remove_favorite", remove)
    monkeypatch.setattr(
        window,
        "station_key",
        Mock(return_value="https://radio.example/clicked"),
    )

    harness = SimpleNamespace(
        selected_station=selected_station,
        profile_name="default",
        status_label=Mock(),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_favorite_buttons=Mock(),
        _view_state=SimpleNamespace(current_view="search"),
    )

    window.MainWindow.remove_station_from_favorites(
        harness,
        clicked_station,
    )

    remove.assert_called_once_with(
        "https://radio.example/clicked",
        profile_name="default",
    )
    harness._refresh_favorite_cache.assert_called_once_with()
    harness._render_results.assert_called_once_with()
    harness._update_favorite_buttons.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with("Removed from favorites.")
    assert harness.selected_station is selected_station


def test_gtk_context_favorite_callback_targets_clicked_station() -> None:
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
        add_station_to_favorites=Mock(),
        remove_station_from_favorites=Mock(),
    )

    window.MainWindow.on_context_add_favorite_clicked(
        harness,
        Mock(),
        clicked_station,
    )
    window.MainWindow.on_context_remove_favorite_clicked(
        harness,
        Mock(),
        clicked_station,
    )

    harness.add_station_to_favorites.assert_called_once_with(clicked_station)
    harness.remove_station_from_favorites.assert_called_once_with(clicked_station)
    assert harness.selected_station is selected_station


def test_gtk_selected_favorite_handlers_delegate_to_explicit_station_seams() -> None:
    station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }

    harness = SimpleNamespace(
        selected_station=station,
        add_station_to_favorites=Mock(),
        remove_station_from_favorites=Mock(),
    )

    window.MainWindow.on_add_favorite_clicked(harness, Mock())
    window.MainWindow.on_remove_favorite_clicked(harness, Mock())

    harness.add_station_to_favorites.assert_called_once_with(station)
    harness.remove_station_from_favorites.assert_called_once_with(station)


def test_gtk_remove_context_favorite_preserves_other_selection_in_favorites_view(
    monkeypatch,
) -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }
    reloaded_selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }

    monkeypatch.setattr(window, "remove_favorite", Mock(return_value=True))
    monkeypatch.setattr(
        window,
        "load_favorites",
        Mock(return_value=[reloaded_selected_station]),
    )

    harness = SimpleNamespace(
        selected_station=selected_station,
        stations=[selected_station, clicked_station],
        profile_name="default",
        status_label=Mock(),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_favorite_buttons=Mock(),
        _view_state=SimpleNamespace(current_view="favorites"),
    )

    window.MainWindow.remove_station_from_favorites(
        harness,
        clicked_station,
    )

    assert harness.stations == [reloaded_selected_station]
    assert harness.selected_station is reloaded_selected_station


def test_gtk_remove_context_favorite_clears_selection_when_selected_station_is_removed(
    monkeypatch,
) -> None:
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }
    remaining_station = {
        "name": "Remaining FM",
        "url_resolved": "https://radio.example/remaining",
    }

    monkeypatch.setattr(window, "remove_favorite", Mock(return_value=True))
    monkeypatch.setattr(
        window,
        "load_favorites",
        Mock(return_value=[remaining_station]),
    )

    harness = SimpleNamespace(
        selected_station=clicked_station,
        stations=[clicked_station, remaining_station],
        profile_name="default",
        status_label=Mock(),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_favorite_buttons=Mock(),
        _view_state=SimpleNamespace(current_view="favorites"),
    )

    window.MainWindow.remove_station_from_favorites(
        harness,
        clicked_station,
    )

    assert harness.stations == [remaining_station]
    assert harness.selected_station is None


def test_gtk_context_menu_shows_add_to_favorites_for_non_favorite_station(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, x, y, width, height) -> None:
            self.x = x
            self.y = y
            self.width = width
            self.height = height

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rect) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert labels == [
        "Play",
        "Add to favorites",
        "Add to playlist…",
        "Copy stream URL",
        "Copy station name",
    ]

    favorite_button = FakePopover.last_created.child.children[1]
    assert favorite_button.connections == [
        (
            "clicked",
            harness.on_context_add_favorite_clicked,
            (station,),
        )
    ]


def test_gtk_context_menu_shows_remove_from_favorites_for_favorite_station(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, x, y, width, height) -> None:
            self.x = x
            self.y = y
            self.width = width
            self.height = height

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rect) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=True),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert labels == [
        "Play",
        "Remove from favorites",
        "Add to playlist…",
        "Copy stream URL",
        "Copy station name",
    ]

    favorite_button = FakePopover.last_created.child.children[1]
    assert favorite_button.connections == [
        (
            "clicked",
            harness.on_context_remove_favorite_clicked,
            (station,),
        )
    ]


def test_gtk_open_station_homepage_targets_explicit_station_without_changing_selection() -> None:
    selected_station = {
        "name": "Selected FM",
        "homepage": "https://selected.example",
    }
    clicked_station = {
        "name": "Clicked FM",
        "homepage": "https://clicked.example/",
    }

    harness = SimpleNamespace(
        selected_station=selected_station,
        status_label=Mock(),
        _open_external_uri=Mock(),
    )

    window.MainWindow.open_station_homepage(
        harness,
        clicked_station,
    )

    harness._open_external_uri.assert_called_once_with("https://clicked.example/")
    harness.status_label.set_text.assert_not_called()
    assert harness.selected_station is selected_station


def test_gtk_open_station_homepage_rejects_missing_homepage() -> None:
    station = {
        "name": "Clicked FM",
        "homepage": "",
    }

    harness = SimpleNamespace(
        status_label=Mock(),
        _open_external_uri=Mock(),
    )

    window.MainWindow.open_station_homepage(
        harness,
        station,
    )

    harness._open_external_uri.assert_not_called()
    harness.status_label.set_text.assert_called_once_with("Station has no homepage.")


def test_gtk_open_station_homepage_rejects_non_http_uri() -> None:
    station = {
        "name": "Clicked FM",
        "homepage": "file:///tmp/example.html",
    }

    harness = SimpleNamespace(
        status_label=Mock(),
        _open_external_uri=Mock(),
    )

    window.MainWindow.open_station_homepage(
        harness,
        station,
    )

    harness._open_external_uri.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Station homepage URL is not safe to open."
    )


def test_gtk_context_open_homepage_callback_targets_clicked_station() -> None:
    selected_station = {
        "name": "Selected FM",
        "homepage": "https://selected.example",
    }
    clicked_station = {
        "name": "Clicked FM",
        "homepage": "https://clicked.example",
    }

    harness = SimpleNamespace(
        selected_station=selected_station,
        open_station_homepage=Mock(),
    )

    window.MainWindow.on_context_open_homepage_clicked(
        harness,
        Mock(),
        clicked_station,
    )

    harness.open_station_homepage.assert_called_once_with(clicked_station)
    assert harness.selected_station is selected_station


def test_gtk_open_external_uri_uses_gio_default_launcher(
    monkeypatch,
) -> None:
    launch_default_for_uri = Mock()

    fake_gio = SimpleNamespace(
        AppInfo=SimpleNamespace(
            launch_default_for_uri=launch_default_for_uri,
        ),
    )

    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gio",
        fake_gio,
        raising=False,
    )

    window.MainWindow._open_external_uri(
        SimpleNamespace(),
        "https://clicked.example/",
    )

    launch_default_for_uri.assert_called_once_with(
        "https://clicked.example/",
        None,
    )


def test_gtk_open_station_homepage_contains_launcher_failure() -> None:
    station = {
        "name": "Clicked FM",
        "homepage": "https://clicked.example/",
    }

    harness = SimpleNamespace(
        status_label=Mock(),
        _open_external_uri=Mock(
            side_effect=RuntimeError("launcher unavailable"),
        ),
    )

    window.MainWindow.open_station_homepage(
        harness,
        station,
    )

    harness._open_external_uri.assert_called_once_with("https://clicked.example/")
    harness.status_label.set_text.assert_called_once_with(
        "Could not open station homepage: launcher unavailable"
    )


def test_gtk_context_menu_shows_open_homepage_for_safe_homepage(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=FakeRectangle),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "homepage": "https://clicked.example/",
    }

    harness = SimpleNamespace(
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert labels == [
        "Play",
        "Add to favorites",
        "Add to playlist…",
        "Open station homepage",
        "Copy stream URL",
        "Copy station name",
    ]

    homepage_button = FakePopover.last_created.child.children[3]
    assert homepage_button.connections == [
        (
            "clicked",
            harness.on_context_open_homepage_clicked,
            (station,),
        )
    ]


def test_gtk_context_menu_hides_open_homepage_without_safe_homepage(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label

        def connect(self, *_args) -> None:
            pass

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=FakeRectangle),
        raising=False,
    )

    station = {
        "name": "Clicked FM",
        "homepage": "file:///tmp/example.html",
    }

    harness = SimpleNamespace(
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert labels == [
        "Play",
        "Add to favorites",
        "Add to playlist…",
        "Copy stream URL",
        "Copy station name",
    ]


def test_gtk_start_recording_targets_explicit_station_without_changing_selection(
    monkeypatch,
    tmp_path,
) -> None:
    selected_station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }
    clicked_station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }
    output = tmp_path / "clicked-fm.mka"

    monkeypatch.setattr(
        window,
        "recording_output_path",
        Mock(return_value=output),
    )

    manager = Mock()
    manager.active_session = None

    harness = SimpleNamespace(
        selected_station=selected_station,
        recording_available=True,
        recording_manager=manager,
        status_label=Mock(),
        _station_url=Mock(side_effect=lambda station: station["url_resolved"]),
        _station_display_name=Mock(side_effect=lambda station: station["name"]),
        _update_record_button=Mock(),
    )

    window.MainWindow.start_station_recording(
        harness,
        clicked_station,
    )

    request = manager.start.call_args.args[0]
    assert request.station_name == "Clicked FM"
    assert request.source_url == "https://radio.example/clicked"
    assert request.output_path == output
    assert harness.selected_station is selected_station

    harness._update_record_button.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(f"Recording: Clicked FM → {output.name}")


def test_gtk_context_record_callback_targets_clicked_station() -> None:
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
        start_station_recording=Mock(),
    )

    window.MainWindow.on_context_record_clicked(
        harness,
        Mock(),
        clicked_station,
    )

    harness.start_station_recording.assert_called_once_with(clicked_station)
    assert harness.selected_station is selected_station


def test_gtk_selected_recording_delegates_to_explicit_station_seam() -> None:
    station = {
        "name": "Selected FM",
        "url_resolved": "https://radio.example/selected",
    }

    harness = SimpleNamespace(
        selected_station=station,
        recording_available=True,
        start_station_recording=Mock(),
        status_label=Mock(),
        _update_record_button=Mock(),
    )

    window.MainWindow.start_selected_recording(harness)

    harness.start_station_recording.assert_called_once_with(station)


def test_gtk_station_recording_state_matches_active_session_source_url() -> None:
    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        recording_manager=SimpleNamespace(
            active_session=SimpleNamespace(
                source_url="https://radio.example/clicked",
            ),
        ),
        _station_url=Mock(return_value="https://radio.example/clicked"),
    )

    assert (
        window.MainWindow._is_station_recording(
            harness,
            station,
        )
        is True
    )


def test_gtk_station_recording_state_rejects_different_active_session() -> None:
    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        recording_manager=SimpleNamespace(
            active_session=SimpleNamespace(
                source_url="https://radio.example/other",
            ),
        ),
        _station_url=Mock(return_value="https://radio.example/clicked"),
    )

    assert (
        window.MainWindow._is_station_recording(
            harness,
            station,
        )
        is False
    )


def test_gtk_station_recording_state_is_false_without_active_session() -> None:
    station = {
        "name": "Clicked FM",
        "url_resolved": "https://radio.example/clicked",
    }

    harness = SimpleNamespace(
        recording_manager=SimpleNamespace(active_session=None),
        _station_url=Mock(return_value="https://radio.example/clicked"),
    )

    assert (
        window.MainWindow._is_station_recording(
            harness,
            station,
        )
        is False
    )


def test_gtk_context_stop_recording_callback_does_not_change_selection() -> None:
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
        stop_recording=Mock(),
    )

    window.MainWindow.on_context_stop_recording_clicked(
        harness,
        Mock(),
        clicked_station,
    )

    harness.stop_recording.assert_called_once_with()
    assert harness.selected_station is selected_station


def test_gtk_context_menu_shows_record_session_when_no_recording_is_active(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
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
        "homepage": "",
    }

    harness = SimpleNamespace(
        recording_available=True,
        recording_manager=SimpleNamespace(active_session=None),
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        on_context_record_clicked=Mock(),
        on_context_stop_recording_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _station_url=Mock(return_value="https://radio.example/clicked"),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert "Record session" in labels

    record_button = next(
        button
        for button in FakePopover.last_created.child.children
        if button.label == "Record session"
    )
    assert record_button.connections == [
        (
            "clicked",
            harness.on_context_record_clicked,
            (station,),
        )
    ]


def test_gtk_context_menu_shows_stop_recording_for_active_station(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label
            self.connections = []

        def connect(self, signal, callback, *args) -> None:
            self.connections.append((signal, callback, args))

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
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
        "homepage": "",
    }

    harness = SimpleNamespace(
        recording_available=True,
        recording_manager=SimpleNamespace(
            active_session=SimpleNamespace(
                source_url="https://radio.example/clicked",
            ),
        ),
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        on_context_record_clicked=Mock(),
        on_context_stop_recording_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _station_url=Mock(return_value="https://radio.example/clicked"),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert "Stop recording" in labels
    assert "Record session" not in labels

    stop_button = next(
        button
        for button in FakePopover.last_created.child.children
        if button.label == "Stop recording"
    )
    assert stop_button.connections == [
        (
            "clicked",
            harness.on_context_stop_recording_clicked,
            (station,),
        )
    ]


def test_gtk_context_menu_hides_recording_action_for_different_active_station(  # noqa: C901 - reviewed ceiling 16; see docs/complexity-baseline.json
    monkeypatch,
) -> None:
    class FakeRectangle:
        def __init__(self, *_args) -> None:
            pass

    class FakeButton:
        def __init__(self, *, label: str) -> None:
            self.label = label

        def connect(self, *_args) -> None:
            pass

    class FakeBox:
        def __init__(self, **_kwargs) -> None:
            self.children = []

        def set_margin_top(self, _value) -> None:
            pass

        def set_margin_bottom(self, _value) -> None:
            pass

        def set_margin_start(self, _value) -> None:
            pass

        def set_margin_end(self, _value) -> None:
            pass

        def append(self, child) -> None:
            self.children.append(child)

    class FakePopover:
        last_created = None

        def __init__(self) -> None:
            type(self).last_created = self
            self.child = None

        def set_parent(self, _row) -> None:
            pass

        def set_child(self, child) -> None:
            self.child = child

        def connect(self, _signal, _callback) -> None:
            pass

        def set_pointing_to(self, _rectangle) -> None:
            pass

        def popup(self) -> None:
            pass

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=FakePopover,
            Box=FakeBox,
            Button=FakeButton,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
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
        "homepage": "",
    }

    harness = SimpleNamespace(
        recording_available=True,
        recording_manager=SimpleNamespace(
            active_session=SimpleNamespace(
                source_url="https://radio.example/other",
            ),
        ),
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        on_context_record_clicked=Mock(),
        on_context_stop_recording_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _station_url=Mock(return_value="https://radio.example/clicked"),
        _on_station_context_menu_closed=Mock(),
    )

    window.MainWindow._show_station_context_menu(
        harness,
        object(),
        station,
        1.0,
        2.0,
    )

    labels = [button.label for button in FakePopover.last_created.child.children]

    assert "Record session" not in labels
    assert "Stop recording" not in labels


def test_gtk_ripping_context_start_callback_targets_clicked_station() -> None:
    selected = {"name": "Selected FM", "url": "https://example.com/selected"}
    clicked = {"name": "Clicked FM", "url_resolved": "https://example.com/clicked"}
    harness = SimpleNamespace(
        selected_station=selected,
        start_station_ripping=Mock(),
        stop_station_ripping=Mock(),
    )

    window.MainWindow.on_context_rip_clicked(harness, Mock(), clicked)

    harness.start_station_ripping.assert_called_once_with(clicked)
    harness.stop_station_ripping.assert_not_called()
    assert harness.selected_station is selected


def test_gtk_ripping_context_stop_callback_targets_clicked_station() -> None:
    selected = {"name": "Selected FM", "url": "https://example.com/selected"}
    clicked = {"name": "Clicked FM", "url_resolved": "https://example.com/clicked"}
    harness = SimpleNamespace(
        selected_station=selected,
        start_station_ripping=Mock(),
        stop_station_ripping=Mock(),
    )

    window.MainWindow.on_context_stop_ripping_clicked(harness, Mock(), clicked)

    harness.stop_station_ripping.assert_called_once_with(clicked)
    harness.start_station_ripping.assert_not_called()
    assert harness.selected_station is selected


def _ripping_menu_harness(
    monkeypatch, tmp_path, *, state=None, available=True, workers_finished=True
):
    from fluxtuner.core.ripping import RippingAvailability, RippingRequest
    from fluxtuner.core.ripping_service import RippingService, RippingSnapshot

    menu_box = Mock()
    menu_box.children = []
    menu_box.append.side_effect = menu_box.children.append

    def button(*, label):
        result = SimpleNamespace(label=label, connections=[])
        result.connect = lambda signal, callback, *args: result.connections.append(
            (signal, callback, args)
        )
        return result

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            Popover=Mock(),
            Box=Mock(return_value=menu_box),
            Button=button,
            Orientation=SimpleNamespace(VERTICAL=object()),
        ),
    )
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Rectangle=Mock()),
        raising=False,
    )
    station = {
        "name": "Clicked FM",
        "url_resolved": "https://example.com/clicked",
        "homepage": "",
    }
    request = RippingRequest(
        station_name="Original name",
        source_url=station["url_resolved"],
        output_directory=tmp_path / "tracks",
        profile_id=7,
        profile_name="Focus",
    )
    service = Mock(spec=RippingService)
    service.wait.return_value = workers_finished
    service.snapshot.return_value = (
        None if state is None else RippingSnapshot(job_id=1, request=request, state=state)
    )
    harness = SimpleNamespace(
        selected_station={"name": "Other station"},
        ripping_service=service,
        ripping_availability=RippingAvailability(available),
        _ripping_shutting_down=False,
        _ripping_profile_context=Mock(return_value=(7, "Focus")),
        status_label=Mock(),
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
        on_context_add_playlist_clicked=Mock(),
        on_context_remove_playlist_clicked=Mock(),
        on_context_remove_favorite_clicked=Mock(),
        on_context_open_homepage_clicked=Mock(),
        on_context_rip_clicked=Mock(),
        on_context_stop_ripping_clicked=Mock(),
        copy_station_url=Mock(),
        copy_station_name=Mock(),
        _is_favorite_station=Mock(return_value=False),
        _on_station_context_menu_closed=Mock(),
    )
    return harness, station, menu_box


@pytest.mark.parametrize(
    ("state", "available", "workers_finished", "expected"),
    [
        (None, True, True, "Rip tracks"),
        (None, False, True, None),
        ("starting", True, False, "Stop ripping"),
        ("running", False, False, "Stop ripping"),
        ("stopping", True, False, None),
        ("stopped", True, False, None),
        ("failed", True, True, "Rip tracks"),
        ("completed", True, True, "Rip tracks"),
    ],
)
def test_gtk_ripping_menu_wiring_projects_policy(
    monkeypatch, tmp_path, state, available, workers_finished, expected
) -> None:
    harness, station, menu = _ripping_menu_harness(
        monkeypatch,
        tmp_path,
        state=state,
        available=available,
        workers_finished=workers_finished,
    )
    selection = harness.selected_station

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    actions = [button for button in menu.children if button.label in ("Rip tracks", "Stop ripping")]
    assert [button.label for button in actions] == ([] if expected is None else [expected])
    if actions:
        callback = (
            harness.on_context_rip_clicked
            if expected == "Rip tracks"
            else harness.on_context_stop_ripping_clicked
        )
        assert actions[0].connections == [("clicked", callback, (station,))]
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.ripping_service.start.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.status_label.set_text.assert_not_called()
    assert harness.selected_station is selection


@pytest.mark.parametrize("mismatch", ["profile", "station"])
def test_gtk_ripping_menu_wiring_hides_other_operation(monkeypatch, tmp_path, mismatch) -> None:
    harness, station, menu = _ripping_menu_harness(
        monkeypatch, tmp_path, state="running", workers_finished=False
    )
    if mismatch == "profile":
        harness._ripping_profile_context.return_value = (8, "Other")
    else:
        station["url_resolved"] = "https://example.com/other"

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    assert not {"Rip tracks", "Stop ripping"} & {button.label for button in menu.children}
    harness.ripping_service.wait.assert_called_once_with(timeout=0)


def test_gtk_ripping_menu_wiring_skips_shutdown(monkeypatch, tmp_path) -> None:
    harness, station, menu = _ripping_menu_harness(monkeypatch, tmp_path)
    harness._ripping_shutting_down = True

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    assert not {"Rip tracks", "Stop ripping"} & {button.label for button in menu.children}
    harness._ripping_profile_context.assert_not_called()
    harness.ripping_service.wait.assert_not_called()


def test_gtk_ripping_menu_wiring_contains_profile_failure(monkeypatch, tmp_path) -> None:
    harness, station, menu = _ripping_menu_harness(monkeypatch, tmp_path)
    harness._ripping_profile_context.side_effect = RuntimeError("Profile unavailable")

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    assert not {"Rip tracks", "Stop ripping"} & {button.label for button in menu.children}
    assert "Copy station name" in {button.label for button in menu.children}
    harness.status_label.set_text.assert_called_once_with(
        "Could not check ripping actions: Profile unavailable"
    )


def test_gtk_ripping_menu_wiring_reads_snapshot_after_wait(monkeypatch, tmp_path) -> None:
    from dataclasses import replace

    harness, station, menu = _ripping_menu_harness(monkeypatch, tmp_path, state="running")
    initial = harness.ripping_service.snapshot.return_value

    def finish(*, timeout):
        assert timeout == 0
        harness.ripping_service.snapshot.return_value = replace(initial, state="stopped")
        return True

    harness.ripping_service.wait.side_effect = finish

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    labels = {button.label for button in menu.children}
    assert "Rip tracks" in labels
    assert "Stop ripping" not in labels


def test_playlist_context_callback_targets_clicked_station() -> None:
    selected = {"name": "Selected", "url": "https://example.com/selected"}
    clicked = {"name": "Clicked", "url": "https://example.com/clicked"}
    harness = SimpleNamespace(selected_station=selected, open_playlist_picker=Mock())

    window.MainWindow.on_context_add_playlist_clicked(harness, Mock(), clicked)

    harness.open_playlist_picker.assert_called_once_with(clicked)
    assert harness.selected_station is selected


def test_playlist_remove_callback_targets_clicked_station_and_playlist() -> None:
    selected = {"name": "Selected"}
    clicked = {"name": "Clicked", "url": "https://example.com/clicked"}
    harness = SimpleNamespace(selected_station=selected, remove_station_from_saved_playlist=Mock())

    window.MainWindow.on_context_remove_playlist_clicked(harness, Mock(), clicked, "Morning")

    harness.remove_station_from_saved_playlist.assert_called_once_with(clicked, "Morning")
    assert harness.selected_station is selected


def test_playlist_context_menu_binds_active_playlist(monkeypatch, tmp_path) -> None:
    from fluxtuner.gui.gtk_view_state import ViewState

    harness, station, menu = _ripping_menu_harness(monkeypatch, tmp_path)
    harness._view_state = ViewState()
    harness._view_state.show_playlist("Morning")

    window.MainWindow._show_station_context_menu(harness, object(), station, 1.0, 2.0)

    add = next(button for button in menu.children if button.label == "Add to playlist…")
    remove = next(button for button in menu.children if button.label == "Remove from playlist")
    assert add.connections == [("clicked", harness.on_context_add_playlist_clicked, (station,))]
    assert remove.connections == [
        ("clicked", harness.on_context_remove_playlist_clicked, (station, "Morning"))
    ]


def _playlist_dialog_harness(monkeypatch):
    from fluxtuner.gui.gtk_view_state import ViewState

    picker = SimpleNamespace(names=("Morning",), add=Mock(return_value=True))
    capture = Mock(return_value=picker)
    monkeypatch.setattr(window, "create_playlist_picker", capture)
    dropdown = Mock()
    dropdown.get_selected.return_value = 0
    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            ResponseType=SimpleNamespace(ACCEPT=1, CANCEL=0),
            DropDown=SimpleNamespace(new_from_strings=Mock(return_value=dropdown)),
        ),
    )
    dialog, content = Mock(), Mock()
    label = Mock()
    selection = {"name": "Selected", "url": "https://example.com/selected"}
    harness = SimpleNamespace(
        _playlist_profile_id=Mock(return_value=7),
        _make_playlist_dialog=Mock(return_value=(dialog, content)),
        _make_value_label=Mock(return_value=label),
        _view_state=ViewState(),
        _refresh_favorite_cache=Mock(),
        _refresh_saved_playlists=Mock(),
        _render_results=Mock(),
        _show_saved_playlist=Mock(),
        selected_station=selection,
        status_label=Mock(),
    )
    clicked = {"name": "Clicked", "url": "https://example.com/clicked"}
    window.MainWindow.open_playlist_picker(harness, clicked)
    callback = dialog.connect.call_args.args[1]
    capture.assert_called_once_with(clicked, profile_id=7)
    return harness, picker, dialog, label, callback


def test_playlist_picker_cancel_does_not_write_or_change_selection(monkeypatch) -> None:
    harness, picker, dialog, _label, respond = _playlist_dialog_harness(monkeypatch)
    selection = harness.selected_station

    respond(dialog, 0)

    picker.add.assert_not_called()
    dialog.destroy.assert_called_once_with()
    harness._render_results.assert_not_called()
    assert harness.selected_station is selection


def test_playlist_picker_confirm_preserves_selection(monkeypatch) -> None:
    harness, picker, dialog, _label, respond = _playlist_dialog_harness(monkeypatch)
    selection = harness.selected_station

    respond(dialog, 1)

    picker.add.assert_called_once_with("Morning")
    dialog.destroy.assert_called_once_with()
    harness._refresh_favorite_cache.assert_called_once_with()
    harness._refresh_saved_playlists.assert_called_once_with()
    assert harness.selected_station is selection


def test_playlist_picker_rejects_profile_change_before_write(monkeypatch) -> None:
    harness, picker, dialog, label, respond = _playlist_dialog_harness(monkeypatch)
    harness._playlist_profile_id.return_value = 8

    respond(dialog, 1)

    picker.add.assert_not_called()
    dialog.destroy.assert_not_called()
    label.set_text.assert_called_once_with("The profile changed. Reopen this dialog.")


def test_playlist_picker_storage_error_keeps_dialog_open(monkeypatch) -> None:
    harness, picker, dialog, label, respond = _playlist_dialog_harness(monkeypatch)
    picker.add.side_effect = OSError("Storage unavailable")

    respond(dialog, 1)

    dialog.destroy.assert_not_called()
    label.set_text.assert_called_once_with("Storage unavailable")
    harness._render_results.assert_not_called()
