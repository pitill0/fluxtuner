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

old_section_title = '''    def _append_section_title(self, container: Gtk.Box, text: str) -> None:
        title = Gtk.Label(label=text)
        title.set_xalign(0)
        title.add_css_class("heading")
        container.append(title)

'''

new_section_title = old_section_title + '''    def _make_value_label(self, text: str = "—", *, selectable: bool = False) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_wrap(True)
        label.set_selectable(selectable)
        label.add_css_class("dim-label")
        return label

    def _append_detail_row(self, container: Gtk.Box, title: str) -> Gtk.Label:
        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0)
        title_label.add_css_class("caption-heading")
        container.append(title_label)

        value_label = self._make_value_label()
        container.append(value_label)

        return value_label

'''

if "def _make_value_label" not in t:
    if old_section_title not in t:
        raise SystemExit("Could not find _append_section_title block.")
    t = t.replace(old_section_title, new_section_title, 1)

old_side_panel = '''    def _build_side_panel(self, content: Gtk.Box) -> None:
        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        side_panel.set_size_request(260, -1)
        side_panel.set_hexpand(False)
        side_panel.set_vexpand(True)
        content.append(side_panel)

        self._append_section_title(side_panel, "Now Playing")

        self.now_playing_label = Gtk.Label(label="Nothing playing")
        self.now_playing_label.set_xalign(0)
        self.now_playing_label.set_wrap(True)
        self.now_playing_label.set_selectable(True)
        side_panel.append(self.now_playing_label)

        self.data_usage_label = Gtk.Label(label="Data: 0.0 MB session · 0.0 MB today · 0.0 MB/h est.")
        self.data_usage_label.set_xalign(0)
        self.data_usage_label.set_wrap(True)
        self.data_usage_label.set_selectable(True)
        side_panel.append(self.data_usage_label)

        self.player_state_label = Gtk.Label(label="Player: stopped")
        self.player_state_label.set_xalign(0)
        self.player_state_label.set_wrap(True)
        self.player_state_label.set_selectable(True)
        side_panel.append(self.player_state_label)

        self._build_favorite_controls(side_panel)

        hint = Gtk.Label(label="Tip: select a station and use ▶/⏸ below, or double-click it.")
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        side_panel.append(hint)

'''

new_side_panel = '''    def _build_side_panel(self, content: Gtk.Box) -> None:
        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        side_panel.set_size_request(300, -1)
        side_panel.set_hexpand(False)
        side_panel.set_vexpand(True)
        content.append(side_panel)

        self._append_section_title(side_panel, "Now Playing")

        self.now_playing_label = Gtk.Label(label="Nothing playing")
        self.now_playing_label.set_xalign(0)
        self.now_playing_label.set_wrap(True)
        self.now_playing_label.set_selectable(True)
        self.now_playing_label.add_css_class("title-3")
        side_panel.append(self.now_playing_label)

        self._append_section_title(side_panel, "Station details")

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details_box.set_hexpand(True)
        side_panel.append(details_box)

        self.country_detail_label = self._append_detail_row(details_box, "Country")
        self.codec_detail_label = self._append_detail_row(details_box, "Codec")
        self.bitrate_detail_label = self._append_detail_row(details_box, "Bitrate")
        self.tags_detail_label = self._append_detail_row(details_box, "Tags")

        self._append_section_title(side_panel, "Data usage")

        self.data_usage_label = self._make_value_label(
            "0.0 MB session · 0.0 MB today · 0.0 MB/h est.",
            selectable=True,
        )
        side_panel.append(self.data_usage_label)

        self.player_state_label = self._make_value_label("Player: stopped", selectable=True)
        side_panel.append(self.player_state_label)

        self._build_favorite_controls(side_panel)

        hint = Gtk.Label(label="Tip: select a station and use ▶ Play below, or double-click it.")
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        side_panel.append(hint)

'''

if old_side_panel not in t:
    raise SystemExit("Could not find exact _build_side_panel block from your pasted file.")
t = t.replace(old_side_panel, new_side_panel, 1)

lines = t.splitlines()
start = None
for i, line in enumerate(lines):
    if line.startswith("    def update_now_playing(self)"):
        start = i
        break

if start is None:
    raise SystemExit("Could not find update_now_playing.")

end = len(lines)
for i in range(start + 1, len(lines)):
    if lines[i].startswith("    def ") and not lines[i].startswith("    def update_now_playing"):
        end = i
        break

replacement = [
    "    def update_now_playing(self) -> None:",
    "        if not self.current_station:",
    '            self.now_playing_label.set_text("Nothing playing")',
    '            if hasattr(self, "country_detail_label"):',
    '                self.country_detail_label.set_text("—")',
    '                self.codec_detail_label.set_text("—")',
    '                self.bitrate_detail_label.set_text("—")',
    '                self.tags_detail_label.set_text("—")',
    "            return",
    "",
    '        name = self.current_station.get("name") or "Unknown station"',
    '        country = self.current_station.get("country") or "Unknown"',
    '        codec = self.current_station.get("codec") or "?"',
    '        bitrate = self.current_station.get("bitrate") or 0',
    '        tags = self.current_station.get("tags") or "No tags"',
    "",
    "        self.now_playing_label.set_text(str(name))",
    "        self.country_detail_label.set_text(str(country))",
    "        self.codec_detail_label.set_text(str(codec))",
    '        self.bitrate_detail_label.set_text(f"{bitrate} kbps")',
    "        self.tags_detail_label.set_text(str(tags))",
    "",
]
lines[start:end] = replacement
t = "\n".join(lines) + "\n"

t = t.replace(
    'self.data_usage_label.set_text(format_usage_line(self.usage_tracker.snapshot()))',
    'self.data_usage_label.set_text(format_usage_line(self.usage_tracker.snapshot()).replace("Data: ", ""))',
)

p.write_text(t)
PY

python -m compileall fluxtuner >/dev/null

echo "Applied exact GUI side panel details patch."
echo
echo "Review:"
echo "  git diff fluxtuner/gui/window.py"
echo
echo "Test:"
echo "  python -m fluxtuner --gui --player mpv"
echo
echo "Expected:"
echo "  - Right panel has Now Playing, Station details and Data usage sections."
echo "  - Station details update when playback starts."
echo "  - Details reset when playback stops."
