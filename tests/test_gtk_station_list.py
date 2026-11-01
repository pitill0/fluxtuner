"""Native selection contracts established before extracting station-list ownership."""

from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_gtk_library import library_store  # noqa: F401 - shared isolated database fixture.

from fluxtuner.players.capabilities import PlayerCapabilities


@pytest.fixture
def native_station_window(library_store, monkeypatch):  # noqa: F811
    from test_gtk_orchestration import window

    if not hasattr(window.Gtk, "init_check"):
        pytest.skip("Real GTK bindings are required for station-list signal contracts")
    from gi.repository import Gio, Gtk

    app = Gtk.Application(
        application_id=f"io.github.pitill0.Fluxtuner.StationListContract.u{uuid4().hex}",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)
    player = Mock()
    player.capabilities.return_value = PlayerCapabilities(general_purpose=True)
    player.supports_mute.return_value = False
    player.supports_volume.return_value = False
    player.supports_pause.return_value = False
    player.is_playing.return_value = False
    monkeypatch.setattr(window, "create_player", Mock(return_value=player))
    monkeypatch.setattr(window, "resolve_effective_profile_name", lambda: "default")
    monkeypatch.setattr(window.RippingController, "probe_availability", lambda self: None)
    actual = window.MainWindow(app)
    try:
        from fluxtuner.gui.gtk_station_context_menu import StationContextMenu
        from fluxtuner.gui.gtk_station_list import StationList

        assert isinstance(actual._station_list, StationList)
        assert isinstance(actual._station_context, StationContextMenu)
        assert actual.results_list is actual._station_list.results_list
        assert actual._station_context._view_state is actual._view_state
        yield actual
    finally:
        actual.shutdown()
        actual.destroy()


@pytest.mark.parametrize("scenario", ["selected", "current", "removed", "empty"])
def test_native_station_list_restores_selection_across_row_rebuilds(
    native_station_window, scenario
):
    actual = native_station_window
    first = {"name": "Alpha", "url": "https://radio.example/alpha"}
    second = {"name": "Beta", "url": "https://radio.example/beta"}
    actual.stations = [first, second]
    actual._render_results()
    actual.results_list.select_row(actual.results_list.get_row_at_index(1))
    assert actual.selected_station is second

    current = {"name": "Playing", "url": first["url"]}
    actual.current_station = current
    replacement_first = dict(first, name="Alpha refreshed")
    replacement_second = dict(second, name="Beta refreshed")
    actual.stations = [replacement_first, replacement_second]
    if scenario == "current":
        actual.selected_station = None
    elif scenario == "removed":
        actual.stations = [replacement_first]
    elif scenario == "empty":
        actual.stations = []
    before_cache = set(actual._library_controller.favorite_urls)

    actual._render_results()

    expected = {
        "selected": replacement_second,
        "current": replacement_first,
        "removed": replacement_first,
        "empty": None,
    }[scenario]
    assert actual.selected_station is expected
    selected_row = actual.results_list.get_selected_row()
    if expected is None:
        assert selected_row is None
        assert actual.results_list.get_row_at_index(0) is None
    else:
        assert selected_row.station is expected
    assert actual.current_station is current
    assert actual._library_controller.favorite_urls == before_cache


def test_native_row_gesture_plays_the_clicked_station_only_on_double_click(
    native_station_window, monkeypatch
):
    actual = native_station_window
    first = {"name": "Selected", "url": "https://radio.example/selected"}
    target = {"name": "Clicked", "url": "https://radio.example/clicked"}
    actual.stations = [first, target]
    actual._render_results()
    assert actual.selected_station is first
    play = Mock()
    monkeypatch.setattr(actual, "play_selected_station", play)
    row = actual.results_list.get_row_at_index(1)
    controllers = row.observe_controllers()
    gestures = [controllers.get_item(index) for index in range(controllers.get_n_items())]
    gesture = next(
        item for item in gestures if hasattr(item, "get_button") and item.get_button() == 0
    )

    gesture.emit("pressed", 1, 4.0, 8.0)
    play.assert_not_called()
    assert actual.selected_station is first

    gesture.emit("pressed", 2, 4.0, 8.0)
    play.assert_called_once_with()
    assert actual.selected_station is target
