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

The first GTK orchestration workstream is complete. Issue #316 defines a
second incremental workstream for responsibilities added or retained since it.

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


## Issue #316: second GTK controller workstream

### Measured baseline and validation environment

At `054156b` (after PR #321), `window.py` contains 2,760 lines and 155 direct
`MainWindow` methods. Earlier estimates counted 166 methods; direct class-body
AST counting is the reproducible baseline used here. At C901 threshold 10,
only `_show_station_context_menu` exceeds the threshold, at 12. The remaining
problem is breadth of responsibility, not excessive branching in every method.

On Nukleuz, the isolated `.venv` initially ran 323 GTK contracts with one
module skipped because `gi` was unavailable. The system interpreter and `.venv`
share CPython 3.12.15 and the same ABI. System PyGObject 3.58.1 and GTK 4.24.1
initialize successfully under Wayland. A temporary directory exposing only the
system `gi` and Cairo packages enabled the same `.venv` to run 332 GTK contracts
with no skips. A native GTK button signal was also checked. This validates the
binding environment and contracts, not every interactive desktop workflow.

`scripts/run_gtk_tests.py` makes real-binding validation explicit. It requires
GTK4 and a working display before collecting tests and checks that the real
bindings remain loaded after the run. Ordinary headless tests remain available;
the real-GTK runner supplements them rather than treating skips as validation.
It neither installs packages nor changes virtual-environment configuration.

From the checkout, in a graphical session:

```bash
.venv/bin/python scripts/run_gtk_tests.py
```

For Nukleuz's isolated environment, supply an explicitly prepared temporary
binding directory containing `gi` and, where needed, `cairo` from the compatible
system Python. Check Python version and SOABI before preparing these links;
do not link packages built for another interpreter.

```bash
.venv/bin/python scripts/run_gtk_tests.py --bindings-dir /path/to/gtk-bindings
```

Additional arguments are forwarded to pytest. Pass explicit test paths when
adding pytest options, for example `-- -q tests/test_gtk_recording.py`.
The runner is not the full quality/security gate.

### Extraction sequence and ownership

1. Recording actions: isolate FFmpeg recording request/start/finalization
   coordination. Preserve selected versus explicitly targeted station behavior,
   status messages, recording independence from playback and button projection.
2. Ripping actions and monitoring: isolate Brynse availability, explicit station
   actions, status deduplication and worker monitoring. Preserve profile scope,
   existing service contracts and one-owner GLib timer cancellation.
3. Quit/shutdown lifecycle: isolate pending work, confirmation, deadlines and
   completion decisions. Preserve asynchronous FFmpeg/Brynse finalization,
   idempotent callbacks, tray behavior and explicit force-quit consent.
4. Library actions: reassess favorites, persistent playlists and selection/cache
   refresh ownership after the recording lifecycle boundaries are stable.
5. Reassess remaining projection/layout/context-menu responsibilities based on
   measured coupling. Preserve the existing playback, metadata, search and
   logical-view boundaries unless a specific contract demonstrates a need.

Controllers must not import `MainWindow` or retain the whole window as an
untyped dependency. Pass narrow services, state or projection callbacks. Keep
GTK widget mutation on the main loop, and make ownership of threads, GLib
sources and deferred completions explicit. Do not duplicate state between a
controller and the window merely to keep old attribute names working.

### Per-extraction acceptance and budgets

Each extraction requires focused controller contracts, existing GTK contracts,
real-binding validation and manual desktop smoke checks for affected behavior,
followed by the full project quality and security gate before its PR. Compare
observable side effects and ordering, including failure and stale completion
paths; do not replace behavior tests with source-length assertions.

The baseline is 2,760 lines/155 direct methods. Record both metrics after each
extraction and reduce the measured budget when responsibilities move. Do not
impose an arbitrary 800/1,200-line ceiling before identifying coherent owners,
and do not move code solely to satisfy a count. The C901 policy from #315
continues to apply to production code and tests.

A PR delivering one stage must refer to #316 without closing the umbrella issue.
Close #316 only after the agreed controller workstream and its validation are
complete. Web #311, metadata/background recovery, the initial login HTTP 422,
Brynse version updates and Flatpak permission changes remain separate work.


### First extraction: recording actions

`fluxtuner/gui/gtk_recording.py:RecordingController` now coordinates explicit
station recording and synchronous user-requested finalization. It receives the
existing `RecordingManager` and narrow status/control projection callbacks; it
does not import GTK, hold the window, own a second session or create workers.
A short-lived action controller is bound by `MainWindow._recording_actions` for
each action. All recording state remains authoritative in the existing manager.

`MainWindow` retains selection handling, the shutdown guard, signal handlers,
button widgets and button projection. Existing URL/name/output-path helpers are
passed into the start action. Their exceptions remain outside the manager error
boundary, matching previous behavior. Successful starts/stops refresh controls
before displaying status; validation/backend errors display status before the
control refresh, also matching previous behavior.

The asynchronous `AsyncRecordingStop` shutdown path continues to call the same
manager directly. This extraction does not route shutdown through a synchronous
UI stop action or change pending-recording confirmation and finalization.

Controller contracts cover explicit target identity, unavailable backends,
missing URLs, request construction, preparation/backend/projection failures,
status/control ordering, completed recording identity and live manager state.
Existing GTK recording and context-menu contracts remain unchanged. Structural
checks preserve every other `MainWindow` method, including shutdown and ripping.
Record post-format window metrics in the extraction report; the workstream
remains open pending later controller extractions and manual/full-gate validation.


### Second extraction: ripping actions and monitoring

PR #322 completed the first recording-action stage. Its full gate passed
(1,948 tests, eight optional/environment skips), with 346 additional real-GTK
contracts. Manual session recording, explicit stop, canceling close during an
active recording and confirmed close/finalization were checked on Nukleuz.

The next baseline at `9b3ad9c` ran 114 focused ripping/lifecycle contracts with
real GTK. Seven optional Brynse backend contracts were skipped because Brynse
was not installed. The installed `fluxtuner-ripper` development distribution is
not evidence that those Brynse contracts ran. The pinned Brynse revision remains unchanged. Subsequent validation installed
that exact revision only in a temporary dependency directory, preserving
the project virtualenv. GTK and ripping contracts then ran together: 406
passed with no skips, including all seven real-Brynse contracts.

The user also confirmed the manual GTK sequence with the isolated backend:
an explicitly targeted station, responsive ripping, explicit stop, canceling
quit while active, then confirming quit and waiting for finalization. The
application exited normally; two MP3 outputs (264.528 and 209.160 seconds)
were recognized by ffprobe. The final full gate follows these checks.

`gtk_ripping_controller.py:RippingController` now owns cached capability and
its probe handle, status deduplication and the single UI monitoring timer. It
receives the existing `RippingService`, profile resolver and narrow status,
shutdown-state and scheduling callbacks. It imports no GTK widgets or window,
retains no window dependency, and does not duplicate service snapshots/jobs.
The existing availability worker dispatches results to the main loop. Late
results and future actions are ignored once the shared shutdown guard is set.

`MainWindow` retains profile resolution, GTK signal adapters and context-menu
construction. The menu reads the controller's authoritative cached capability.
The window's shutdown lifecycle still sets the existing shared guard and asks
`RippingShutdown` to finalize backend workers. It delegates only UI source
cancellation to `stop_monitoring`, preserving the former ordering. The
controller neither waits for workers synchronously nor owns another shutdown
flag; the later quit/shutdown extraction remains separate.

Start/stop keep their existing error boundaries, targeted station/profile and
status-before-timer order. Monitoring calls `wait(timeout=0)` before taking a
snapshot, continues through terminal states while workers are pending, and
updates messages when late finalized outputs appear. Deduplication includes
the job identity. Existing orchestration contracts move to this owner, while
window signal, profile and shutdown integration contracts remain in place.

Record post-format size/direct-method metrics in the extraction report. Four
monitor/probe methods leave `MainWindow`; recording, playback, metadata, search,
profile resolution and quit decisions retain their existing contracts. Manual
GTK checks and the full gate remain required before the second-stage PR.


## Stage 3: quit and shutdown ownership

The ripping-controller stage was integrated in PR #323. Its final gate passed
1,954 tests with eight optional skips; the separate real-GTK/ripping run passed
406 tests without skips, including the pinned Brynse contracts. The new focused
shutdown baseline passed 157 real-GTK contracts without skips on Nukleuz.

`gtk_shutdown.py:ShutdownController` receives RecordingManager, RippingService
and narrow callbacks for status, dialogs, playback/activity cancellation,
accepted-quit preparation, scheduling and monotonic time. It imports neither
GTK nor MainWindow. It owns pending confirmation, the shutdown guard and close
authorization, both existing stop helpers, the first completion callback, one
polling source, its deadline and whether the warning dialog is open. Manager
and service still own their runtime sessions/jobs; helper implementations and
backend stop semantics are unchanged.

The window builds this owner once and delegates request_quit/shutdown. Its
ripping controller, playback and recording actions read the same guard.
MainWindow retains GTK dialog construction, close-to-tray/hide behavior and
its close-request adapter. A small activity adapter preserves monitor, usage
timer, player-state timer, metadata and usage-tracker cancellation order.
The accepted-quit adapter disables hiding to the tray. No proxy state aliases
or duplicated shutdown flags remain in the window.

The extraction preserves confirmation cancellation, protection against repeated
responses, first-completion priority, nonblocking FFmpeg and ripping checks,
one 200 ms polling source, the monotonic 12 second warning and explicit
Keep waiting/Quit anyway choices. A timeout or backend failure never grants
automatic exit. Dialog implementations and unrelated MainWindow methods retain
their AST. Sixteen lifecycle contracts move to the GTK-independent controller
suite; GTK window/dialog and actual asynchronous recording-stop integration
contracts remain at the window boundary. New contracts cover stop ordering,
duplicate requests, canceled confirmation callbacks and window delegation.

This is an ownership change rather than a method-count target: the timer
callback leaves the window, while two narrow UI adapters are added. Record
post-format line/direct-method metrics in the extraction report. Incremental
checks, native GTK checks, manual recording/ripping closure and the full final
quality/security gate must be reported distinctly. Manual checks are confirmed below; the full final gate follows this update. Library actions and the later measured
reassessment remain under the open #316 umbrella.


Stage-3 manual validation on Nukleuz was confirmed by the user after block 275.
The FFmpeg-only and combined FFmpeg/Brynse GTK instances both exited normally.
The user confirmed active ripping and session recording during the combined
phase, cancellation of quit, and accepted quit with work still active. Four
session files were recognized by ffprobe (29.074, 10.188, 19.879 and 37.224
seconds). No Brynse track files were produced in this short live run; this is
not claimed as new manual validation of segmented track output. The previous
ripping stage's two validated MP3 outputs remain separate evidence. One GDK
frame-timing warning appeared in the first instance without preventing normal
exit. All eight source files, index, branches and virtualenv were preserved.

After formatting, MainWindow measures 2,525 lines and 153 direct methods,
compared with 2,633 lines and 152 methods before this stage. The additional
method reflects replacing the polling callback with two narrow UI adapters;
shutdown state, timer and worker coordination now have a single owner. All
357 GTK contracts passed with real bindings during incremental validation.
The complete final quality/security gate is run after this documentation update;
its result must be reviewed separately before staging or preparing the PR.
