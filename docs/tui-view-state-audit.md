# TUI view and selection state audit

## Purpose

This document audits the remaining view and selection-state coordination in
`fluxtuner/tui.py` after playback coordination was extracted.

The goal is to determine whether the next refactor should introduce a dedicated
state object, extract explicit transition helpers or leave the current code in
place.

## State currently coordinated by the TUI

The main view-related fields are:

- `view_mode`;
- `selected_station`;
- `selected_theme`;
- `selected_tag`;
- `selected_playlist`;
- `active_playlist_name`;
- `favorite_tag_filter`;
- `pending_input_action`;
- `table_items`;
- `table_key_counter`.

Not all of these belong to one conceptual state object. `table_items` and
`table_key_counter` are DataTable projection state, `pending_input_action` is
input-workflow state and `favorite_tag_filter` is a favorites-view parameter.

## Current view modes

The current modes are `search`, `favorites`, `history`, `playlists`,
`playlist_stations` and `themes`.

## Transition map

### Search, favorites and history

These three station-list views apply the same broad reset:

- set the new `view_mode`;
- clear station, theme, tag and playlist selections;
- clear `active_playlist_name`;
- clear details before repopulating the table.

Favorites additionally stores `favorite_tag_filter`.

### Playlists index

Entering playlists:

- sets `view_mode` to `playlists`;
- clears `active_playlist_name`;
- clears station, theme, tag and playlist selections;
- resets the table to playlist-shaped columns.

After population, the first actionable row becomes either
`selected_playlist` or `selected_tag`. Those selections are mutually exclusive.

### Persistent playlist stations

Entering a persistent playlist:

- sets `view_mode` to `playlist_stations`;
- stores `active_playlist_name`;
- clears station, theme and tag selections;
- preserves the parent `selected_playlist`;
- clears details before station population.

This is the main exception to a generic reset.

### Themes

Entering themes:

- sets `view_mode` to `themes`;
- clears station and tag selection;
- rebuilds the table using playlist/theme-shaped columns;
- initializes `selected_theme` when rows exist.

Theme entry is intentionally asymmetric with the station-list resets. Future
helpers should make that asymmetry explicit rather than hiding it.

## Row-highlight selection rules

The DataTable payload kind drives a second selection state machine.

- A station selects `selected_station`, clears theme and tag, and clears
  `selected_playlist` unless the current mode is `playlist_stations`.
- A theme selects `selected_theme` and clears station, tag and playlist.
- A persistent playlist selects `selected_playlist` and clears tag, station and
  theme.
- A dynamic tag selects `selected_tag` and clears playlist, station and theme.

The key invariant is that only the selection compatible with the highlighted
payload remains active, except that playlist-station rows deliberately preserve
their parent playlist.

## Action routing coupled to view state

Enter, Add, Delete, Random and Favorites interpret the same shortcut differently
according to `view_mode`. That routing should remain in `tui.py`: it is
interface behavior, not generic state management.

## Invariants worth protecting

1. Persistent playlist and dynamic tag selections are mutually exclusive.
2. Theme selection excludes station, playlist and tag selection.
3. A normal station selection excludes theme and tag selection.
4. A station inside `playlist_stations` preserves its parent playlist.
5. Leaving `playlist_stations` clears `active_playlist_name`.
6. Entering search, favorites or history clears all row selections before
   population.
7. `favorite_tag_filter` remains a favorites-view parameter.
8. `pending_input_action` is not reset by unrelated selection transitions unless
   workflow cancellation is explicit.

## Recommendation

Do not introduce a broad mutable `TUIViewState` object yet.

Such an object would combine view identity, DataTable projection, input workflow,
favorites filtering and library context. That would move assignments without
reducing behavioral coupling.

The next safe step should extract small, explicit transition helpers that mutate
the existing `FluxTunerTUI` fields in one place.

Candidate helpers:

- `enter_station_view(mode, *, favorite_tag_filter=None)`;
- `enter_playlists_view()`;
- `enter_playlist_stations_view(playlist_name)`;
- `enter_themes_view()`;
- `select_station(station, *, preserve_playlist=False)`;
- `select_theme(theme_name)`;
- `select_playlist(name)`;
- `select_tag(tag)`.

The helpers should remain TUI-specific and should not become a generic
application service.

## Recommended branch sequence

### 1. Add view-state transition contracts

Branch: `test/tui-view-state-contracts`

Title: `test: add TUI view-state transition contracts`

Cover:

- complete resets for search, favorites and history;
- playlists selecting only one playlist kind;
- playlist-stations preserving the parent playlist;
- themes clearing incompatible selections;
- row-highlight payload invariants;
- clearing `active_playlist_name` when leaving playlist-stations.

### 2. Extract explicit transition helpers

Branch: `refactor/tui-view-state-transitions`

Title: `refactor: centralize TUI view-state transitions`

Replace repeated assignments without changing widget composition, action
routing, table population, details rendering or feature behavior.

### 3. Reassess remaining pressure

Compare library mutations, metadata lifecycle, search orchestration and theme
coordination. Do not choose the next seam based only on remaining line count.

## Non-goals

- no generic state framework;
- no reducer or event bus;
- no GTK or Web state unification;
- no action-routing extraction;
- no DataTable abstraction;
- no input-workflow redesign;
- no user-visible behavior changes.

## Validation expectations

Every structural PR should keep:

```bash
git diff --check
make gate
```

View-transition changes also require a manual TUI smoke check across search,
favorites, history, playlists, playlist contents and themes.
