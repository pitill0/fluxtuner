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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
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
        "Copy stream URL",
        "Copy station name",
    ]

    (
        play_button,
        favorite_button,
        copy_url_button,
        copy_name_button,
    ) = popover.child.children

    assert play_button.connections == [
        ("clicked", harness.on_context_play_clicked, (station,))
    ]
    assert favorite_button.connections == [
        (
            "clicked",
            harness.on_context_add_favorite_clicked,
            (station,),
        )
    ]
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
        on_context_play_clicked=lambda _button, target: target,
        on_context_add_favorite_clicked=lambda _button, target: target,
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
        on_context_play_clicked=Mock(),
        on_context_add_favorite_clicked=Mock(),
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
    harness.status_label.set_text.assert_called_once_with(
        "Added to favorites."
    )
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
    harness.status_label.set_text.assert_called_once_with(
        "Removed from favorites."
    )
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


def test_gtk_context_menu_shows_add_to_favorites_for_non_favorite_station(
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

    labels = [
        button.label
        for button in FakePopover.last_created.child.children
    ]

    assert labels == [
        "Play",
        "Add to favorites",
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


def test_gtk_context_menu_shows_remove_from_favorites_for_favorite_station(
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

    labels = [
        button.label
        for button in FakePopover.last_created.child.children
    ]

    assert labels == [
        "Play",
        "Remove from favorites",
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
