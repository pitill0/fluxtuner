# Architecture refactor roadmap

FluxTuner has grown from a local internet-radio app into a multi-interface
platform with TUI, GTK, CLI and Web/server mode. This roadmap describes an
incremental refactor path for the post-`v1.0.5` series.

The goal is not a rewrite. The goal is to make the existing behaviour easier to
reason about, test and extend while keeping releases small and reversible.

## Current pressure points

### Large interface modules

Several interface modules carry many responsibilities at once:

- `fluxtuner/web/app.py` previously owned FastAPI app creation, auth guards,
  setup, dashboard, admin user management, password-change requests, search,
  history, favorites, playlists and station payload shaping. The first Web
  refactor pass has reduced it to composition/bootstrap plus a small set of
  setup, dashboard and health endpoints.
- `fluxtuner/web/static/app.js` is now a small ES module composition root. It
  collects DOM references, creates shared application state and focused browser
  controllers, connects late-bound dependencies, binds application events and
  starts the browser bootstrap sequence. DOM lookup, session UI, navigation,
  event binding, bootstrap ordering and the player runtime bridge now live in
  dedicated modules under `fluxtuner/web/static/js/`.
- The Web visual system is now split into focused stylesheets for the global
  base, shell, buttons, panels, forms, feedback, dialogs and feature-local
  components. Stylesheet ownership and load order are protected by regression
  tests; future CSS changes should extend the matching component boundary rather
  than rebuilding a monolithic `styles.css`.
- `fluxtuner/tui.py` and `fluxtuner/gui/window.py` contain broad UI orchestration
  plus player, metadata, favorites, history and playlist behaviour. The current
  TUI responsibility map, test gaps and proposed extraction order are documented
  in `docs/tui-orchestration-audit.md`.

These files are still workable, but new features increasingly require scanning a
large surface area.

### Core storage boundaries

`fluxtuner/core/db.py` remains the shared SQLite foundation for local and Web
data. It owns connection setup, schema creation and migrations, default
user/profile bootstrap and compatibility wrappers for older call sites.

Domain-specific persistence now lives in focused modules:

- `fluxtuner/core/users.py` for user-account storage;
- `fluxtuner/core/password_changes.py` for password-change requests;
- `fluxtuner/core/profiles.py` for profiles and profile ownership;
- `fluxtuner/core/stations.py` for station records;
- `fluxtuner/core/favorites.py` for favorites;
- `fluxtuner/core/history.py` for listening history;
- `fluxtuner/core/playlists.py` for playlists;
- `fluxtuner/core/public_stats.py` for public statistics.

Schema and bootstrap responsibilities intentionally remain together in `db.py`.
Compatibility wrappers are retained while existing call sites are reviewed
gradually.

### Web state model

The Web player now uses an explicit internal state model for `idle`, `loading`,
`playing`, `paused` and `error`. Allowed transitions are validated, the DOM is a
UI projection rather than the source of truth, and playback attempt IDs prevent
obsolete asynchronous work from changing current state.

Browser connectivity, visibility and page lifecycle events reconcile the model,
audio element and Media Session conservatively. If connectivity interrupts an
active stream, the player uses bounded, cancellable retries to reconnect it.
Explicit pause, stop and station changes retain priority and never trigger stale
automatic playback.

### Feature parity pressure

TUI, GTK and Web all expose overlapping concepts: search, station selection,
playback, favorites, history, playlists, metadata and data usage. Some logic is
already shared through core modules, but UI-specific orchestration still repeats
patterns that could be expressed as application services.

## Target shape

Use a light layering model rather than a heavy framework:

```text
interfaces/
  web, tui, gui, cli
application/
  use cases and orchestration services
core/domain/
  entities, validation, pure rules
adapters/
  sqlite, radio-browser/http, audio players, filesystem/config
```

The repository does not need to adopt these exact directory names immediately.
The first step is to introduce seams and move code only when it reduces risk.

## Web refactor status after v1.0.5

The first Web refactor phases are complete. `fluxtuner/web/app.py` is now kept
as the FastAPI composition/bootstrap layer: app creation, static/template
wiring, health, setup, dashboard and router inclusion. The browser client has
also been split from one large `static/app.js` file into focused ES modules
loaded through a no-build module entrypoint.

Current Web routers:

- `fluxtuner/web/routes/public.py` for public API endpoints.
- `fluxtuner/web/routes/auth.py` for register, login, logout, session and
  password-change request endpoints.
- `fluxtuner/web/routes/library.py` for search, history, favorites and
  playlists.
- `fluxtuner/web/routes/admin.py` for admin users and password-change review
  endpoints.

Extracted Web helper/action modules:

- `payloads.py`, `validation.py`, `security.py`, `setup.py`;
- `context.py`, `guards.py`, `dashboard.py`, `library.py`;
- `admin_users.py`, `admin_actions.py`;
- `password_changes.py`, `password_change_actions.py`;
- `registration_actions.py`.

Current Web browser modules:

- `api.js` for CSRF-aware API requests.
- `auth.js`, `account-requests.js` and `setup.js` for login, account request,
  password-change request and first-run setup flows.
- `dashboard.js`, `admin.js`, `public-stats.js` and `health.js` for authenticated
  dashboard, admin operations, public stats and server health rendering.
- `search.js`, `favorites.js`, `playlists.js`, `library-views.js`,
  `station-renderer.js` and `playlist-renderer.js` for Radio Browser search and
  profile-owned library interactions.
- `player.js`, `metadata.js`, `media-session.js` and `player-debug.js` for
  browser playback, cached Now Playing metadata, mobile Media Session handoff
  and local diagnostics.
- `theme.js` and `ui-shell.js` for theme preference and responsive app shell
  behavior.
- `app-elements.js` for the application DOM registry.
- `app-state.js` for shared browser application state.
- `session-ui.js` for authentication/setup-driven UI coordination.
- `navigation.js` for application navigation.
- `app-events.js` for application-wide event binding.
- `app-bootstrap.js` for startup ordering.
- `player-runtime.js` for the single late-bound browser player reference.

Executable JavaScript contract tests now run ES modules through Node from
`tests/test_web_js_modules.py`. Source-boundary and ownership checks remain in
`tests/test_web_static_js_sanity.py`; both styles protect different failure modes.

Packaging note: new Web subpackages must be included in the setuptools package
list. The router package is currently listed as `fluxtuner.web.routes` in
`pyproject.toml`; keep this in mind when adding new package directories.

Recommended next branches should stay separate:

- search quality/debugging;
- the first TUI orchestration workstream is complete: playback coordination,
  view-state transitions and stream-metadata lifecycle are isolated behind
  executable contracts;
- GTK orchestration auditing is next, including a least-privilege review of
  `flatpak/io.github.pitill0.Fluxtuner.yml` finish arguments;
- smaller follow-up storage cleanups only where they reduce risk without moving schema.

The numbered roadmap remains the source of truth. The first six phases and the
Web CSS/component boundary workstream are complete. Search quality, local
interface audits and storage cleanup are follow-up workstreams and should remain
independently scoped.

## Roadmap progress

```text
Phase 1  Audit and safety rails                          complete
Phase 2  Extract Web API helpers and routers             complete
Phase 3  Split storage by domain without changing SQLite complete
Phase 4  Web JavaScript module boundaries                complete and hardened
Phase 5  Web player state model                          complete
Phase 6  Revisit metadata `Now Playing`                  complete
```

### Completed follow-up workstreams

#### TUI orchestration boundaries

Status: completed for the first focused workstream.

The completed TUI work established and hardened three explicit boundaries:

- playback coordination, including success, failure and stop side effects;
- view and selection-state transitions across search, favorites, history,
  playlists, playlist stations and themes;
- stream-metadata lifecycle state, including throttle, request identity, task
  ownership, cancellation, stale-result rejection, deduplication and fallback
  projection.

`fluxtuner/tui.py` remains the Textual composition and projection boundary.
Focused modules own behavior only where lifecycle safety or executable
testability clearly improved. Favorites, playlists, search and themes remain
interface-local until a future audit demonstrates a stronger seam.

The workstream was delivered through separate audit, contract, hardening and
extraction PRs. It intentionally introduced no GTK changes and no generic
cross-interface application service.

#### Web CSS and component styling boundaries

Status: completed.

The Web visual system now uses focused stylesheets with explicit ownership:

```text
styles.css              global tokens, document base and typography
shell.css               application shell
buttons.css             shared button behavior
panels.css              hero and panel surfaces
forms.css               shared form controls
feedback.css            status, empty-state and error feedback
dialogs.css             dialogs
auth.css                authentication and setup
public.css              public entry and statistics
dashboard.css           authenticated dashboard
admin.css               administration
search.css              search controls and diagnostics
stations.css            station lists and cards
station-actions.css     station actions
player.css              player and Now Playing
```

Source-boundary tests verify that selectors remain in their owning stylesheet.
Load-order tests protect intentional cascade relationships, including shared
buttons before panel-specific hero overrides and shared feedback before
feature-specific status rules.

`styles.css` should remain a small global base. Future visual changes should be
made in the matching component stylesheet, and new files should only be added
when they introduce a clear ownership boundary.

The first six phases and the CSS follow-up workstream are complete. Future work
should continue through small, independently reviewable branches rather than
extending completed Web composition, player, metadata or CSS series
opportunistically.

## Proposed incremental phases

### Phase 1: Audit and safety rails

Status: completed and continuously enforced.

Completed safety rails include:

- keeping `make gate` green after every small patch;
- tests that detect accidental duplicate Web player functions or duplicated
  Media Session handlers;
- documented module responsibilities and known seams;
- separation of feature work from structural moves;
- source-boundary tests that protect module ownership;
- executable Node-based tests for pure ES module contracts;
- manual smoke testing after changes to browser composition, session or playback;
- transactional local transformation scripts with anchor validation, `--check`
  support and dirty-target protection.

A composition regression during application-event extraction temporarily removed
Media Session setup and player initialization. It was restored immediately and
converted into regression coverage. Startup ordering must therefore be protected
by executable tests rather than source checks alone.

### Phase 2: Extract Web API helpers and routers

Status: completed for the first Web refactor pass.

The completed pass moved pure or nearly pure operations out of
`fluxtuner/web/app.py`:

- admin user payload/count helpers;
- dashboard payload building;
- public stats payload shaping;
- station payload shaping;
- playlist/favorite/history request validation.

The final shape uses focused helper/action modules plus FastAPI routers instead
of one broad `services.py` module. This keeps Web licensing boundaries clear
while reducing `app.py` size without changing the external API.

### Phase 3: Split storage by domain without changing SQLite

Status: completed.

The storage split introduced focused ownership for:

```text
fluxtuner/core/public_stats.py
fluxtuner/core/password_changes.py
fluxtuner/core/users.py
fluxtuner/core/profiles.py
fluxtuner/core/stations.py
fluxtuner/core/favorites.py
fluxtuner/core/history.py
fluxtuner/core/playlists.py
```

`fluxtuner/core/db.py` intentionally retains:

- SQLite connection setup;
- schema creation and migrations;
- default user/profile bootstrap;
- compatibility wrappers for existing call sites.

Focused boundary tests verify that the extracted domain modules and the
compatibility wrappers operate on the same storage. Schema, migration and
bootstrap logic should only be changed in a dedicated, carefully scoped PR.

Storage tests now follow the same ownership boundaries:

```text
tests/test_stations_storage.py
tests/test_favorites_storage.py
tests/test_history_storage.py
tests/test_playlists_storage.py
tests/test_profiles_storage.py
tests/test_users_storage.py
tests/test_storage_domain_boundaries.py
```

`tests/test_db.py` is intentionally limited to SQLite connection behavior,
schema creation, migrations, idempotency and default user/profile bootstrap.
Domain persistence behavior belongs in the corresponding `*_storage.py` test
module. `tests/test_storage_domain_boundaries.py` protects compatibility between
direct domain-module calls and the wrappers retained in `db.py`.

Future persistence tests should be added to the matching domain test module.
Schema, migration and bootstrap changes should remain isolated in dedicated,
carefully reviewed PRs.

### Phase 4: Web JavaScript module boundaries

Status: completed and hardened after `v1.0.5`.

The browser client keeps the no-build approach. `static/app.js` is now the
composition root for focused ES modules under `fluxtuner/web/static/js/`.

The completed boundary work includes API access, auth/setup/account-request
flows, dashboard/admin/public stats/health rendering, search, favorites,
playlists, library rendering, playback, Media Session, player debug, theme,
responsive shell, centralized DOM lookup, shared application state, session UI,
navigation, event binding, startup ordering and the late-bound player runtime.

The final hardening pass validates player-runtime attachment, prevents accidental
reattachment, fails fast for invalid early operations and adds executable Node
tests for runtime delegation and bootstrap ordering.

`app.js` should now remain a composition root. Future changes must not extract
additional code solely to reduce line count; they should require a concrete
ownership, lifecycle or testability improvement.

Future JavaScript changes should preserve the no-build module boundary unless a
separate build-pipeline decision is made explicitly.

### Phase 5: Web player state model

Status: completed.

The Web player remains a dedicated browser controller with a hardened late-bound
runtime bridge. Its state is now explicit and internal rather than inferred from
DOM attributes.

The completed model defines:

- supported states: `idle`, `loading`, `playing`, `paused` and `error`;
- allowed transitions between those states;
- `playerBar.dataset.state` as a UI projection rather than a state source;
- one monotonically increasing playback attempt ID;
- the active playback attempt as the only path that confirms successful startup
  and records listening history;
- permanent audio listeners as observers that cannot confirm obsolete attempts;
- deterministic invalidation when playback is paused, stopped, replaced or
  interrupted by connectivity loss;
- lifecycle reconciliation across visibility, `pagehide`, `pageshow`, `online`
  and `offline`;
- conservative connectivity recovery that keeps the station selected in
  `paused` and requires an explicit user resume;
- Media Session state as a projection of player transitions and lifecycle
  reconciliation;
- debug snapshots that expose internal state, attempt IDs, flags, audio state
  and lifecycle context.

Executable Node-based contracts cover the state model, DOM projection,
successful playback, station replacement, stop during startup, pause during
startup, stale `playing` events, lifecycle reconciliation and Media Session
action delegation. Source-boundary tests continue to protect module ownership.

Intentional limits remain:

- FluxTuner does not promise uninterrupted playback through every mobile
  background or lock-screen lifecycle;
- returning online does not automatically restart a stream;
- a paused live stream resumes by opening a new playback attempt;
- retry and buffering policy remain local to the player controller;
- metadata `Now Playing` fetching is not part of this phase.

Phase 5 was completed through these focused PRs:

1. `test: add executable Web player lifecycle contracts`
2. `refactor: define Web player state transitions`
3. `fix: make Web playback attempts deterministic`
4. `fix: reconcile Web player lifecycle state`
5. `docs: complete Web player state model phase`

The goal was not to force mobile lock-screen persistence. The completed model
keeps FluxTuner's internal state coherent and makes resume, restart, stop,
replacement and lifecycle recovery behaviour explicit.

### Phase 6: Revisit metadata `Now Playing`

Status: completed.

The completed Web metadata design keeps network parsing and browser rendering
behind separate, explicit boundaries.

Backend responsibilities now include:

- strict stream URL validation and SSRF protection;
- short connection and read timeouts;
- one cache entry per canonical stream URL;
- background metadata refresh through a coordinator/worker boundary;
- deduplication of concurrent refresh work for the same stream;
- bounded cache state for fresh, empty and failed results;
- failure isolation so metadata errors do not interrupt audio playback;
- a cached metadata endpoint that does not make browser requests block on stream
  parsing;
- administrative diagnostics with aggregate counters only and no sensitive
  stream data.

Browser responsibilities now include:

- an immediate metadata request when playback starts;
- conservative polling every 15 seconds while playback remains active;
- suspension of metadata polling while the document is hidden, followed by an
  immediate refresh when it becomes visible again;
- request-generation and canonical-URL checks that reject stale responses;
- safe `textContent` rendering for station, artist and track values;
- station fallback while track metadata is unavailable;
- forwarding fresh metadata to Media Session without changing playback state;
- a compact responsive Now Playing hierarchy for desktop and mobile;
- accessible icon controls with keyboard and touch support;
- overflow-aware track scrolling only when the rendered title does not fit;
- respect for `prefers-reduced-motion`;
- copying the current artist and track with a private-HTTP clipboard fallback.

The completed architecture intentionally does not add:

- WebSocket or server-sent event delivery;
- metadata persistence or listening-history enrichment;
- remote station or album artwork;
- configurable browser polling intervals;
- automatic playback changes in response to metadata failures.

Phase 6 was delivered as a focused series covering backend safety, cache and
worker coordination, endpoint integration, visible Now Playing rendering, Media
Session updates, diagnostics and final responsive player refinement.

The result keeps metadata optional: playback remains authoritative, metadata
remains cache-backed and best-effort, and failures remain observable without
becoming user-facing audio failures.

## Completed first Web refactor PRs after v1.0.4

1. `docs: add architecture refactor roadmap`
2. Web helper/action extraction for payloads, validation, security, setup,
   dashboard, context, guards, library, admin users/actions, registration and
   password-change flows.
3. Web router extraction for public, auth, library and admin API endpoints.
4. Packaging update for the `fluxtuner.web.routes` package.
5. Web JavaScript module extraction for auth, admin, dashboard, search,
   favorites, playlists, player, Media Session, player debug, theme and shell
   behavior.
6. Mobile Media Session/player hardening and Player debug UX cleanup.
7. Application DOM registry extraction.
8. Browser application-state encapsulation.
9. Session UI coordinator extraction.
10. Navigation coordinator extraction.
11. Application event-binding extraction.
12. Player initialization regression restoration and ordering protection.
13. Application bootstrap extraction.
14. Player runtime bridge encapsulation.
15. Application composition contract hardening with executable Node tests.

The final `app.js` composition series corresponds to pull requests #119 through
#127. It is complete and should be treated as the closing hardening pass for
Phase 4 plus additional Phase 1 safety rails, not as completion of the remaining
Phase 5 player state-model work.

Future structural PRs should remain small enough to review manually and should
not change user-visible behaviour unless explicitly stated. Phase status changes
must be reflected in this roadmap when the corresponding work is merged.

## Next interface audit sequence

The first TUI audit and extraction sequence is complete. The next structural
work should continue with another documentation-only audit before moving code:

1. Audit `fluxtuner/gui/window.py` using the same responsibility-map and
   contract-first approach used for the TUI.
2. During the GTK audit, review the Flatpak sandbox permissions in
   `flatpak/io.github.pitill0.Fluxtuner.yml` and verify whether each current
   `finish-args` entry remains necessary:

   ```yaml
   - --share=network
   - --share=ipc
   - --socket=fallback-x11
   - --socket=wayland
   - --socket=pulseaudio
   - --device=dri
   ```

   Any permission reduction must be validated against GTK startup, Wayland and
   X11 fallback behavior, audio playback, rendering and network radio access.
3. Introduce cross-interface application services only after equivalent behavior
   and duplicated orchestration have been demonstrated in at least two
   interfaces.

## Issue #315: Web HTTP composition boundaries

The first extraction moves HTTP plumbing out of `create_app`:

- `fluxtuner/web/middleware.py` resolves and renews sessions off the event loop
  and applies private API and legacy static cache headers. Registration keeps
  cache policy outside session resolution, preserving response ordering.
- `fluxtuner/web/static_routes.py` publishes optional static snapshots, mounts
  versioned assets before legacy assets, resolves icon aliases and prepares
  identity/gzip HTML responses with conditional GET/HEAD handling.

`create_app` retains optional Web dependency handling, application lifespan,
metadata coordinator ownership, setup/dashboard endpoints and router wiring.
The extracted modules are imported within its existing optional-dependency
boundary. Static publication fallback and the public HTTP routes are preserved.

Executable HTTP tests cover GET/HEAD parity and revalidation with legacy and
versioned assets, session renewal ordering and cache policy on error responses.
Existing auth, setup, session and static publication contracts remain applicable.

The Web extraction and CLI dispatch decomposition are incremental steps of #315.
PLS parsing is also decomposed. The C901 policy below records the remaining
reviewed debt without expanding these extractions into unrelated interfaces.
The pre-extraction C901 baseline at threshold 10 reports `create_app` at 41,
CLI `main` at 31 and `parse_pls` at 29, with 26 functions above 10 overall.


### CLI command dispatch

`fluxtuner/__main__.py` separates parser construction, profile commands,
diagnostic commands, library transfer commands, theme resolution and interface
launching into focused private helpers. Existing public helpers and the command
entrypoint remain in their original module.

The dispatcher preserves command precedence: positional Web administration,
profile changes, diagnostics, library import/export, theme/player selection,
then CLI, GTK or default TUI. Profile resolution still occurs before terminal
profile/diagnostic/library options, and theme persistence still precedes player
validation. Existing messages and exit statuses remain unchanged.

Regression coverage exercises competing terminal options, early exit without
player probing, CLI-over-GTK precedence, GUI backend forwarding and optional
dependency/unknown-command errors through `main`.


### PLS import parsing

`parse_pls` composes focused helpers for bounded UTF-8 decoding, header/key
records, PLS v2 fields, station validation and preview construction. Parsing
remains free of database and network I/O.

Byte/line/station bounds, first-key-wins handling, indexed station ordering,
URL deduplication, validation messages and diagnostic line numbers/order are
preserved. M3U parsing, format dispatch and persistence behavior are unchanged.
Contracts include malformed fields mixed with valid stations, source-line
diagnostics, invalid input types/encoding and declared/indexed station limits.


### Complexity policy

Ruff C901 is enabled with a general maximum of 15. Prefer functions at or below
10 when adding or extracting behavior; the new CLI and PLS helpers meet that
target. Existing behavior is not rewritten solely to satisfy a numerical limit.

Seven reviewed production functions and ten existing GTK contract tests exceed
15. Each has a function-level C901 annotation and a named entry with its measured
ceiling and justification in `docs/complexity-baseline.json`. File-wide C901
exemptions are not used.

`tests/test_complexity_policy.py` runs an isolated C901 scan over the whole Python
lint scope, including tests, with noqa disabled.
It rejects new exempt functions, growth beyond an existing function's ceiling,
duplicate/ambiguous identities and obsolete exception entries. This makes the
baseline a ratchet rather than a blanket allowance: reduce ceilings after
improvement and remove both annotation and entry once a function reaches 15.
Any additional exception or ceiling increase requires explicit review and a
documented reason; do not regenerate the baseline to make a failure disappear.

The retained exceptions cover search orchestration, M3U stateful parsing, two
GTK lifecycle entrypoints, bounded HTTP body framing, theme property dispatch
and the remaining Web setup/dashboard/lifespan composition. Their executable
contracts remain in place. GTK decomposition continues separately under #316.


The ten retained GTK test exceptions contain inline widget doubles whose nested
callables contribute to C901. Their bodies and assertions are preserved. The
same named-function budgets apply to these tests; the policy does not disable
C901 across the test suite or across the context-menu test module.


## Issue #316: GTK controller workstream

Status: recording, ripping and shutdown integrated; complete library extraction in progress.

The first GTK playback/metadata/search/view-state workstream remains complete.
Issue #316 is a second bounded sequence for retained recording, ripping,
shutdown and library orchestration; it does not reopen the completed work solely
to reduce line count. The historical next-audit recommendations above describe
the original sequence. The current responsibility map and new sequence live in
`docs/gtk-orchestration-audit.md`.

The baseline at `054156b` is 2,760 lines and 155 direct `MainWindow` methods.
Nukleuz real-binding validation runs 332 GTK contracts without skips using
compatible system PyGObject/GTK bindings alongside the isolated project `.venv`.
`scripts/run_gtk_tests.py` provides a repeatable entrypoint. Native-binding tests,
manual desktop checks and the complete quality/security gate remain distinct.

Proceed through recording actions, ripping/monitoring, quit/shutdown lifecycle,
then library boundaries and a measured reassessment. Each extraction must
preserve behavior, define its state/runtime owner and lower the measured window
budget when responsibilities move. Keep #316 open across these bounded PRs;
Flatpak permissions, Brynse version changes and Web work stay independent.


The first extraction introduces `RecordingController` for recording request/start
and explicit stop/finalization coordination without GTK imports or duplicated
session state. Selection, widgets, projection and the shutdown guard remain in
`MainWindow`; asynchronous shutdown continues through its existing worker.
See the GTK audit document for ownership and validation details. This stage does
not complete #316.


### Issue #316 progress after PR #322

The recording-action controller and real-GTK runner are integrated. The next
bounded extraction moves ripping actions, cached availability and UI monitoring
to `RippingController`, sharing the authoritative `RippingService`. Its source
is canceled by its owner during the existing asynchronous shutdown sequence.
Profile resolution, menu widgets and quit decisions remain in the window.

The ripping baseline passed 114 contracts with real GTK; its seven optional
Brynse contracts were initially skipped. The unchanged pinned Brynse revision
was then prepared in a temporary dependency directory: all 406 GTK/ripping
contracts passed without skips. Manual targeted ripping, stop and quit
cancellation/finalization were confirmed, with two MP3 outputs inspected.
Dependency/version updates stay outside this refactor. After the full gate
and second-stage PR, continue with the quit/shutdown controller, then
reassess library actions.
Keep #316 open across the bounded PRs.


### Issue #316 progress after PR #323

Recording and ripping controller stages are merged. The real-GTK shutdown
baseline on Nukleuz passed all 157 focused lifecycle contracts without skips.
The next bounded change introduces `ShutdownController` as the single owner
of confirmation/shutdown state, worker coordination, the completion callback,
the 200 ms polling source and the monotonic 12 second warning deadline.

`MainWindow` keeps GTK dialogs, close-to-tray policy, the window close adapter
and cancellation of its own UI activity. RecordingManager and RippingService
remain authoritative for sessions/jobs. The existing asynchronous FFmpeg stop
and nonblocking ripping-finalization helpers are reused without modification.
The ripping controller and playback/recording adapters consult this same
shutdown owner; no parallel shutdown flag or worker state is added.

Controller lifecycle contracts run without GTK; native dialog, close-to-tray,
window delegation and real FFmpeg-stop integration remain separately covered.
The extraction report records post-format size and direct-method metrics.
Manual shutdown checks were confirmed with FFmpeg alone and with FFmpeg plus
Brynse active. Both GTK instances exited normally; four session files passed
ffprobe. This short run produced no Brynse track outputs; track-output validation
from the previous stage remains separate. The full final gate follows this update. Continue to library actions after this bounded PR; keep #316
open. Web recovery, dependency/version changes and Flatpak policy remain separate.


### Issue #316: complete library boundary after PR #324

The next stage groups favorites, history, persistent playlists, favorite-tag
filters, custom-station editing/creation and import refresh in one PR. The
Nukleuz baseline passed all 433 GTK/core-library contracts with real bindings.
The measured surface covers 49 related MainWindow methods, including widgets,
dialogs, actions and view projection; it is a responsibility map, not a target
to remove every interface adapter.

`LibraryController` owns storage access, profile lookup, playlist picker creation,
custom-station transactions and the single favorite URL cache without importing
GTK. `LibraryPanel` owns library widgets, dialogs, handlers and library-view
transitions. Explicit live-state ports connect it to the station list; stations,
selection, current playback and ViewState remain single authoritative objects.
The GTK parent is used only for transient dialogs/importers, not as an opaque
application dependency.

MainWindow retains three small station-view adapters and composes the panel.
It decreases from 2,525 lines/153 direct methods to 1,690 lines/107 methods
after extraction and the GTK tag projection fix. This stage removes 46 methods from the
window together; it does not split the library into separate favorites,
history and playlist PRs. Total production line count is not used as a claim
of simplification: explicit boundaries and wiring introduce some additional
code while removing the library's breadth from MainWindow.

Existing behavior contracts follow their owners with their assertions retained.
Additional contracts use real SQLite storage for profile isolation, cached
favorite identity, playlist deletion/membership, custom-station transactions
and shared live selection. A native-GTK window-composition contract exercises
library button signals and favorite editing; it is explicitly skipped without
real GTK and must pass in the native run. Manual library checks were confirmed after block 282, with the GTK tag
projection correction confirmed after block 283. The full final quality/security
gate follows this documentation update.

After this complete library PR, reassess the remaining station-list/layout and
context-menu boundaries. Keep #316 open until that reassessment and the agreed
workstream are complete. Web work, Brynse dependency changes and Flatpak
permissions remain separate.


Manual checks also exposed a pre-existing GTK tag-display gap. Personal favorite
tags were saved correctly but absent from station rows and Now Playing details.
The library stage includes a scoped GTK projection fix combining stream and
personal tags without changing storage or other interfaces. Its manual recheck
was confirmed by the user after block 283; the full final gate follows this update.
