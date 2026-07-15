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
audio element and Media Session conservatively. Connectivity recovery keeps the
station selected and requires an explicit resume instead of restarting playback
automatically.

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
- TUI orchestration safety contracts followed by focused boundary work, based
  on `docs/tui-orchestration-audit.md`;
- GTK orchestration auditing, including a least-privilege review of
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

The next structural work should begin with documentation-only audits rather than
immediate code movement:

1. Audit `fluxtuner/tui.py` responsibilities and identify focused seams with
   matching safety tests.
2. Extract the first TUI boundary only where ownership, lifecycle or testability
   clearly improves.
3. Audit `fluxtuner/gui/window.py` using the same approach.
4. During the GTK audit, review the Flatpak sandbox permissions in
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
5. Introduce cross-interface application services only after equivalent behavior
   and duplicated orchestration have been demonstrated in at least two
   interfaces.
