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
- `fluxtuner/web/static/app.js` is now a small ES module composition layer. It
  wires focused browser controllers under `fluxtuner/web/static/js/` for auth,
  admin, dashboard, search, library views, playlists, browser playback, Media
  Session integration, player debugging and theme/mobile shell behaviour.
- `fluxtuner/web/static/styles.css` owns the full Web visual system and has
  become large enough that feature-local CSS is hard to audit.
- `fluxtuner/tui.py` and `fluxtuner/gui/window.py` contain broad UI orchestration
  plus player, metadata, favorites, history and playlist behaviour.

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

The Web player has improved after `v1.0.4`, but it still relies on DOM state,
`currentStation`, audio element state, Media Session state and several flags.
A clearer model would make future changes safer, especially around browser and
mobile lifecycle behaviour.

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
- `player.js`, `media-session.js` and `player-debug.js` for browser playback,
  mobile Media Session handoff and local diagnostics.
- `theme.js` and `ui-shell.js` for theme preference and responsive app shell
  behavior.



Packaging note: new Web subpackages must be included in the setuptools package
list. The router package is currently listed as `fluxtuner.web.routes` in
`pyproject.toml`; keep this in mind when adding new package directories.

Recommended next branches should stay separate:

- search quality/debugging;
- Web CSS/component styling boundaries for `fluxtuner/web/static/styles.css`;
- smaller follow-up storage cleanups only where they reduce risk without moving schema.

## Proposed incremental phases

### Phase 1: Audit and safety rails

- Keep `make gate` green after every small patch.
- Add tests that detect accidental duplicate Web player functions or duplicated
  Media Session handlers.
- Document current module responsibilities and known seams.
- Avoid feature work in the same commits as structural moves.

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

Status: completed in `v1.0.5`.

The browser client now keeps the no-build approach, but `static/app.js` has been
reduced to a small ES module entrypoint that wires focused modules under
`fluxtuner/web/static/js/`.

The current split includes API access, auth/setup/account-request flows,
dashboard/admin/public stats/health rendering, search, favorites, playlists,
library rendering, browser playback, Media Session integration, player debug,
theme preference and responsive shell behaviour.

Future JavaScript changes should preserve the no-build module boundary unless a
separate build-pipeline decision is made explicitly.

### Phase 5: Web player state model

Status: partially completed in `v1.0.5`.

The Web player now lives in a dedicated browser controller with playback
attempt IDs, lifecycle handling, Media Session updates and debug snapshots.
Future work can still simplify the state model further by making requested
state transitions more explicit.

The player controller currently owns:

- current station;
- requested state (`idle`, `loading`, `playing`, `paused`, `error`);
- current playback attempt id;
- audio element reconciliation;
- Media Session metadata/state;
- lifecycle/debug events.

The goal is not to force mobile lock-screen persistence. The goal is to keep
FluxTuner's internal state coherent and make Resume/restart behaviour explicit.

### Phase 6: Revisit metadata `Now Playing`

Only after the previous phases are stable, implement Web metadata with a backend
cache/worker design:

- short timeouts;
- strict URL validation and SSRF protection;
- cache per stream URL;
- frontend polling with conservative intervals;
- safe Media Session metadata updates when available.

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

Future structural PRs should remain small enough to review manually and should
not change user-visible behaviour unless explicitly stated.
