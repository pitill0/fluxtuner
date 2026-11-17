"""Nonblocking, bounded GTK artwork presentation backed by the shared cache."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from fluxtuner.core.artwork_service import ArtworkService  # noqa: E402

_MAX_PENDING = 128


def station_artwork_url(station: dict[str, Any] | None) -> str:
    """Use only the independently validated favicon field, not the stream URL."""
    value = station.get("favicon") if isinstance(station, dict) else None
    return value.strip() if isinstance(value, str) else ""


class GtkArtwork:
    """Deliver optional artwork on GTK's loop without waiting for network I/O."""

    def __init__(
        self,
        service: ArtworkService | None = None,
        *,
        dispatch: Callable[..., object] | None = None,
    ) -> None:
        self._service = service if service is not None else ArtworkService()
        self._dispatch = dispatch if dispatch is not None else GLib.idle_add
        self._pending: queue.Queue[tuple[str, str, int, Gtk.Picture]] = queue.Queue(
            maxsize=_MAX_PENDING
        )
        self._generations = {"rows": 0, "player": 0}
        self._closed = threading.Event()
        self._worker = threading.Thread(target=self._run, name="fluxtuner-gtk-artwork", daemon=True)
        self._worker.start()

    def invalidate(self, scope: str) -> None:
        self._generations[scope] += 1

    def close(self) -> None:
        self._closed.set()
        self.invalidate("rows")
        self.invalidate("player")

    def widget(self, station: dict[str, Any], *, scope: str, size: int) -> Gtk.Box:
        """Return an immediate fallback, optionally replaced with a cached image."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_size_request(size, size)
        box.add_css_class("station-artwork")
        name = station.get("name", "")
        initial = str(name).strip()[:1].upper() or "♪"
        placeholder = Gtk.Label(label=initial)
        placeholder.set_size_request(size, size)
        placeholder.add_css_class("station-artwork-fallback")
        box.append(placeholder)
        picture = Gtk.Picture()
        picture.set_size_request(size, size)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_visible(False)
        box.append(picture)

        url = station_artwork_url(station)
        if url and not self._closed.is_set():
            task = (url, scope, self._generations[scope], picture)
            with suppress(queue.Full):
                self._pending.put_nowait(task)
        return box

    def _run(self) -> None:
        while not self._closed.is_set():
            try:
                url, scope, generation, picture = self._pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._closed.is_set() or generation != self._generations[scope]:
                continue
            result = self._service.get(url)
            if result is not None and not self._closed.is_set():
                self._dispatch(self._deliver, scope, generation, picture, result.data)

    def _deliver(self, scope: str, generation: int, picture: Gtk.Picture, data: bytes) -> bool:
        if self._closed.is_set() or generation != self._generations[scope]:
            return False
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk

        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        except (GLib.Error, ValueError, TypeError):
            return False
        parent = picture.get_parent()
        if parent is None:
            return False
        placeholder = parent.get_first_child()
        picture.set_paintable(texture)
        if placeholder is not None:
            placeholder.set_visible(False)
        picture.set_visible(True)
        return False
