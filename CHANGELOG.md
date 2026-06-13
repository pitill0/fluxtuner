# Changelog

All notable changes to FluxTuner will be documented in this file.

The format is inspired by Keep a Changelog, and this project uses semantic versioning where possible.

---

## [Unreleased]

### Added

- Nothing yet.

### Changed

- Nothing yet.

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
