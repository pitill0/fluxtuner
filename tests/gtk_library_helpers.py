"""Bind existing GTK contract doubles to the extracted library boundary."""

from __future__ import annotations

from types import SimpleNamespace

from fluxtuner.gui.gtk_library import LibraryController


def bind_library_harness(harness):
    """Keep contract assertions on their original collaborators after relocation."""
    if "_controller" not in vars(harness):
        harness._controller = LibraryController(
            profile_name=lambda: getattr(harness, "profile_name", None)
        )
    controller = harness._controller
    bindings = {
        "_playlist_profile_id": controller.playlist_profile_id,
        "_refresh_favorite_cache": controller.refresh_favorite_cache,
        "_is_favorite_station": controller.is_favorite_station,
        "_favorites_matching_favorite_tag": controller.favorites_matching_favorite_tag,
        "_all_favorite_playlist_tags": controller.all_favorite_playlist_tags,
        "_parent": harness,
    }
    if "status_label" in vars(harness):
        bindings["_set_status"] = harness.status_label.set_text
    if "_search_lifecycle" in vars(harness):
        bindings["_invalidate_search"] = harness._search_lifecycle.invalidate

    def close_menu():
        popover = getattr(harness, "application_menu_popover", None)
        if popover is not None:
            popover.popdown()

    bindings["_close_menu"] = close_menu
    for name, value in bindings.items():
        if name not in vars(harness):
            setattr(harness, name, value)
    return harness


def bind_library_menu(harness):
    """Supply the explicit library callback owner to station/menu doubles."""
    names = (
        "on_context_add_favorite_clicked",
        "on_context_remove_favorite_clicked",
        "on_context_add_playlist_clicked",
        "on_context_remove_playlist_clicked",
        "on_import_stations_clicked",
        "on_import_stations_url_clicked",
        "on_add_custom_station_clicked",
    )
    if "_library" not in vars(harness):
        harness._library = SimpleNamespace(
            **{name: getattr(harness, name) for name in names if hasattr(harness, name)}
        )
    return harness
