# SPDX-License-Identifier: MIT

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("gi", reason="PyGObject is required for GTK tests")

from fluxtuner.core.search_service import SearchResult
from fluxtuner.gui import window
from fluxtuner.gui.gtk_search import SearchLifecycle


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, "radio-browser"),
        (1, "local"),
        (2, "all"),
    ],
)
def test_gtk_source_selector_maps_all_choices(index, expected):
    harness = SimpleNamespace(search_source_dropdown=SimpleNamespace(get_selected=lambda: index))

    assert window.MainWindow._selected_search_source(harness) == expected


def test_gtk_source_selector_rejects_invalid_index():
    harness = SimpleNamespace(search_source_dropdown=SimpleNamespace(get_selected=lambda: 99))

    with pytest.raises(ValueError, match="Unknown station discovery source"):
        window.MainWindow._selected_search_source(harness)


def test_gtk_source_change_invalidates_results_and_selection():
    lifecycle = SearchLifecycle()
    old_generation = lifecycle.begin()
    view_state = SimpleNamespace(show_search=Mock())

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=view_state,
        last_search_results=[{"name": "Old station"}],
        stations=[{"name": "Old station"}],
        selected_station={"name": "Old station"},
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    window.MainWindow._on_search_source_changed(harness, Mock(), Mock())

    assert not lifecycle.is_current(old_generation)
    assert harness.last_search_results == []
    assert harness.stations == []
    assert harness.selected_station is None
    view_state.show_search.assert_called_once_with()
    harness._render_results.assert_called_once_with()
    harness._update_playlist_status.assert_called_once_with()
    harness._set_view_status.assert_called_once_with("Search results", 0)


@pytest.mark.parametrize("source", ["local", "all"])
def test_gtk_local_and_combined_dispatch_to_worker_adapter(monkeypatch, source):
    idle_add = Mock()
    monkeypatch.setattr(window.GLib, "idle_add", idle_add, raising=False)

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(window.threading, "Thread", ImmediateThread)

    adapter = Mock(return_value=SearchResult(stations=[{"name": "Local radio"}]))
    monkeypatch.setattr(window, "search_desktop_stations", adapter)

    service_search = Mock(side_effect=AssertionError("Wrong search backend"))
    lifecycle = SearchLifecycle()
    capabilities = object()

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _selected_search_source=lambda: source,
        profile_name="default",
        player_capabilities=capabilities,
        search_entry=SimpleNamespace(get_text=lambda: "  rock  "),
        country_entry=SimpleNamespace(get_text=lambda: "  Spain  "),
        min_bitrate_entry=SimpleNamespace(get_text=lambda: "128"),
        status_label=Mock(),
        search_service=SimpleNamespace(search=service_search),
        _search_failed=Mock(),
        _search_finished=Mock(),
    )

    window.MainWindow.on_search_clicked(harness, Mock())

    adapter.assert_called_once()
    args, kwargs = adapter.call_args
    assert args[0].source == source
    assert args[0].query == "rock"
    assert args[0].country == "Spain"
    assert args[0].min_bitrate == 128
    assert kwargs["profile_name"] == "default"
    assert kwargs["capabilities"] is capabilities
    service_search.assert_not_called()
    idle_add.assert_called_once_with(
        harness._search_finished,
        lifecycle.generation,
        [{"name": "Local radio"}],
    )


def test_gtk_stale_result_cannot_replace_new_source_view():
    lifecycle = SearchLifecycle()
    stale_generation = lifecycle.begin()
    lifecycle.invalidate()

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=SimpleNamespace(show_search=Mock()),
        last_search_results=[],
        stations=[],
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    accepted = window.MainWindow._search_finished(
        harness, stale_generation, [{"name": "Stale station"}]
    )

    assert accepted is False
    assert harness.stations == []
    assert harness.last_search_results == []
    harness._render_results.assert_not_called()
    harness._view_state.show_search.assert_not_called()


def test_gtk_source_change_preserves_active_playback():
    playing = {"name": "Currently playing", "url": "https://example.org/live"}
    player = Mock()
    lifecycle = SearchLifecycle()
    old_generation = lifecycle.begin()

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=SimpleNamespace(show_search=Mock()),
        last_search_results=[{"name": "Previous result"}],
        stations=[{"name": "Previous result"}],
        selected_station={"name": "Previous result"},
        current_station=playing,
        player=player,
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    window.MainWindow._on_search_source_changed(harness, Mock(), Mock())

    assert not lifecycle.is_current(old_generation)
    assert harness.last_search_results == []
    assert harness.stations == []
    assert harness.selected_station is None
    assert harness.current_station is playing
    player.stop.assert_not_called()
