# Architecture refactor roadmap

FluxTuner has grown from a local internet-radio app into a multi-interface
project with TUI, GTK, CLI and Web/server mode. This roadmap describes an
incremental refactor path for the post-`v1.0.4` series.

The goal is not a rewrite. The goal is to make the existing behaviour easier to
reason about, test and extend while keeping releases small and reversible.

## Current pressure points

### Large interface modules

Several interface modules carry many responsibilities at once:

- `fluxtuner/web/app.py` owns FastAPI app creation, auth guards, setup,
  dashboard, admin user management, password-change requests, search, history,
  favorites, playlists and station payload shaping.
- `fluxtuner/web/static/app.js` owns navigation, auth, admin UI, dashboard,
  Radio Browser search, favorites, playlists, browser playback, Media Session
  integration, player debugging and theme/mobile shell behaviour.
- `fluxtuner/web/static/styles.css` owns the full Web visual system and has
  become large enough that feature-local CSS is hard to audit.
- `fluxtuner/tui.py` and `fluxtuner/gui/window.py` contain broad UI orchestration
  plus player, metadata, favorites, history and playlist behaviour.

These files are still workable, but new features increasingly require scanning a
large surface area.

### Core storage concentration

`fluxtuner/core/db.py` is the single SQLite foundation for local and Web data.
It currently owns schema creation/migrations, users, approval state, password
change requests, profile ownership, public stats, station records, favorites,
history and playlists.

Keeping one SQLite backend is fine, but the module now mixes multiple domains.
Future changes should reduce the risk of touching unrelated storage code.

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

## Proposed incremental phases

### Phase 1: Audit and safety rails

- Keep `make gate` green after every small patch.
- Add tests that detect accidental duplicate Web player functions or duplicated
  Media Session handlers.
- Document current module responsibilities and known seams.
- Avoid feature work in the same commits as structural moves.

### Phase 2: Extract Web API service helpers

Start with pure or nearly pure operations currently embedded in
`fluxtuner/web/app.py`:

- admin user payload/count helpers;
- dashboard payload building;
- public stats payload shaping;
- station payload shaping;
- playlist/favorite/history request validation.

Candidate destination:

```text
fluxtuner/web/services.py
```

This keeps Web licensing boundaries clear while reducing `app.py` size without
changing the external API.

### Phase 3: Split storage by domain without changing SQLite

Keep `fluxtuner/core/db.py` as the schema and low-level SQLite foundation, then
move domain-specific persistence functions behind small modules where it helps:

```text
fluxtuner/core/users.py
fluxtuner/core/library.py
fluxtuner/core/playlists.py     # existing higher-level module can grow here
fluxtuner/core/history.py       # existing higher-level module can grow here
```

Do this gradually. Avoid moving schema definitions until the behaviour is well
covered.

### Phase 4: Web JavaScript module boundaries

If the no-build Web approach remains important, prefer small plain JavaScript
files loaded in order rather than introducing a bundler immediately.

Potential split:

```text
static/js/state.js
static/js/api.js
static/js/player.js
static/js/admin.js
static/js/library.js
static/js/navigation.js
static/js/main.js
```

Only do this after the player and admin flows are stable, because moving large JS
blocks too early can create noisy diffs.

### Phase 5: Web player state model

Introduce an explicit player controller/state object that owns:

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

## Suggested first PRs after v1.0.4

1. `docs: add architecture refactor roadmap`
2. `web: extract admin payload helpers`
3. `web: extract dashboard/public stats helpers`
4. `web: extract station payload helpers`
5. `web: add player controller design notes`

Each PR should be small enough to review manually and should not change user
visible behaviour unless explicitly stated.
