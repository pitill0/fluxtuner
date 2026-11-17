"""GTK artwork worker and lifecycle contracts; no network requests are performed."""

from __future__ import annotations

import threading
from unittest.mock import Mock

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from fluxtuner.gui.gtk_artwork import GtkArtwork, station_artwork_url  # noqa: E402


def test_station_artwork_url_uses_only_favicon() -> None:
    assert station_artwork_url({"favicon": " https://station.example/logo.png "}) == (
        "https://station.example/logo.png"
    )
    assert station_artwork_url({"url": "https://station.example/stream"}) == ""
    assert station_artwork_url({"favicon": 123}) == ""
    assert station_artwork_url(None) == ""


def test_worker_drops_stale_rows_before_lookup() -> None:
    if not Gtk.is_initialized():
        pytest.skip("GTK display initialization is required")
    requested = threading.Event()
    service = Mock()
    service.get.side_effect = lambda _url: requested.set()
    pending: list[tuple[object, ...]] = []
    loader = GtkArtwork(service=service, dispatch=lambda *args: pending.append(args))
    try:
        row = loader.widget(
            {"name": "Radio", "favicon": "https://station.example/logo.png"},
            scope="rows",
            size=28,
        )
        assert row.get_first_child() is not None
        assert requested.wait(2)
        loader.invalidate("rows")
        loader.close()
        assert pending == []
    finally:
        loader.close()


def test_invalid_favicon_never_schedules_network() -> None:
    if not Gtk.is_initialized():
        pytest.skip("GTK display initialization is required")
    service = Mock()
    loader = GtkArtwork(service=service)
    try:
        loader.widget({"name": "No image", "favicon": ""}, scope="rows", size=28)
        loader.close()
        service.get.assert_not_called()
    finally:
        loader.close()
