# TUI orchestration audit

## Status

Completed as a historical audit and decision record.

The first focused TUI workstream subsequently added executable orchestration
contracts and isolated playback coordination, view-state transitions and the
stream-metadata lifecycle. This document remains useful as the original
responsibility map; statements describing the pre-extraction shape should be
read in that historical context.

## Purpose

This document maps the responsibilities of `fluxtuner/tui.py` before the first
focused extractions.

The goal is not to split the file by line count. The goal is to identify seams
that improve ownership, lifecycle safety and executable testability while
preserving the existing Textual interface and player behavior.

## Current shape

`FluxTunerTUI` is both the Textual application and the primary orchestration
object for the local terminal interface.

Construction currently creates or resolves:

- the active theme and runtime theme path;
- the selected audio backend and its capabilities;
- the effective local profile;
- the player adapter;
- the search service;
- the data-usage tracker;
- mutable selection, playlist, theme and playback state;
- asynchronous search and metadata tasks.

The class also owns widget composition, lifecycle hooks, keyboard action
routing, status and details rendering, table payload state and direct calls into
core persistence modules.

## Responsibility map

### Application composition and lifecycle

Owned directly by `FluxTunerTUI`:

- player, search-service and usage-tracker construction;
- theme initialization;
- mount and unmount behavior;
- playback-state restoration and persistence;
- search-task and metadata-task cancellation;
- recurring Now Playing refresh.

This composition responsibility should remain in the application class unless a
later extraction produces a concrete lifecycle seam.

### Textual widget composition and interaction

The class defines:

- the complete widget tree;
- keyboard bindings;
- shortcut help;
- focus movement;
- button and table event handling;
- mode-dependent action routing.

Textual-specific event handlers should remain at the interface boundary. They
may delegate to focused coordinators, but should not be hidden behind a generic
framework abstraction.

### View and selection state

The following mutable fields are coordinated together:

- `view_mode`;
- `selected_station`;
- `selected_theme`;
- `previewed_theme`;
- `selected_tag`;
- `selected_playlist`;
- `active_playlist_name`;
- `favorite_tag_filter`;
- `pending_input_action`;
- `table_items` and `table_key_counter`.

Search, favorites, history, playlists, playlist stations and themes repeatedly
reset overlapping subsets of this state. This is a real seam, but extracting it
before executable view-routing contracts would make regressions difficult to
detect.

### Search orchestration

The TUI owns:

- live-search debounce and cancellation;
- reading search and filter widgets;
- `SearchRequest` construction;
- background `SearchService.search` execution;
- result table reset and population;
- compatibility-filter status output;
- focus behavior after explicit searches.

Search-service behavior is already shared. The remaining code is mostly
interface orchestration and is a medium-priority extraction candidate after
safety contracts exist.

### Playback orchestration

The TUI directly coordinates:

- station compatibility and URL validation;
- player start and stop;
- selected, playing and last-station state;
- metadata reset and refresh scheduling;
- data-usage tracking;
- listening-history recording;
- restored volume and mute preferences;
- playback-state persistence;
- active-row marker refresh;
- button, details and status projection.

This is the highest-value functional seam because it combines adapter calls,
persistence side effects and UI projection. It is also high risk and should not
be extracted without executable success, failure and stop contracts.

### Metadata and Now Playing

The class owns:

- metadata polling cadence;
- asynchronous metadata task lifecycle;
- stream metadata fetching;
- stale/raw metadata tracking;
- artist and track projection;
- player and data-usage status rendering.

Metadata is related to playback but has a distinct asynchronous lifecycle.
Initial playback extraction should preserve this as a dependency rather than
moving both concerns in one PR.

### Favorites and history

The class directly calls focused core modules for:

- loading, adding, removing and updating favorites;
- favorite tags and display names;
- loading and recording history;
- favorite marker and details refresh;
- rename, tag-edit and tag-filter input flows.

The persistence boundary already exists in core. The TUI still owns mutation
orchestration, validation messages and post-mutation view refresh.

### Persistent and dynamic playlists

The TUI coordinates:

- persistent playlist creation, deletion and membership changes;
- dynamic tag playlist loading;
- playlist and tag counts;
- playlist table rendering;
- playlist details;
- random smart play;
- switching between playlist index and station views.

This is cohesive enough for a later library/playlist coordinator, but it should
remain separate from the first playback extraction.

### Themes

Theme listing, preview, restoration, application and persistence remain in the
application class. Message formatting and details rendering are already
partially separated into `tui_themes.py` and `tui_details.py`.

Theme behavior is comparatively isolated and lower risk, but extracting it
first would not address the most important orchestration pressure.

### Table and details projection

Pure or nearly pure helpers already live in:

- `fluxtuner/tui_table.py`;
- `fluxtuner/tui_details.py`;
- `fluxtuner/tui_themes.py`.

`FluxTunerTUI` still owns the Textual `DataTable` mutation, row-payload registry,
selection restoration and widget updates. These should remain interface-local
unless an extraction clearly reduces duplicated mode transitions.

## Existing seams worth preserving

The TUI already delegates important domain behavior to focused modules:

- `SearchService` and `SearchRequest`;
- player adapters and `PlayerCapabilities`;
- station compatibility helpers;
- station normalization helpers;
- domain-specific favorites, history and playlist storage;
- data-usage tracking;
- stream metadata fetching;
- table formatting and details text generation;
- runtime theme application.

Future work should build on these seams rather than creating another broad
`services.py` module.

## Current test coverage and gap

`tests/test_ui_smoke.py` currently verifies that:

- `fluxtuner.tui` imports;
- `FluxTunerTUI` can be constructed with mocked player and theme dependencies;
- GTK import and renderer bootstrap behavior remain available.

This is useful packaging coverage, but it does not execute TUI mount, view
routing, playback success, playback failure, stop behavior, persistence side
effects, metadata-task lifecycle or library mutations.

Moving orchestration before adding those contracts would repeat the risk already
seen during the Web composition refactor.

## Recommended branch sequence

### 1. Add executable TUI orchestration contracts

Suggested branch:

`test/tui-orchestration-contracts`

Suggested title:

`test: add TUI orchestration contracts`

Minimum contracts:

- the app mounts with mocked runtime dependencies;
- initial selection and player state are coherent;
- successful `play_station` updates player, history, persistence and UI-facing
  state exactly once;
- unsupported or URL-less stations do not call the player;
- player failures do not commit playing state or history;
- `stop_playback` stops usage tracking and clears playing state;
- unmount cancels pending search/metadata work and stops the player;
- mode-dependent action routing remains explicit.

Tests should prefer mocked dependencies and Textual's pilot/test support rather
than real network or audio processes.

### 2. Extract TUI playback coordination

Suggested branch:

`refactor/tui-playback-coordinator`

Suggested title:

`refactor: isolate TUI playback coordination`

The first extraction should own the transactional playback sequence:

- validate station compatibility and URL;
- call the player adapter;
- update playing/last station state;
- start and stop usage tracking;
- record history after a successful start;
- apply restored preferences;
- persist playback state;
- expose a small result that the Textual layer projects to widgets and status.

Metadata polling, table refresh and Textual widget lookup should initially remain
in `FluxTunerTUI` and be passed as narrow callbacks only where necessary.

### 3. Reassess the next seam

After playback is isolated, compare the remaining pressure:

- view/selection-state transitions;
- favorites and playlist mutation coordination;
- search debounce and result projection;
- metadata lifecycle;
- theme coordination.

Choose one based on reduced coupling and test value, not file length.

## Candidate ownership rules

- `tui.py`: Textual composition, events, widget lookup and top-level wiring.
- playback coordinator: player transaction and playback-related side effects.
- future library coordinator: favorites/history/playlist mutation workflows.
- future view state: supported modes and selection resets, only if contracts
  demonstrate value.
- existing core modules: persistence and pure station/domain behavior.

## Non-goals for the first extraction

- no GTK changes;
- no Web changes;
- no player adapter rewrite;
- no metadata redesign;
- no shared cross-interface application service yet;
- no schema or storage migration;
- no user-visible shortcut, status-text or layout changes.

## Cross-interface services

The TUI and GTK expose overlapping features, but shared application services
should not be introduced from this audit alone.

First isolate one well-tested TUI workflow. During the later GTK audit, compare
actual orchestration and dependencies. Promote logic to a shared application
service only when equivalent behavior exists in at least two interfaces.

## Validation expectations

Every structural PR should keep:

```bash
git diff --check
make gate
```

Changes to mount, event routing, playback, metadata or task cancellation also
require a manual TUI smoke check with the supported player backends relevant to
the change.
