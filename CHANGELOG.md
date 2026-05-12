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
