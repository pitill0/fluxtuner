#!/usr/bin/env bash
set -euo pipefail

FILE="fluxtuner/gui/window.py"

if [ ! -f "$FILE" ]; then
  echo "Run from repo root"
  exit 1
fi

python - <<'PY'
from pathlib import Path
import re

p = Path("fluxtuner/gui/window.py")
t = p.read_text()

while "self.self." in t:
    t = t.replace("self.self.", "self.")

t = re.sub(
    r'\n\s*self\.pause_button\s*=\s*Gtk\.Button\(label="[^"]*"\)\n'
    r'(?:\s*self\.pause_button\.[^\n]*\n)*'
    r'\s*playback_bar\.append\(self\.pause_button\)\n',
    '\n',
    t,
)

t = re.sub(
    r'\n\s*self\.stop_button\s*=\s*Gtk\.Button\(label="[^"]*"\)\n'
    r'(?:\s*self\.stop_button\.[^\n]*\n)*'
    r'\s*playback_bar\.append\(self\.stop_button\)\n',
    '\n',
    t,
)

t = re.sub(r'self\.play_button\s*=\s*Gtk\.Button\(label="[^"]*"\)', 'self.play_button = Gtk.Button(label="▶ Play")', t, count=1)

if "self.play_button.set_size_request" not in t:
    t = t.replace(
        'self.play_button = Gtk.Button(label="▶ Play")\n',
        'self.play_button = Gtk.Button(label="▶ Play")\n'
        '        self.play_button.set_size_request(112, -1)\n'
        '        self.play_button.set_hexpand(False)\n',
        1,
    )
else:
    t = re.sub(r'self\.play_button\.set_size_request\([^)]*\)', 'self.play_button.set_size_request(112, -1)', t, count=1)

t = t.replace('self.play_button.set_tooltip_text("Play selected station")', 'self.play_button.set_tooltip_text("Play selected station / stop playback")')

on_play_re = re.compile(
    r'    def on_play_clicked\(self, _button: Gtk\.Button\) -> None:\n'
    r'(?:        .*\n)+?'
    r'(?=\n    def |\Z)',
    re.MULTILINE,
)
on_play_new = (
    '    def on_play_clicked(self, _button: Gtk.Button) -> None:\n'
    '        if self._has_active_playback():\n'
    '            self.on_stop_clicked(_button)\n'
    '            return\n'
    '        self.play_selected_station()\n'
)
t, count = on_play_re.subn(on_play_new, t)
if count != 1:
    raise SystemExit("Could not replace on_play_clicked cleanly.")

if 'self.status_label.set_text("Buffering…")' not in t:
    t = t.replace(
        '        try:\n            self.player.play(url)\n',
        '        try:\n'
        '            self.status_label.set_text("Buffering…")\n'
        '            self.player.play(url)\n',
        1,
    )

if 'row.add_css_class("suggested-action")' not in t:
    t = t.replace(
        '            row = Gtk.ListBoxRow()\n'
        '            row.station = station  # type: ignore[attr-defined]\n',
        '            row = Gtk.ListBoxRow()\n'
        '            if self._is_current_station(station):\n'
        '                row.add_css_class("suggested-action")\n'
        '            row.station = station  # type: ignore[attr-defined]\n',
    )

lines = t.splitlines()
start = None
for i, line in enumerate(lines):
    if line.startswith("    def _update_play_pause_button(self)"):
        start = i
        break

if start is None:
    raise SystemExit("Could not find _update_play_pause_button.")

end = len(lines)
for i in range(start + 1, len(lines)):
    if lines[i].startswith("    def ") and not lines[i].startswith("    def _update_play_pause_button"):
        end = i
        break

replacement_lines = [
    "    def _update_play_pause_button(self) -> None:",
    "        if not hasattr(self, \"play_button\"):",
    "            return",
    "        if self._has_active_playback():",
    "            self.play_button.set_label(\"■ Stop\")",
    "            self.play_button.set_tooltip_text(\"Stop playback\")",
    "        else:",
    "            self.play_button.set_label(\"▶ Play\")",
    "            self.play_button.set_tooltip_text(\"Play selected station\")",
    "",
]
lines[start:end] = replacement_lines
t = "\n".join(lines) + "\n"

if 'self._update_play_pause_button()\n        self.status_label.set_text("Playing")' not in t:
    t = t.replace(
        '        self.status_label.set_text("Playing")\n',
        '        self._update_play_pause_button()\n'
        '        self.status_label.set_text("Playing")\n',
        1,
    )

stop_start = t.find("    def stop_playback(self)")
if stop_start != -1:
    next_def = t.find("\n    def ", stop_start + 1)
    stop_block = t[stop_start: next_def if next_def != -1 else len(t)]
    if "self._update_play_pause_button()" not in stop_block:
        t = t.replace(
            '            self._render_results()\n',
            '            self._update_play_pause_button()\n'
            '            self._render_results()\n',
            1,
        )

p.write_text(t)
PY

python -m compileall fluxtuner >/dev/null
echo "GUI UX v1 patch applied."
