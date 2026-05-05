#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "fluxtuner/tui.py" ]; then
  echo "fluxtuner/tui.py not found. Run from repo root."
  exit 1
fi

python - <<'PY'
from pathlib import Path

path = Path("fluxtuner/tui.py")
text = path.read_text()

old = """    async def search(self, query: str, live: bool = False) -> None:
        self.restore_active_theme_if_previewing()
        query = query.strip()
        if not query:
            self.set_status("Type a station name or genre/tag first.")
            return

        self.view_mode = "search"
"""

new = """    async def search(self, query: str, live: bool = False) -> None:
        self.restore_active_theme_if_previewing()
        query = query.strip()
        country = self.query_one("#country-filter", Input).value.strip()
        min_bitrate_raw = self.query_one("#bitrate-filter", Input).value.strip()

        if not query and not country and not min_bitrate_raw:
            self.set_status("Type a station name/genre, or use country/min kbps filters.")
            return

        self.view_mode = "search"
"""

if old not in text:
    raise SystemExit("Could not find expected search() opening block. It may already be fixed or changed.")
text = text.replace(old, new)

old_inner = """        try:
            country = self.query_one("#country-filter", Input).value.strip()
            min_bitrate_raw = self.query_one("#bitrate-filter", Input).value.strip()
            min_bitrate = None
            if min_bitrate_raw:
                try:
                    min_bitrate = int(min_bitrate_raw)
                except ValueError:
                    self.set_status("Min kbps must be a number.")
                    return
            stations = await asyncio.to_thread(search_stations_filtered, query, country or None, min_bitrate, 50)
"""

new_inner = """        try:
            min_bitrate = None
            if min_bitrate_raw:
                try:
                    min_bitrate = int(min_bitrate_raw)
                except ValueError:
                    self.set_status("Min kbps must be a number.")
                    return
            stations = await asyncio.to_thread(search_stations_filtered, query, country or None, min_bitrate, 50)
"""

if old_inner not in text:
    raise SystemExit("Could not find expected filter parsing block.")
text = text.replace(old_inner, new_inner)

old_suffix = """        filters = []
        country = self.query_one("#country-filter", Input).value.strip()
        min_bitrate_raw = self.query_one("#bitrate-filter", Input).value.strip()
        if country:
            filters.append(f"country={country}")
"""

new_suffix = """        filters = []
        if country:
            filters.append(f"country={country}")
"""

if old_suffix not in text:
    raise SystemExit("Could not find expected status filter block.")
text = text.replace(old_suffix, new_suffix)

anchor = """    @on(Input.Changed, "#query")
    def live_search_from_input(self, event: Input.Changed) -> None:
        if self.pending_input_action:
            return
        self.schedule_live_search(event.value)
"""

addition = """    @on(Input.Submitted, "#country-filter")
    async def search_from_country_filter(self, _event: Input.Submitted) -> None:
        self.cancel_pending_search()
        query = self.query_one("#query", Input).value
        await self.search(query)

    @on(Input.Submitted, "#bitrate-filter")
    async def search_from_bitrate_filter(self, _event: Input.Submitted) -> None:
        self.cancel_pending_search()
        query = self.query_one("#query", Input).value
        await self.search(query)

"""

if addition not in text:
    if anchor not in text:
        raise SystemExit("Could not find live_search_from_input anchor.")
    text = text.replace(anchor, anchor + addition)

path.write_text(text)
PY

python -m compileall fluxtuner >/dev/null
echo "TUI country/min bitrate search fix applied."
