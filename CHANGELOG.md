# Changelog

All notable changes to FluxTuner will be documented in this file.

The format is inspired by Keep a Changelog, and this project uses semantic versioning where possible.

---

## [Unreleased]

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
- README screenshots for TUI and GUI workflows.
- Added live ICY stream metadata polling in the GTK GUI.
- Added `--list-players` to inspect supported and available playback backends.

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
