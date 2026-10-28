# FluxTuner Web — Navigation Architecture

Status: UX-01 through UX-04 implemented for v1.4.1
Scope: Responsive application shell and unified library
Implementation: Incremental, without a frontend framework migration

## 1. Objectives

Evolve FluxTuner Web into a coherent application with:

- Consistent navigation across desktop and mobile.
- Clear separation between destinations and actions.
- A unified personal library.
- Persistent playback across navigation transitions.
- Accessible navigation and predictable focus behavior.
- Strict preservation of authorization boundaries.

This document records the implemented navigation architecture and the original UX contract. Some aspirational catalog-card details remain outside the delivered scope.

## 2. Information architecture

### Primary destinations

| Destination | Purpose |
| --- | --- |
| Dashboard | Overview and relevant activity |
| Explore | Station discovery and search |
| My Library | Personal station collections |
| Account | Personal settings and security |
| Administration | Authorized server management |

### My Library destinations

| Destination | Purpose |
| --- | --- |
| Favorites | Saved favorite stations |
| Playlists | User-defined collections |
| My Stations | Manually added stations |
| Remote Catalogs | Subscribed remote collections |
| History | Listening history |

My Stations lists manually added stations in the authenticated user's selected profile.

### Contextual actions

- Add station
- Import stations
- Create playlist
- Subscribe to remote catalog
- Refresh remote catalog
- Unsubscribe from remote catalog

Actions must not be modeled as top-level destinations.

## 3. Navigation state

The target navigation model distinguishes:

- Primary destination.
- Optional library subsection.
- Optional selected entity, such as a playlist or catalog.
- Transient navigation overlay state.
- Authentication and authorization state.

Player runtime state is independent of navigation state.

The active destination must have one authoritative source
of truth. Controllers must not maintain competing copies
of the active navigation state.

## 4. Responsive behavior

### Desktop

- Collapsible sidebar with visible active destination.
- Section labels remain understandable when expanded.
- Collapsed controls expose accessible names.
- Main content adapts without horizontal overflow.
- Player remains available during navigation.

### Mobile

- Navigation drawer with a maximum of two menu levels.
- Explicit Back action for nested menu sections.
- Escape closes the drawer when appropriate.
- Focus is restored to the navigation trigger on close.
- Opening the drawer does not interrupt playback.
- Closing the drawer does not reset the content view.

### Shared behavior

- Authentication controls destination availability.
- Administration is only available to authorized users.
- The currently active destination is exposed accessibly.
- Navigation actions do not discard unsaved input silently.
- Normal navigation does not restart audio playback.

## 5. Browser navigation

Target behavior:

- Back and Forward restore meaningful application views.
- Deep links must not bypass authentication or authorization.
- Reloading a supported destination restores the view
  when the user is authorized.
- Transient dialogs do not automatically become browser
  history entries.
- Logout clears access to protected destinations.
- Stale asynchronous results must not overwrite a newer view.

Supported destinations use browser-history state and deep-link restoration, subject to authentication and session checks.

## 6. Remote catalog navigation

The delivered UX-03 allows users to:

- List their subscribed catalogs.
- Identify catalog cards by their source ID and revision.
- Open a catalog and browse its stations.
- Refresh and review changes before confirmation.
- Unsubscribe without deleting independent user data.

Catalog views must respect the current user's profile and
existing subscription authorization contracts.

## 7. Compatibility constraints

Preserve:

- FastAPI routes and existing security boundaries.
- Current modular JavaScript controllers.
- Light and dark themes.
- User profiles, favorites and playlists.
- Remote subscription preview/confirmation semantics.
- Player runtime and Media Session integration.
- Initial setup and unauthenticated entry.
- Administrative authorization checks.
- Recovery-code and other modal interactions.

No schema migration is planned solely for UX-01 or UX-02.

## 8. Accessibility contract

The implementation must verify:

- Keyboard navigation and visible focus.
- Accessible names for icon-only controls.
- Correct expanded and current states.
- Predictable focus after navigation or drawer dismissal.
- Escape behavior with dialogs and navigation overlays.
- Responsive behavior at narrow viewport widths.
- Reduced-motion preferences.
- No navigation overlay obscuring critical dialog actions.

## 9. Acceptance test matrix

| Scenario | Expected behavior |
| --- | --- |
| Desktop navigation | Destination loads, active state updates |
| Collapsed sidebar | Destinations remain accessible |
| Mobile drawer | Open, enter subsection, Back, close |
| Keyboard | All destinations reachable without mouse |
| Browser Back | Previous supported destination restored |
| Browser Forward | Next supported destination restored |
| Playback | Continues through normal navigation |
| Logout | Protected navigation becomes unavailable |
| Admin access | Hidden and blocked for non-admin users |
| Session change | Stale private views are invalidated |
| Catalog list | Only owned subscriptions are accessible |
| Catalog detail | Stations are discoverable and playable |
| Catalog refresh | Existing confirmation security preserved |
| Theme switching | Navigation works in both themes |
| Recovery dialogs | No stacking or focus regression |
| Mobile layout | No unexpected horizontal scrolling |

## 10. Delivery sequence

UX-01:
- Approve information architecture and state contract.
- Identify compatibility and test migration requirements.

UX-02:
- Implement shared navigation state and responsive shell.
- Validate playback, permissions and browser navigation.

UX-03:
- Implement unified library and catalog browsing.
- Preserve current import and subscription operations.

UX-04:
- Complete accessibility, responsive and regression checks.
- Run real desktop/mobile tests on Nukleuz.

## 11. Release gate

UX-01 through UX-04 were integrated before v1.4.1 release preparation. Release validation continues to require automated tests, installed-package checks, CI and manual desktop/mobile verification.
