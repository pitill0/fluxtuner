#!/usr/bin/env bash
set -euo pipefail

FILE="fluxtuner/gui/window.py"

if [ ! -f "$FILE" ]; then
  echo "Run from repo root"
  exit 1
fi

python - <<'PY'
from pathlib import Path

p = Path("fluxtuner/gui/window.py")
t = p.read_text()

t = t.replace(
    'playback_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)\n'
    '        playback_bar.set_hexpand(True)\n'
    '        playback_bar.set_halign(Gtk.Align.CENTER)\n',
    'playback_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)\n'
    '        playback_bar.set_hexpand(True)\n'
    '        playback_bar.set_halign(Gtk.Align.CENTER)\n'
    '        playback_bar.set_valign(Gtk.Align.CENTER)\n'
    '        playback_bar.set_homogeneous(False)\n',
)

t = t.replace(
    'self.stop_button = Gtk.Button(label="■")\n'
    '        self.stop_button.set_tooltip_text("Stop playback")\n',
    'self.stop_button = Gtk.Button(label="■")\n'
    '        self.stop_button.set_size_request(64, -1)\n'
    '        self.stop_button.set_hexpand(False)\n'
    '        self.stop_button.set_tooltip_text("Stop playback")\n',
)

t = t.replace(
    'self.pause_button = Gtk.Button(label="⏯")\n'
    '        self.pause_button.set_tooltip_text("Pause / resume")\n',
    'self.pause_button = Gtk.Button(label="⏯")\n'
    '        self.pause_button.set_size_request(64, -1)\n'
    '        self.pause_button.set_hexpand(False)\n'
    '        self.pause_button.set_tooltip_text("Pause / resume")\n',
)

t = t.replace(
    'self.play_button = Gtk.Button(label="▶")\n'
    '        self.play_button.set_tooltip_text("Play selected station")\n',
    'self.play_button = Gtk.Button(label="▶")\n'
    '        self.play_button.set_size_request(84, -1)\n'
    '        self.play_button.set_hexpand(False)\n'
    '        self.play_button.set_tooltip_text("Play selected station")\n',
)

t = t.replace(
    'self.mute_button = Gtk.Button(label="")\n'
    '        self.mute_button.set_tooltip_text("Mute / unmute")\n',
    'self.mute_button = Gtk.Button(label="🔊")\n'
    '        self.mute_button.set_size_request(64, -1)\n'
    '        self.mute_button.set_hexpand(False)\n'
    '        self.mute_button.set_tooltip_text("Mute / unmute")\n',
)

t = t.replace('self.volume_scale.set_size_request(160, -1)\n', 'self.volume_scale.set_size_request(180, -1)\n')
t = t.replace('self.mute_button.set_label("" if muted else "")\n', 'self.mute_button.set_label("🔇" if muted else "🔊")\n')

p.write_text(t)
PY

python -m compileall fluxtuner >/dev/null
echo "Stable playback bar layout patch applied."
