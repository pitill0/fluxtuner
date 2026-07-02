# Changelog

All notable changes to FluxTuner will be documented in this file.

The format is inspired by Keep a Changelog, and this project uses semantic versioning where possible.

 ---

## Unreleased

### Added

- Nothing yet.

### Changed

- Nothing yet.

### Fixed

- Nothing yet.

## [1.0.4] - 2026-07-02

### Added

- Added an admin-only user deletion API that removes the user and related Web sessions, favorites, playlists, history and password change requests.
- Added a compact Admin user danger zone with strong confirmation for deleting a user and all related data.
- Added the total number of approved Web users to anonymous public stats.
- Added an admin-only opt-in Web player debug panel with event snapshots, copy/export controls and downloadable logs for mobile playback diagnostics.

### Changed

- Deduplicated Web player and Media Session logic so browser, mobile and external media controls use a single playback flow.
- Improved the Admin player debug panel layout on mobile so it no longer widens the page.
- Kept external Media Session stop actions conservative by pausing and preserving the current station instead of clearing playback state.

### Fixed

- Fixed admin user management lacking a real destructive-delete path for removing stale or test accounts.
- Fixed Web player Media Session handlers being registered through overlapping paths, which could cause inconsistent playback behavior after search, pause, resume or external controls.
- Fixed public stats copy and rendering so anonymous platform usage can include user count without exposing usernames, sessions, IP addresses or timestamps.

### Security

- User deletion remains admin-only, CSRF-protected and blocks self-delete.
- Public user stats expose only an anonymous aggregate count of approved active users with passwords configured.
- Player debug logging is local, opt-in and admin-facing; it is intended for diagnostics and can be disabled per browser.

## [1.0.3] - 2026-07-01

### Added

- Added anonymous public Web activity stats under the login screen.
- Added a public Web stats endpoint with aggregate play, favorite and playlist counts.
- Added visible Web password requirements to setup, access request and password change forms.

### Changed

- Polished the public Web entry experience with a clearer intro, compact login card and improved stats layout.
- Improved Web button styling across dark and light themes.
- Improved mobile live-stream handling by treating external media controls as soft pauses and restarting live streams when playback resumes.

### Fixed

- Fixed public Web dialog Escape handling and hover contrast regressions.
- Fixed Web login form spacing so username, password and submit controls do not overlap.

### Security

- Public stats expose only anonymous aggregate counts and top station names, without users, profiles, stream URLs, IPs or timestamps.

## [1.0.2] - 2026-07-01

### Added

- Added Web password change requests for private server deployments.
- Added a public password change request form where users choose a new password that only becomes active after administrator approval.
- Added admin UI actions to approve or reject pending password change requests.

### Changed

- Non-admin users with a pending password change request are prevented from logging in with the old password until the request is resolved.
- Active sessions for non-admin users are revoked when a password change request is created.
- Standardized visible Web timestamps as `YYYY-MM-DD HH:mm` in the user's local browser time.

### Security

- Password change requests store only password hashes, never plaintext passwords.
- Public password change requests use a generic response to avoid revealing whether an account exists.
- Administrator accounts are not blocked through the public password change request flow; admin recovery remains a CLI/manual operation.

## [1.0.1] - 2026-06-30

### Changed

- Improved the Web player bar contrast, spacing and active playback visibility.
- Styled the external stream action consistently with the rest of the Web controls.
- The authenticated header now shows the user's display name when available instead of the internal username.
- Register and playlist dialogs are now scrollable on small mobile screens.

### Fixed

- Fixed hidden Web dialogs and authenticated header controls being displayed incorrectly on mobile.

### Notes

- This is a Web UX polish release based on early real-world private-server usage.
- No storage migration or authentication model change is required.

## [1.0.0] - 2026-06-30

### Added

- Added a Web dashboard with user library metrics, recent playback, favorite highlights and quick navigation.
- Added admin-only dashboard metrics for total users, new users, pending approvals and compact server health.
- Added public Web account requests that create inactive users pending administrator approval.
- Added Admin approve/reject actions for pending Web users.

### Changed

- Web user state now tracks explicit approval status (`approved`, `pending`, `rejected`, `disabled`) while keeping existing active/inactive behavior compatible.
- Login now reports `Account pending approval.` only when a pending user provides the correct password.
- Full-package mypy validation is now part of the release quality gate and CI workflow.
- Station action links in the Web UI now use button-style presentation for visual consistency.

### Security

- Hardened Web authentication flows by requiring CSRF protection for logout.
- Hardened public account registration, setup and admin user creation with input size limits and safer rate-limit boundaries.
- Restricted Web search to authenticated sessions in private server mode.
- Restricted station stream URLs accepted by Web library mutations to absolute `http` or `https` URLs.
- Hardened Web client handling of external station and homepage URLs.
- Added explicit playlist name length limits across Web API routes and client-side validation.

### Documentation

- Reviewed and updated 1.0 Web, multi-user, security, release and smoke-test documentation.
- Clarified that favorites act as the saved-station library used by manual playlists in the 1.0 data model.

## [0.9.0] - 2026-06-28

### Added

- Added real Web/server multi-user authentication with local username/password accounts.
- Added Argon2id password hashing for Web/server users.
- Added server-side web sessions with opaque HttpOnly cookies and hashed session tokens.
- Added CSRF protection for authenticated Web API mutations.
- Added first-run web setup flow for creating the initial administrator.
- Added setup-token protection for remote first-run setup with `FLUXTUNER_WEB_SETUP_TOKEN`.
- Added authenticated Web API access for favorites, playback history and manual playlists.
- Added user-owned profile resolution for Web/server mode.
- Added Web admin API endpoints for listing users, creating users, resetting passwords, activating/deactivating users and granting/removing admin access.
- Added Web admin UI for browser-based user management.
- Added a responsive Web app shell with compact hamburger navigation, a centered player, isolated Admin view and light/dark theme toggle.
- Added a playlist picker in the Web UI so stations can be added to existing or new playlists without browser prompts.
- Added emergency CLI commands for Web user administration through `fluxtuner web users ...`.
- Added session revocation when passwords change or users are deactivated.
- Added protection against deactivating or demoting the last active configured administrator.
- Added `FLUXTUNER_WEB_SECURE_COOKIES` and `FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS` configuration.
- Added secure Web deployment documentation with HTTPS, reverse proxy, setup-token, backup and post-deploy checklists.
- Added split licensing documentation for MIT core/local components and non-commercial Web/server components.
- Added FluxTuner trademark and branding policy documentation.

### Changed

- Web/server library data routes now require authentication.
- Web/server mode now treats profiles as owned by authenticated users instead of global profile names.
- The Web UI now shows login, first-run setup and administrator sections according to session state.
- The Web admin CLI implementation was moved into `fluxtuner/web/admin_cli.py` to keep the Web/server licensing boundary clear.
- Documentation now distinguishes local/core FluxTuner components from Web/server multi-user components.
- Project metadata and README license information now describe the split licensing model.

### Fixed

- Prevented stale admin user data from remaining visible in the Web UI after logout or session loss.
- Fixed deleting Web favorites by raw stream URL.
- Ensured self password reset and self deactivation revoke the current admin session.
- Ensured inactive Web users cannot log in.
- Ensured password hashes and session tokens are not exposed by Web API responses.

## [0.8.0] - 2026-06-27

### Added

- Added multi-profile support for favorites, playback history and manual playlists.
- Added persistent active profile support.
- Added `--profile NAME` for profile-aware CLI commands.
- Added `--set-active-profile`, `--show-active-profile` and `--clear-active-profile`.
- Added profile-aware import/export for favorites and manual playlists.
- Added profile-aware behavior to the legacy numbered CLI favorites flow.
- Added profile-aware behavior to the Textual TUI, GTK GUI and Web mode.
- Added Web API `?profile=NAME` override support for profile-aware endpoints.
- Added dynamic favorite tag playlist support scoped by profile.

### Changed

- Favorites, playback history and manual playlists are now resolved using profile-aware storage.
- Profile resolution now follows this order: explicit profile, persisted active profile, internal default profile.
- The Web API now uses the persisted active profile by default when no `?profile=NAME` override is provided.
- Documentation now describes the feature as multi-profile support rather than multi-user support.

### Notes

- Profiles separate favorites, manual playlists and playback history by context.
- Profiles are not user accounts and do not provide authentication, permissions or per-user isolation.
- This release prepares the storage and interface foundation for future true multi-user support.

## 0.7.1 - 2026-06-27

### Added

- Added internal profile-aware core helpers for favorites, playback history and manual playlists.
- Added `--list-profiles` to inspect known FluxTuner profiles from the CLI.

### Changed

- Centralized profile resolution for core library storage while keeping the existing default-profile behavior unchanged.

### Fixed

- Nothing yet.

---

## 0.7.0 - 2026-06-26

### Added

- Added a SQLite storage foundation with schema migrations and an internal `default` profile.
- Added SQLite persistence helpers for normalized stations, favorites, playback history and manual playlists.

### Changed

- Moved favorites, playback history and manual playlists from active JSON storage to `fluxtuner.db`.
- Kept existing public APIs and JSON import/export commands compatible while migrating legacy JSON files conservatively.
- Updated storage documentation to describe SQLite as the primary library store.

### Fixed

- Preserved history snapshot compatibility during JSON-to-SQLite migration.

---

## 0.6.0 - 2026-06-26

### Added

- Added FluxTuner Web, a browser-based web/server mode for searching, playing, favoriting and organizing internet radio stations.
- Added browser audio playback using the web client's native audio engine.
- Added web access to playback history, favorites and manual playlists.
- Added `fluxtuner-web` as a dedicated web/server entry point.
- Added optional web dependencies through the `web` extra.
- Added `FLUXTUNER_DATA_DIR` to support isolated data directories for web, containers, demos and tests.
- Added container support with `Containerfile`, `.dockerignore`, `compose.yaml` and persistent `/data` storage.
- Added web and container documentation.

### Changed

- Updated the project description and documentation to include the new web/server mode alongside the TUI and GTK interfaces.
- Improved the mobile web layout so search, playback and library actions are easier to use from phones.
- Polished the web player bar, station cards and server tools layout.
- Kept server health/debug tools available without making them the primary hero action.

### Fixed

- Relaxed web station payload handling so Radio Browser responses and saved station records are accepted more reliably.
- Cleaned up web styles after iterative layout changes.

---

## 0.5.0 - 2026-06-24

### Added

- Added a Textual TUI keyboard shortcuts help modal, available with `?`.

### Changed

- Reduced the visible TUI footer shortcuts to the most important actions.

### Fixed

- Nothing yet.

---

## [0.4.0] - 2026-06-13

### Added

- Added player capability declarations for playback backends.
- Added lightweight `mpg123` and `ogg123` playback backends.
- Added station/backend compatibility checks for specialized backends.
- Added player backend diagnostics to `--list-players`.
- Added install hints for missing playback backends.
- Added `--doctor` runtime diagnostics for support and troubleshooting.
- Added tests covering player capability summaries, backend install hints, legacy CLI compatibility and doctor path diagnostics.

### Changed

- Updated automatic backend selection to include `mpg123` and `ogg123` after `mpv` and `ffplay`.
- Improved Textual TUI and GTK GUI behavior so incompatible stations are filtered or blocked when specialized backends are selected.
- Improved legacy numbered CLI behavior so searches, favorites and random favorite playback respect backend compatibility.
- Updated Flatpak and AppStream metadata to describe backend detection and compatibility generically.
- Expanded player backend documentation, usage notes and troubleshooting guidance.
- Clarified GUI wording and removed stale experimental/MVP language.

### Fixed

- Prevented specialized backends from attempting playback for clearly incompatible stations.
- Improved unsupported-backend messages for saved stations and specialized backend flows.
- Kept saved favorites, history and playlists intact while applying compatibility checks at playback/search time.
- Improved documentation consistency after adding new backends and runtime diagnostics.

---

## [0.3.0] - 2026-06-01

### Added

- Added a shared `SearchService` used by both the Textual TUI and GTK GUI.
- Added structured debug logging for playback, search, metadata, persistence and import/export flows.
- Added `SECURITY.md` with responsible disclosure guidance and project security scope.
- Added development documentation with local setup, validation commands, testing guidance and troubleshooting.
- Added release workflow documentation and tag-triggered release artifact automation.
- Added UI smoke tests for the Textual TUI and GTK GUI entry points.
- Added regression tests for search caching, repeated filtered searches and live search cancellation.
- Added gradual `mypy` typing checks for selected stable modules.

### Changed

- Split TUI table, detail and theme helper logic into dedicated modules.
- Routed TUI and GTK GUI station searches through the shared search service.
- Improved Flatpak sandbox permissions and documented the purpose of remaining permissions.
- Added upper bounds to runtime dependencies to avoid untested future major versions.
- Expanded CI to cover Python version matrix checks, package builds, dependency auditing, Bandit security checks and mypy.
- Improved architecture, development, security and release documentation.

### Fixed

- Hardened imported favorites and playlists validation before persistence.
- Added atomic JSON writes for local user data.
- Improved persistence error reporting without exposing unnecessary local details.
- Hardened network/API failure handling for search and metadata flows.
- Limited ICY stream metadata reads to avoid excessive remote data processing.
- Improved player executable and stream URL validation before external player execution.
- Improved player backend registry typing and availability contracts.
- Improved test isolation around player backends, persistence, cache and UI startup paths.

### Security

- Added Bandit static security analysis to CI.
- Added dependency auditing with `pip-audit`.
- Reviewed Flatpak permissions and removed broader or unnecessary manifest-level overrides.
- Strengthened validation around imports, stream metadata, external player execution and network failures.

---

## [0.2.9] - 2026-05-25

- Fixed TUI station details rendering and side-panel layout after line breaks.

---

## [0.2.8] - 2026-05-20

### Changed

- Improved GTK GUI side-panel navigation by grouping Favorites and History under a Library section.
- Improved GTK GUI status messages for search, favorites, history and tag playlist views.

---

## [0.2.7] - 2026-05-19

### Added

- Added a History view to the GTK GUI, matching the existing TUI history flow.

### Fixed

- Fixed GTK GUI playback history persistence so played stations are available from the shared history.

---

## [0.2.6] - 2026-05-18

### Added

- Added pytest coverage for player backends, backend selection, cache, paths, history, data usage, stream metadata, API filtering and station helper edge cases.
- Added explicit legacy migration tests for favorites, playlists, history and data usage.
- Expanded automated test coverage across persistence, playback backends and API helpers.
- Added tests for legacy CLI flows, CLI import/export, theme handling, XDG path helpers and base player adapter defaults.

### Changed

- Updated TUI playback semantics so `Space` is Play/Stop instead of Pause/Resume.
- Clarified player backend capabilities: `mpv` supports live volume and mute controls, while `ffplay` is treated as a lightweight Play/Stop fallback.
- Improved `ffplay` backend behavior so unsupported pause/mute controls do not silently pretend to work.
- Improved GUI handling for backends without live volume or mute controls.
- Moved legacy data migrations out of import-time paths and into load/save flows.
- Updated README backend capability notes, keybindings and XDG data storage documentation.
- Improved player backend selection tests and error handling for unavailable or unknown backends.
- Centralized station display helpers for safe name, country, codec, bitrate and tag rendering across CLI, TUI and GUI.
- Hardened the legacy numbered CLI to use resolved station URLs and tolerate older or minimal station records.
- Documented XDG environment variable support for config, data and cache directories.

### Fixed

- Fixed TUI table marker updates to avoid rebuilding the station table and causing visual header glitches.
- Fixed TUI station markers after Play/Stop transitions.
- Fixed restored playback volume handling in TUI and GUI.
- Fixed mute restoration so it only applies to backends with live mute support.
- Fixed `mpv` IPC cleanup when the mpv process exits unexpectedly.
- Fixed favorites, playlists, history and usage tests so they cannot read real user legacy files.
- Fixed player adapter docstrings that were previously placed after `raise`/`return` statements.
- Fixed TUI station table column reflow/glitches by using stable column keys and fixed column widths.
- Fixed `ffplay` stop/replacement handling so stale process state is cleared reliably and stream replacement can recover from stop failures.
- Removed unused GUI low-level player command handling and clarified live volume behavior.

---

## [0.2.5] - 2026-05-14

### Changed

- Centralized station helper logic shared by TUI and GTK GUI.
- Improved player backend interface consistency.
- Made GTK imports lazy so TUI usage does not require GUI imports.
- Made legacy user data migration safer by preserving old files.
- Improved configuration defaults handling.

### Fixed

- Preserved resolved station URLs during station normalization.
- Fixed project version metadata consistency.
- Fixed remaining Ruff findings across the package.
- Fixed CI quality checks for push and pull request workflows.

### Added

- GitHub Actions CI for Ruff and Python compile checks.

---

## [0.2.2] - 2026-05-12

### Changed

- Add Flatpak support

## [0.2.1] - 2026-05-08

### Changed

- Improved TUI/GUI parity for playback, favorites and stream information.
- Unified TUI playback behavior with a contextual Play/Stop side-panel control.
- Improved TUI station markers with combined playback/favorite indicators (`▶`, `★`, `▶★`).
- Improved TUI favorite details with visible favorite status, custom tags and action hints.
- Improved GUI favorite editing layout by separating add and edit workflows.
- Replaced emoji mute labels in the GTK GUI with portable text labels for better Linux compatibility.
- Removed hardcoded default search text so search fields start empty with placeholder text.

### Fixed

- Fixed GUI favorite tag editing persistence.
- Fixed GUI favorite name/tag editing false-positive save behavior.
- Fixed TUI station markers not refreshing immediately after playing from favorites or playlists.
- Fixed TUI favorite markers not appearing immediately after adding a favorite from search results.
- Fixed TUI data usage tracking crash when starting playback.
- Fixed TUI data usage display for streams without bitrate metadata by showing an unavailable state.
- Fixed GUI search bar indentation regression after removing default search text.
- Fixed GTK/GDK Vulkan swapchain warning on window close by preferring the Cairo renderer.
- Fixed TUI hard dependency on `mpv` during startup so backend autodetection and `ffplay` fallback work correctly.

---

## [0.2.0] - 2026-05-07

### Added

- GTK4 desktop GUI.
- Responsive GTK dark theme.
- GUI station search with country and minimum bitrate filters.
- GUI favorites controls.
- GUI favorite tag playlist controls.
- GUI random playback by favorite tag.
- GUI side panel with station details.
- GUI session data usage display.
- Estimated data usage tracking core.
- Persistent daily/monthly data usage storage.
- Player lifecycle cleanup when closing the GUI window.
- Modular player backend foundation.
- Live ICY stream metadata polling in the GTK GUI.
- `--list-players` to inspect supported and available playback backends.
- README screenshots for TUI and GUI workflows.

### Changed

- Improved README structure and project presentation.
- Improved TUI/GUI documentation split.
- Improved GUI playback controls with a simplified Play/Stop workflow.
- Improved GUI playback bar layout stability.
- Improved GTK contrast for results lists and controls.
- Improved favorite controls UX in GUI.
- Improved playlist controls UX in GUI.

### Fixed

- Fixed TUI searches using country/minimum bitrate filters without query text.
- Fixed GUI player process continuing after closing the window.
- Fixed GUI data usage live refresh.
- Fixed GTK import/loading issues for stylesheet support.
- Fixed unreadable GTK results table rows in dark theme.
- Fixed GUI layout overflow caused by large side panel content.

---

## [0.1.0] - Initial public release

### Added

- Terminal UI built with Textual.
- Internet radio station search.
- MPV playback integration.
- Favorites support.
- Playlists support.
- Dynamic tag playlists.
- Theme selector with live preview.
- Keybindings for playback, favorites, playlists and themes.
- Import/export commands for favorites and playlists.
- Search cache management.
- Basic project documentation.
- MIT license.

---

## Version notes

### Planned for next development release

- Package/distribution polish.
- GUI settings persistence.
- Improved station history.
- More complete playlist management in GUI.
- Release assets and updated screenshots.
