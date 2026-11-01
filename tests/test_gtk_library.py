from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui.gtk_library import LibraryController, library_tags_text
from fluxtuner.gui.gtk_search import SearchLifecycle
from fluxtuner.gui.gtk_view_state import ViewState
from fluxtuner.players.capabilities import PlayerCapabilities


@pytest.fixture
def library_store(tmp_path, monkeypatch):
    from fluxtuner import config
    from fluxtuner.core import db, favorites, history, manual_playlists
    from fluxtuner.core.profiles import resolve_profile_id

    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    for module, current, legacy, name in (
        (favorites, "FAVORITES_FILE", "LEGACY_FAVORITES_FILE", "favorites.json"),
        (history, "HISTORY_FILE", "LEGACY_HISTORY_FILE", "history.json"),
        (manual_playlists, "PLAYLISTS_FILE", "LEGACY_PLAYLISTS_FILE", "playlists.json"),
    ):
        monkeypatch.setattr(module, current, tmp_path / name)
        monkeypatch.setattr(module, legacy, tmp_path / "legacy" / name)
    db.init_db()
    with db.connect() as conn:
        default_id = db.ensure_default_profile(conn)
        work_id = resolve_profile_id(conn, profile_name="work")
        conn.commit()
    return default_id, work_id


def test_library_cache_and_edits_follow_the_live_profile(library_store):
    profile = ["default"]
    controller = LibraryController(profile_name=lambda: profile[0])
    first = {"name": "Home", "url": "https://radio.example/home"}
    second = {"name": "Work", "url": "https://radio.example/work"}
    assert controller.add_favorite(first)
    controller.refresh_favorite_cache()
    assert controller.is_favorite_station(first)

    profile[0] = "work"
    assert controller.load_favorites() == []
    assert controller.add_favorite(second)
    assert controller.update_favorite(second["url"], custom_name="Office", favorite_tags=["focus"])
    controller.refresh_favorite_cache()
    assert controller.favorite_urls == {second["url"]}
    assert not controller.is_favorite_station(first)
    assert controller.load_favorites()[0]["custom_name"] == "Office"

    profile[0] = "default"
    controller.refresh_favorite_cache()
    assert controller.favorite_urls == {first["url"]}
    assert controller.load_favorites()[0]["name"] == "Home"


def test_library_playlist_membership_and_deletion_preserve_favorites(library_store):
    default_id, _ = library_store
    controller = LibraryController(profile_name=lambda: "default")
    station = {"name": "Selected", "url": "https://radio.example/selected"}
    assert controller.create_playlist("Morning", profile_id=default_id)
    picker = controller.create_playlist_picker(station, profile_id=default_id)
    assert picker.add("Morning")
    assert not picker.add("Morning")
    assert controller.remove_station_from_playlist("Morning", station, profile_id=default_id)
    assert controller.get_playlist_stations("Morning", profile_id=default_id) == []
    assert controller.load_favorites()[0]["url"] == station["url"]
    assert picker.add("Morning")
    assert controller.delete_playlist("Morning", profile_id=default_id)
    assert controller.get_playlist("Morning", profile_id=default_id) is None
    assert controller.load_favorites()[0]["url"] == station["url"]


def test_library_custom_station_commits_only_to_captured_profile(library_store):
    default_id, work_id = library_store
    controller = LibraryController(profile_name=lambda: "work")
    assert controller.add_custom_station(
        profile_id=work_id, name="Private FM", url="https://radio.example/private"
    )
    assert controller.playlist_profile_id() == work_id
    assert controller.load_favorites()[0]["name"] == "Private FM"
    from fluxtuner.core.favorites import load_favorites

    assert load_favorites(profile_id=default_id) == []


def _panel(controller):
    # Reuse the established headless import boundary; native runs keep real GTK.
    from test_gtk_orchestration import window

    from fluxtuner.gui.gtk_library_panel import LibraryPanel, LibraryViewPorts

    assert window.MainWindow is not None
    state = SimpleNamespace(stations=[], selected=None, current=None)
    lifecycle = SearchLifecycle()
    view_state = ViewState()
    panel = LibraryPanel(
        parent=Mock(),
        controller=controller,
        ports=LibraryViewPorts(
            get_stations=lambda: state.stations,
            set_stations=lambda stations: setattr(state, "stations", stations),
            get_selected=lambda: state.selected,
            set_selected=lambda station: setattr(state, "selected", station),
            get_current=lambda: state.current,
            get_capabilities=lambda: PlayerCapabilities(general_purpose=True),
        ),
        view_state=view_state,
        invalidate_search=lifecycle.invalidate,
        render_results=Mock(),
        play_selected=Mock(),
        update_now_playing=Mock(),
        set_status=Mock(),
        set_view_status=Mock(),
        make_value_label=Mock(),
        append_section_title=Mock(),
        close_menu=Mock(),
    )
    # Widget projection is separately covered by native composition and dialog tests.
    panel._refresh_saved_playlists = Mock()
    return panel, state, lifecycle, view_state


def test_library_panel_uses_one_live_selection_across_views(library_store):
    from fluxtuner.core.history import add_history

    controller = LibraryController(profile_name=lambda: "default")
    station = {"name": "Home", "url": "https://radio.example/home"}
    controller.add_favorite(station)
    add_history(station, profile_name="default")
    panel, state, lifecycle, view_state = _panel(controller)
    state.current = station
    state.selected = station
    pending = lifecycle.begin()

    assert panel._show_all_favorites() == 1
    assert not lifecycle.is_current(pending)
    assert view_state.current_view == "favorites"
    assert state.selected is None
    assert panel.stations is state.stations
    assert panel.current_station is state.current

    state.selected = state.stations[0]
    assert panel.selected_station is state.selected
    assert panel._show_history() == 1
    assert state.selected is None
    assert view_state.current_view == "history"
    assert state.current is station


def test_library_panel_removing_other_favorite_preserves_selected_identity(library_store):
    controller = LibraryController(profile_name=lambda: "default")
    first = {"name": "First", "url": "https://radio.example/first"}
    second = {"name": "Second", "url": "https://radio.example/second"}
    controller.add_favorite(first)
    controller.add_favorite(second)
    panel, state, _, _ = _panel(controller)
    panel._show_all_favorites()
    state.selected = next(item for item in state.stations if item["url"] == first["url"])

    assert panel.remove_station_from_favorites(second)

    assert len(state.stations) == 1
    assert state.selected is state.stations[0]
    assert state.selected["url"] == first["url"]
    assert controller.favorite_urls == {first["url"]}


def test_library_panel_saved_playlist_rejects_deleted_destination_without_view_mutation(
    library_store,
):
    default_id, _ = library_store
    controller = LibraryController(profile_name=lambda: "default")
    controller.create_playlist("Morning", profile_id=default_id)
    panel, state, lifecycle, view_state = _panel(controller)
    selection = {"name": "Selected", "url": "https://radio.example/selected"}
    state.selected = selection
    state.stations = [selection]
    token = lifecycle.begin()
    controller.delete_playlist("Morning", profile_id=default_id)

    panel._show_saved_playlist("Morning")

    assert state.selected is selection
    assert state.stations == [selection]
    assert view_state.current_view == "search"
    assert lifecycle.is_current(token)
    panel._render_results.assert_not_called()
    assert "no longer exists" in panel._set_status.call_args.args[0]


def test_native_window_composes_library_widgets_and_routes_live_actions(library_store, monkeypatch):
    from test_gtk_orchestration import window

    if not hasattr(window.Gtk, "init_check"):
        pytest.skip("Real GTK bindings are required for library widget composition")
    from gi.repository import Gio, Gtk

    from fluxtuner.gui import gtk_library_panel

    app = Gtk.Application(
        application_id="io.github.pitill0.Fluxtuner.LibraryContract",
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
        panel = actual._library
        assert isinstance(panel, gtk_library_panel.LibraryPanel)
        assert isinstance(panel.add_favorite_button, Gtk.Button)
        assert isinstance(panel.saved_playlists_box, Gtk.Box)
        assert not hasattr(actual, "favorite_name_entry")
        station = {"name": "Native FM", "url": "https://radio.example/native"}
        actual.selected_station = station
        panel.add_favorite_button.emit("clicked")
        assert actual._library_controller.is_favorite_station(station)
        panel.show_favorites_button.emit("clicked")
        assert actual._view_state.current_view == "favorites"
        assert len(actual.stations) == 1
        actual.selected_station = actual.stations[0]
        panel._update_favorite_buttons()
        panel.favorite_name_entry.set_text("Renamed")
        panel.edit_favorite_tags_entry.set_text("native, jazz")
        panel.save_favorite_button.emit("clicked")
        assert actual._library_controller.load_favorites()[0]["custom_name"] == "Renamed"
        row = actual.results_list.get_row_at_index(0)
        cells = []
        cell = row.get_child().get_first_child()
        while cell is not None:
            cells.append(cell)
            cell = cell.get_next_sibling()
        assert cells[3].get_text() == "jazz, native"
        actual.current_station = actual.stations[0]
        monkeypatch.setattr(actual, "_start_metadata_polling", Mock())
        actual.update_now_playing()
        assert actual.tags_detail_label.get_text() == "jazz, native"
        panel.show_history_button.emit("clicked")
        assert actual._view_state.current_view == "history"
    finally:
        actual.shutdown()
        actual.destroy()


@pytest.mark.parametrize(
    ("station", "expected"),
    [
        ({"favorite_tags": ["library-test"]}, "library-test"),
        (
            {"tags": "jazz, blues", "favorite_tags": ["library-test", "Jazz"]},
            "jazz, blues, library-test",
        ),
        ({"tags": [" ROCK ", "rock"], "favorite_tags": ["Rock", "focus"]}, "ROCK, focus"),
        ({"tags": "jazz"}, "jazz"),
        ({"favorite_tags": []}, ""),
        (None, ""),
    ],
)
def test_library_tags_display_both_sources_without_mutating_storage(station, expected):
    from copy import deepcopy

    before = deepcopy(station)
    assert library_tags_text(station, fallback="") == expected
    assert station == before


def test_library_tags_use_the_requested_empty_detail_fallback():
    assert library_tags_text(None) == "No tags"
    assert library_tags_text({}, fallback="—") == "—"


def test_now_playing_projects_personal_tags_as_well_as_stream_genres():
    from test_gtk_orchestration import window

    station = {"name": "Library Alpha", "tags": "jazz", "favorite_tags": ["library-test"]}
    harness = SimpleNamespace(
        current_station=station,
        _station_display_name=Mock(return_value="Library Alpha"),
        now_playing_label=Mock(),
        country_detail_label=Mock(),
        codec_detail_label=Mock(),
        bitrate_detail_label=Mock(),
        tags_detail_label=Mock(),
        _start_metadata_polling=Mock(),
    )

    window.MainWindow.update_now_playing(harness)

    harness.tags_detail_label.set_text.assert_called_once_with("jazz, library-test")
