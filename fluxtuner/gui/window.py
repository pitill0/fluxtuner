"""Minimal experimental GTK window for FluxTuner."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from fluxtuner.players import create_player

DEFAULT_TEST_STREAM = "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one"


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, player_name: str = "mpv") -> None:
        super().__init__(application=app)

        self.set_title("FluxTuner GUI")
        self.set_default_size(720, 420)

        self.player = create_player(player_name)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self.set_child(root)

        title = Gtk.Label(label="FluxTuner GUI")
        title.set_xalign(0)
        title.add_css_class("title-1")
        root.append(title)

        subtitle = Gtk.Label(label="Experimental desktop GUI scaffold")
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        root.append(subtitle)

        self.url_entry = Gtk.Entry()
        self.url_entry.set_text(DEFAULT_TEST_STREAM)
        self.url_entry.set_hexpand(True)
        root.append(self.url_entry)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(controls)

        play_button = Gtk.Button(label="Play")
        play_button.connect("clicked", self.on_play_clicked)
        controls.append(play_button)

        stop_button = Gtk.Button(label="Stop")
        stop_button.connect("clicked", self.on_stop_clicked)
        controls.append(stop_button)

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0)
        root.append(self.status_label)

    def on_play_clicked(self, _button: Gtk.Button) -> None:
        url = self.url_entry.get_text().strip()
        if not url:
            self.status_label.set_text("No stream URL provided")
            return

        self.player.play(url)
        self.status_label.set_text("Playing")

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self.player.stop()
        self.status_label.set_text("Stopped")
