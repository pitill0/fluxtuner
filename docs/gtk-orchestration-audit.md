# GTK orchestration audit

## Purpose

This document records the GTK orchestration audit, the boundaries extracted
from `fluxtuner/gui/window.py` and the ownership that remains in `MainWindow`.

The goal was not to split `MainWindow` by line count. The work identified
boundaries that improve ownership, lifecycle safety and executable testability
while preserving the GTK4 interface and player behavior.

The Flatpak manifest is reviewed here only as a permission inventory. Permission
changes remain a separate branch and must be tested across Xorg and Wayland
environments.

## Completion status

The GTK orchestration workstream is complete.

The work was delivered as a sequence of focused contract, hardening and
extraction changes:

- GTK orchestration contracts for playback, stop and close;
- GTK playback coordination extraction;
- metadata close cleanup, lifecycle hardening and lifecycle extraction;
- search lifecycle hardening and extraction;
- view-transition hardening;
- logical view-state extraction.

Each boundary was validated with focused orchestration tests, the full project
gate, CI and manual desktop smoke checks before merge.

The resulting ownership is intentionally interface-specific. GTK retains its
GLib, thread and widget boundary rather than forcing reuse of TUI lifecycle
objects whose runtime contracts differ.

## Final ownership boundaries

`MainWindow` remains responsible for the GTK interface boundary:

- widget construction and direct widget mutation;
- GTK signals and gestures;
- daemon thread creation and `GLib.idle_add` handoff;
- GLib timeout creation and removal;
- search request construction and service invocation;
- station-list data, selection and row rendering;
- favorites and history service calls;
- status, playlist and Now Playing projection.

Focused GTK modules now own isolated decisions:

- `fluxtuner/gui/gtk_playback.py`: playback start/stop coordination and results;
- `fluxtuner/gui/gtk_metadata.py`: metadata generation, fetch-slot lifecycle,
  stale-result rejection and deduplication;
- `fluxtuner/gui/gtk_search.py`: search request identity and stale-callback
  rejection;
- `fluxtuner/gui/gtk_view_state.py`: logical view identity and active
  playlist-tag transitions.

No broad generic GUI service was introduced, and no cross-interface abstraction
was forced where GTK and TUI runtime semantics remain different.

## Original shape

`MainWindow` is both the GTK application window and the primary orchestration
object for the desktop interface.

Construction currently resolves or creates:

- the selected player backend and capabilities;
- the effective profile;
- the player adapter;
- the search service;
- the data-usage tracker;
- restored volume and mute preferences;
- mutable search, selection, view, playlist and playback state;
- GLib timer identifiers and metadata polling state;
- the complete GTK widget tree.

The class also owns background thread creation, GLib main-loop handoff,
persistence calls, player control, list rendering and status projection.

## Responsibility map

### GTK composition and widget ownership

`MainWindow` builds and owns:

- the application window and root layout;
- header and search controls;
- station list and row widgets;
- station-details and Now Playing panels;
- favorites, history and playlist controls;
- playback, mute and volume controls;
- status and data-usage labels;
- GTK signal and gesture bindings.

GTK widget construction, signal handlers and direct widget mutation should remain
at the interface boundary.

### Search orchestration

The window currently:

- reads query, country and bitrate fields;
- creates `SearchRequest`;
- starts a daemon `threading.Thread`;
- invokes `SearchService.search`;
- sends success or failure back through `GLib.idle_add`;
- replaces the current station collection;
- re-renders rows and updates view status.

The shared `SearchService` boundary already exists. The remaining GTK code mixes
thread lifecycle, request construction and UI projection. This is a meaningful
candidate only after executable contracts cover success, failure and stale
completion behavior.

### Playback orchestration

The window directly coordinates:

- station selection checks;
- compatibility and URL validation;
- restored preferences before playback;
- player startup;
- volume and mute application;
- current-station commit;
- data-usage tracking;
- history recording;
- Now Playing and player-state refresh;
- GLib timer startup;
- row marker refresh;
- status and play/stop button projection.

This is the highest-value first functional seam. It combines adapter calls,
persistence side effects and GTK projection, and closely resembles the already
isolated TUI playback transaction without yet proving that a shared
cross-interface service is appropriate.

### Playback controls and preference persistence

Mute and volume handling currently own:

- capability checks;
- active-playback checks;
- player command execution;
- error projection;
- restored preference state;
- config persistence;
- player-state refresh.

These operations are related to playback but should not be folded into the first
start/stop extraction unless contracts show that doing so keeps the boundary
smaller.

### Metadata lifecycle

GTK metadata currently uses:

- one GLib timeout source;
- one `_metadata_fetch_in_progress` flag;
- daemon worker threads;
- `fetch_stream_metadata`;
- `GLib.idle_add` completion callbacks;
- raw-value deduplication;
- direct artist/track label projection;
- stop-time timer removal and label clearing.

Known risks to protect before any extraction:

- a slow result for station A can be projected after station B starts;
- stop can clear labels before an older worker posts its result;
- fetch exceptions are not explicitly converted into a contained result;
- `_metadata_fetch_in_progress` is global rather than request-specific;
- a worker completion can race with a newer request.

The TUI `MetadataLifecycle` is evidence of a useful rule set, but GTK should not
reuse it mechanically until threading and GLib callback semantics are covered by
GTK-specific contracts.

### View, selection and row projection

The class coordinates:

- `stations`;
- `last_search_results`;
- `selected_station`;
- `current_station`;
- `current_view`;
- `active_playlist_tag`;
- favorite URL cache;
- preferred-row restoration;
- row markers and CSS classes;
- selection fallback after re-render.

This is a real state-transition seam. It should be reassessed after playback
contracts because row rendering and current-station markers are playback
projections.

### Favorites and history

The window directly calls focused core modules for:

- favorite loading and URL caching;
- add, remove and edit operations;
- tag parsing and tag filtering;
- visible-station mutation after edits;
- history loading and display;
- button sensitivity and edit-field projection.

Persistence ownership already exists in core. GTK still owns validation,
mutation sequencing, cache refresh and view refresh.

### Dynamic tag playlists

The GTK interface currently coordinates tag-based playlists rather than the full
persistent-playlist feature set exposed elsewhere.

It owns:

- available tag discovery;
- filtering favorites by tag;
- active tag state;
- random selection;
- playlist status projection;
- transitions back to unfiltered favorites.

This should remain separate from the first playback extraction.

### Timers and shutdown

The window owns GLib sources for:

- data-usage refresh;
- player-state refresh;
- metadata polling.

Close handling must stop or remove runtime work, persist playback preferences and
stop the player without leaving callbacks that mutate destroyed widgets.

Executable shutdown contracts are required before moving lifecycle code.

## Existing seams worth preserving

The GTK interface already delegates important behavior to:

- `SearchService` and `SearchRequest`;
- player adapters and capability checks;
- station normalization and compatibility helpers;
- domain-specific favorites and history storage;
- data-usage tracking;
- stream metadata fetching;
- playback state configuration.

Future work should build on these seams rather than creating a broad generic
`gui_service.py`.

## Executable contracts

`tests/test_gtk_orchestration.py` now exercises the extracted and retained
boundaries without requiring network access, real audio processes or a live GTK
desktop.

The contracts cover:

- successful, failed and invalid playback starts;
- playback stop and close cleanup;
- metadata generation, fetch-slot ownership, stale completion, deduplication and
  contained worker failure;
- search generation binding and stale success/failure rejection;
- search invalidation when changing to favorites, history or tag playlists;
- logical view and active-tag transitions;
- normal and random tag-playlist behavior;
- GTK projection remaining in `MainWindow`.

Manual smoke checks were also performed throughout the workstream for playback,
rapid stop, station replacement, concurrent searches, local-view transitions,
tag playlists and close during runtime work.

## Workstream result and next branch

The original branch sequence has been completed. Playback, metadata, search and
view state were hardened before extraction, with each change kept in a focused
PR.

No further GTK orchestration extraction is recommended solely to reduce
`MainWindow` line count. Future movement should require a new behavior,
lifecycle risk or independently testable ownership boundary.

The next independent workstream is the Flatpak permission review:

`security/review-flatpak-permissions`

Permission changes must not be combined with GTK orchestration refactors. The
review should use the inventory and environment matrix below, removing only one
candidate permission at a time.

## Flatpak permission inventory

Current `finish-args`:

```yaml
- --share=network
- --share=ipc
- --socket=fallback-x11
- --socket=wayland
- --socket=pulseaudio
- --device=dri
```

### `--share=network`

Expected to remain required.

FluxTuner searches remote station directories, opens internet-radio streams and
fetches optional stream metadata.

### `--socket=wayland`

Expected to remain required for native Wayland GTK sessions.

### `--socket=fallback-x11`

Expected to remain required for Xorg sessions and GTK fallback when Wayland is
unavailable.

Use `fallback-x11`, not unrestricted `x11`, unless testing proves the fallback
socket is insufficient.

### `--socket=pulseaudio`

Expected to remain required for audio playback through the current player
integration.

The later audit should also verify player subprocess behavior inside Flatpak and
whether every supported backend uses the same audio path.

### `--share=ipc`

Candidate for least-privilege testing.

Shared IPC is commonly paired with X11 for performance and compatibility, but it
must not be removed solely from static inspection. Test GTK startup, list
rendering, interaction, playback and shutdown under the target Xorg environments
with this permission removed.

### `--device=dri`

Candidate for least-privilege testing.

GTK rendering may use GPU acceleration even though FluxTuner does not implement
custom graphics. Test with and without DRI under Wayland and Xorg, including
software-rendering fallback, window resizing, scrolling and long-running
playback.

## Flatpak validation matrix

Run the later permission branch against at least:

| Environment | Display path | Required checks |
| --- | --- | --- |
| CRUX | Xorg | startup, search, scrolling, playback, mute/volume, close |
| CRUX | Wayland | startup, search, scrolling, playback, mute/volume, close |
| Ubuntu | Xorg | startup, search, scrolling, playback, mute/volume, close |

For each candidate permission:

1. remove only one permission at a time;
2. rebuild and reinstall the Flatpak;
3. inspect effective permissions with `flatpak info --show-permissions`;
4. run the same smoke sequence;
5. capture terminal output and relevant journal messages;
6. restore the permission before testing the next candidate;
7. keep the reduction only when all required environments pass.

Additional checks:

- launch from the desktop file and from a terminal;
- test the default player and any packaged alternative backend;
- verify audio devices before and after suspend/resume where practical;
- resize and scroll the station list repeatedly;
- close during active playback and during metadata/search work;
- confirm no host filesystem permission is introduced as compensation.

## Non-goals

- no production code movement in the audit PR;
- no Flatpak permission changes in the audit PR;
- no GTK visual redesign;
- no TUI or Web changes;
- no player adapter rewrite;
- no shared application service yet;
- no packaging runtime-version change.

## Validation expectations

Every structural GTK PR should keep:

```bash
git diff --check
make gate
```

Changes to GTK startup, playback, timers, threads or shutdown also require
manual desktop smoke checks.

The later Flatpak permission branch additionally requires the environment matrix
defined above.
