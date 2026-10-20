# Usage Guide

This guide covers installing, running and configuring FluxTuner.

## Requirements

FluxTuner requires:

- Python 3.11 or newer.
- At least one playback backend:
  - `mpv` recommended for broad stream compatibility and live controls.
  - `ffplay`, provided by FFmpeg, as a broad fallback.
  - `mpg123` as an optional lightweight MP3/MPEG backend.
  - `ogg123`, provided by vorbis-tools, as an optional lightweight Ogg/Vorbis/Opus-style backend.
- A terminal emulator with good Unicode support for the TUI.
- FFmpeg if you want to use local stream recording.

The GTK desktop GUI also requires GTK4 and PyGObject.

## Install player backends

### CRUX Linux

```bash
sudo prt-get depinst mpv
sudo prt-get depinst ffmpeg
sudo prt-get depinst mpg123
sudo prt-get depinst libao vorbis-tools
```

### Debian / Ubuntu

```bash
sudo apt install mpv ffmpeg mpg123 vorbis-tools
```

### Arch Linux

```bash
sudo pacman -S mpv ffmpeg mpg123 vorbis-tools
```

### Fedora

```bash
sudo dnf install mpv ffmpeg mpg123 vorbis-tools
```

### macOS

```bash
brew install mpv ffmpeg mpg123 vorbis-tools
```

Verify `ffplay` if you plan to use the fallback backend:

```bash
ffplay -version
```

## Run from source

```bash
git clone https://github.com/pitill0/fluxtuner.git
cd fluxtuner

python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python -m fluxtuner
```

## Install with pipx

```bash
pipx install git+https://github.com/pitill0/fluxtuner.git
fluxtuner
```

Upgrade:

```bash
pipx upgrade fluxtuner
```

Uninstall:

```bash
pipx uninstall fluxtuner
```

## Launch modes

FluxTuner provides four user-facing modes that share core services and
library behavior: the Textual TUI, GTK4 GUI, legacy numbered CLI and
browser-based Web/server mode.

```bash
fluxtuner                                      # Textual TUI, default
fluxtuner --gui                                # GTK4 desktop GUI
fluxtuner --cli                                # legacy numbered CLI
fluxtuner-web --host 127.0.0.1 --port 8080    # Web/server mode
```

The Web/server command requires the optional Web dependencies, installed with
`python -m pip install -e ".[web]"` from a source checkout.

Web users can recover access with server-generated recovery codes. Recovery
codes are shown only when issued, can be regenerated from an authenticated
session, and successful recovery rotates the code set and revokes existing
sessions. See `docs/multiuser.md` for the complete Web account and recovery
model.

The examples in this guide use the installed `fluxtuner` command. When
working directly from a source checkout, use the equivalent module form:

```bash
python -m fluxtuner
```

Options are identical, so `fluxtuner --doctor` becomes
`python -m fluxtuner --doctor`, for example.

## Player backends

FluxTuner currently supports:

- `mpv`
- `ffplay`
- `mpg123`
- `ogg123`

By default, FluxTuner uses automatic backend detection.

```bash
fluxtuner --player auto
fluxtuner --player mpv
fluxtuner --player ffplay
fluxtuner --player mpg123
fluxtuner --player ogg123
```

List supported and available backends:

```bash
fluxtuner --list-players
fluxtuner --doctor
```

Backend notes:

- `mpv` supports play/stop, live pause, live volume and live mute controls.
- `ffplay` is a broad fallback focused on simple play/stop.
- `mpg123` is a specialized lightweight backend for MP3/MPEG streams.
- `ogg123` is a specialized lightweight backend for Ogg/Vorbis/Opus-style streams, depending on the local `ogg123` build.

## Recording

Local stream recording is available in the Textual TUI and GTK4 desktop GUI when
`ffmpeg` is installed and available in `PATH`.

Recording is independent from playback: FluxTuner records the currently selected
station, which does not need to be playing. Only one recording can be active at a time.

Recordings are saved as Matroska audio (`.mka`) files using FFmpeg stream copy, so the
original audio codec is preserved without transcoding. Files are stored under the
FluxTuner data directory:

```text
~/.local/share/fluxtuner/recordings/
```

The TUI uses `R` to start or stop recording. GTK provides a Record / Stop recording
button.

Recording metadata is stored in the FluxTuner SQLite database and scoped to the active
profile. Web/server recording is not included in this release.

## Track ripping with Brynse in GTK

GTK can use the optional Brynse integration to save individual tracks from
compatible ICY radio streams. This is separate from session recording.

From the source checkout and its selected virtual environment:

```bash
python -m pip install -r requirements-brynse.txt
python -m pip check
python -m fluxtuner --gui
```

FFmpeg must be available in `PATH`. The requirements file pins the tested
Brynse revision; installing the base FluxTuner package alone does not enable
this capability.

Right-click a station row and choose `Rip tracks`. The action uses the clicked
station without changing the current selection. Playback does not need to be
running. Once the background availability check completes, reopen the menu if
the action was initially absent.

Only one ripping job can run at a time. Right-click the same station in the
same profile to request `Stop ripping`. Start remains unavailable until both
the run and stop workers finish. Status messages report progress, failures,
finalized track counts and the output directory.

Tracks are saved under `<data_directory>/rips/profile-<id>/<uuid.hex>/`.
`FLUXTUNER_DATA_DIR` overrides the data directory. Brynse controls filenames;
FluxTuner does not reorder artist/title text. Ripping results are not stored
in the SQLite recording history.

Local availability does not guarantee that a station is compatible. The
tested Brynse runner requires ICY metadata and MP3 or AAC audio. Native macOS
has been validated; Linux/Flatpak integration and packaging remain pending.

See [the integration contract](brynse-integration.md) for lifecycle,
shutdown behavior, outputs and validation details.

## TUI Themes

List available themes:

```bash
fluxtuner --list-themes
```

Run with a theme:

```bash
fluxtuner --theme nord
```

Save a theme as default:

```bash
fluxtuner --theme nord --save-theme
```

or:

```bash
fluxtuner --save-theme nord
```

Built-in themes:

- `default`
- `nord`
- `dracula`
- `amber`
- `ptmtrx`

## Saved playlists in GTK

The sidebar provides direct access to saved playlists in the current profile.
Each playlist shows its name and visible station count.

- Use **New playlist…** to create an empty list.
- Click a playlist to display its stations.
- Right-click a station and choose **Add to playlist…** to select a destination.
  The action targets the clicked station and preserves the current selection.
- In a playlist, use **Remove from playlist** to remove the clicked station.
- With a playlist open, use **Delete…** and confirm to delete the list.

Adding a station also saves it to the same profile's favorites, matching the
Web behavior. Removing playlist membership or deleting a playlist preserves
favorites. Playlist contents resolve through favorites; removing a favorite
also removes it from the visible playlist contents.

Names cannot be blank, and duplicate names are rejected without closing the
creation dialog. Canceling a dialog does not modify playlist membership.
The picker captures its station and profile when opened. A deleted destination
is rejected instead of recreated.

Custom favorite tags remain available under **Filter favorites**, collapsed
initially. These filters are separate from persistent playlists.

## GTK application menu

The hamburger button in the upper-right corner opens the application menu:

- **Add station…** saves a personal stream URL to the current profile.
- **Appearance** selects System, Dark or Light. Changes apply immediately
  and the selected mode is saved for the next launch.
- **About FluxTuner** displays the application icon, installed version and
  a link to the project on GitHub.
- **Quit** exits through the coordinated shutdown process, including when
  closing the window would normally hide it to the Linux system tray.

The Quit shortcut is Ctrl+Q on Linux and Command+Q on macOS.

## Custom stations in GTK

Open the application menu and choose **Add station…**. Enter a station name
and an HTTP or HTTPS stream URL, then choose **Add**.

The station is saved to the current profile's favorites and displayed in the
library. Use its normal playback and context-menu actions to play it or add
it to a saved playlist. No Radio Browser entry is required.

Saving does not contact the stream or start playback. Desktop users can also
save HTTP/HTTPS streams on their local network. URLs containing embedded
credentials are not supported.

An existing favorite with the same playable URL is kept unchanged, including
its custom name, user tags and playlist membership. Adding that URL to another
profile stores the chosen display name for that profile while preserving the
shared station metadata.

Names are limited to 200 characters and URLs to 2048. Invalid input leaves the
dialog open for correction. Cancel does not save anything.

### TUI

Press **Ctrl+N** to open Add station. Enter a name and stream URL, then choose
**Add**. Escape cancels. Saving refreshes favorites; existing URLs are preserved.

### Web

Sign in and choose **Add station…** from the main navigation menu, or use
**Favorites → Library actions → Add station…**. Escape cancels the dialog.

Stations are saved to the signed-in user's default profile. Web does not inherit
the desktop's active profile. The API also accepts an explicit existing profile
belonging to that user. Saving requires authentication and CSRF protection and
does not contact the stream. Browser playback and server metadata requests
retain their existing network restrictions.

### Import station collections in GTK

Open the application menu and choose **Import stations…**. Select a local
M3U/M3U8 file and review the valid stations, repeated URLs and reported issues.
Choose an existing playlist or create a new one, then select **Import**.

Valid stations are saved to favorites and the destination playlist in file
order. Existing station metadata, personal names and tags are preserved.
Cancel saves nothing. Reimporting does not duplicate favorites or membership.

Files must use UTF-8, optionally with a BOM, and contain HTTP/HTTPS stream URLs.
The limits are 1 MiB, 5000 station entries and 25000 lines. HLS manifests are
rejected as station collections; an individual station URL may still use HLS.

### Import station collections in Web

Sign in and choose **Import stations…** from the navigation menu. Choose an
M3U/M3U8 file, then select **Preview file**. Review the stations and skipped
entries, choose a new or existing destination playlist, and select
**Import stations**.

The same format limits and metadata-preservation rules apply as in GTK.
Uploads are limited to 1 MiB. Preview and cancel make no library changes;
confirmation saves into the signed-in user's default profile. Existing
favorite names and tags are retained.

### Import station collections in TUI

Press **Ctrl+O**, enter or paste the local M3U/M3U8 file path and press
**Enter** or choose **Preview file**. Paths starting with `~` are supported.
Review the preview, choose a new or existing destination playlist, then
choose **Import**. The destination opens after saving.

**Escape** cancels without saving before confirmation, including during file
reading. Changing the path requires a new preview. Reading and saving run in
the background; repeated submissions and cancellation are disabled while saving.

The same format limits, duplicate handling and metadata-preservation rules
apply across GTK, TUI and Web. TUI imports use the profile captured when the
dialog opened and reject a changed profile or a deleted existing destination.
Use **Tab** to move between controls and **?** for keyboard help.

See [Playlist imports](playlist-imports.md) for format and conflict rules.

## GTK appearance

The GTK desktop GUI provides an appearance selector with three modes:

- `System` — follows the system color-scheme preference when GTK exposes it.
- `Dark` — always uses the FluxTuner dark palette.
- `Light` — always uses the FluxTuner light palette.

The selected appearance is persisted and changes are applied immediately.

On platforms where GTK does not expose the system color scheme, `System`
falls back to the native GTK appearance. Explicit `Dark` and `Light` modes
remain available.

On current GTK builds for macOS, the system color scheme may be reported as
unsupported, so `System` can fall back to GTK's default light appearance.

## GTK system tray on Linux

On Linux, the GTK frontend automatically attempts to register a
StatusNotifierItem with the desktop session. There is no separate tray setting
and no additional Python dependency.

When the desktop provides a compatible StatusNotifierWatcher:

- the FluxTuner tray icon is shown automatically;
- closing the main window hides it instead of terminating the application;
- playback continues while the window is hidden;
- activating the tray icon restores and focuses the main window;
- the tray menu shows the current station and provides `Show FluxTuner`,
  `Stop` and `Quit` actions.

`Quit` is the explicit way to terminate FluxTuner while tray mode is active.

If the desktop session does not provide a compatible watcher, tray
registration fails gracefully and closing the GTK window keeps the normal
application-exit behavior.

The current tray backend is Linux-only. macOS keeps its existing GTK window
lifecycle; native menu-bar integration can be considered separately in the
future.

## Useful commands

```bash
fluxtuner --help
fluxtuner --version
fluxtuner --list-players
fluxtuner --doctor
fluxtuner --list-themes
fluxtuner --clear-cache
fluxtuner --export-favs favorites.json
fluxtuner --import-favs favorites.json
fluxtuner --export-playlists playlists.json
fluxtuner --import-playlists playlists.json
```

## TUI keybindings

| Key | Action |
| --- | --- |
| `/` | Focus search |
| `Enter` | Play/apply selected row |
| `Escape` | Focus station list |
| `Space` | Play/stop selected station |
| `x` | Stop playback |
| `+` / `-` | Volume up/down when supported by the active backend |
| `m` | Mute/unmute when supported by the active backend |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `d` | Remove selected favorite |
| `e` | Rename favorite |
| `g` | Edit favorite tags |
| `u` | Filter favorites by tag |
| `p` | Show playlists |
| `n` | Create playlist |
| `b` | Add station to playlist |
| `r` | Play random favorite |
| `h` | Show history |
| `l` | Play last station |
| `t` | Show themes |
| `y` | Save selected theme |
| `q` | Quit |

## Data storage

FluxTuner stores local data in XDG-style locations.

The base directories respect `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` when they are set.

Default locations:

- Library database: `~/.local/share/fluxtuner/fluxtuner.db`
- Config: `~/.config/fluxtuner/config.json`
- Data usage: `~/.local/share/fluxtuner/usage.json`
- Search cache: `~/.cache/fluxtuner/search_cache.json`

The library database stores favorites, playback history, manual playlists and
normalized station records for profile-scoped library data.

Favorites are the saved-station library used by all FluxTuner frontends. Manual
playlists reference saved stations; adding a station to a playlist can therefore
also save it to favorites/library if it is not already present. This keeps
playlist resolution, exports and compatibility checks consistent across the TUI,
GTK, CLI and Web modes.

Legacy library JSON files are still supported as migration sources:

- `~/.local/share/fluxtuner/favorites.json`
- `~/.local/share/fluxtuner/playlists.json`
- `~/.local/share/fluxtuner/history.json`

Older dotfiles such as `~/.fluxtuner_favorites.json`,
`~/.fluxtuner_playlists.json`, `~/.fluxtuner_history.json` and
`~/.fluxtuner_usage.json` are copied into the current XDG locations when needed
and kept in place as a conservative migration.

Import and export commands still use JSON files:

```bash
fluxtuner --export-favs favorites.json
fluxtuner --import-favs favorites.json
fluxtuner --export-playlists playlists.json
fluxtuner --import-playlists playlists.json
```

## macOS GTK note

When using a Python virtual environment, PyGObject installed through Homebrew may not be visible inside the venv.

Install system dependencies:

```bash
brew install gtk4 pygobject3 mpv ffmpeg
```

If the GUI fails with `ModuleNotFoundError: No module named 'gi'`, find the Homebrew PyGObject path:

```bash
find "$(brew --prefix)" -path "*site-packages/gi/__init__.py" 2>/dev/null
```

Then run FluxTuner with that site-packages directory in `PYTHONPATH`.

## Specialized player backend compatibility

FluxTuner supports both general-purpose and specialized playback backends.

General-purpose backends:

- `mpv` — recommended backend with broad stream compatibility and live controls.
- `ffplay` — broad compatibility fallback provided by FFmpeg.

Specialized lightweight backends:

- `mpg123` — lightweight backend for MP3/MPEG streams.
- `ogg123` — lightweight backend for Ogg/Vorbis/Opus/FLAC-style streams, depending on the local `ogg123` build.

When a specialized backend is selected explicitly, FluxTuner filters search results where possible so the station list only contains streams that match the active backend capabilities. Saved favorites, history and playlists are kept intact, but incompatible stations are marked and blocked from playback with a clear message.

```bash
fluxtuner --player mpg123
fluxtuner --player ogg123
```

The legacy numbered CLI uses the same compatibility checks for searches, favorites and random favorite playback when a specialized backend is active.

## Runtime diagnostics

Use `--doctor` to print a compact runtime diagnostic report:

```bash
fluxtuner --doctor
```

The report includes the FluxTuner version, Python/runtime platform, XDG storage paths and player backend availability. This is useful when reporting issues or checking what FluxTuner can see inside a sandboxed environment.

## Troubleshooting player backends

Use `--list-players` to inspect which playback backends FluxTuner can find in the current environment:

```bash
fluxtuner --list-players
```

The command shows whether each backend is available or missing, whether it is general-purpose or specialized, and which codecs or live controls it declares.

If no backend is available, install at least one supported player:

- `mpv` for the recommended general-purpose backend.
- `ffmpeg` / `ffplay` for the broad fallback backend.
- `mpg123` for lightweight MP3/MPEG playback.
- `vorbis-tools` / `ogg123` for lightweight Ogg/Vorbis/Opus-style playback.

Inside Flatpak or other sandboxed environments, run the same command inside the sandbox to confirm which player binaries are actually visible to FluxTuner.

### Profiles

FluxTuner profiles separate favorites, manual playlists and playback history by
context. They are useful for setups such as work, home, terrace, pool, focus or
testing.

Profiles are not separate user accounts. Anyone using the same FluxTuner
installation can still see and select the available profiles.

List known profiles:

    python -m fluxtuner --list-profiles

Use `--profile NAME` to target a profile explicitly:

    python -m fluxtuner --profile work

### Persistent active profile

FluxTuner can persist an active profile for profile-aware commands and
interfaces:

    python -m fluxtuner --profile work --set-active-profile
    python -m fluxtuner --show-active-profile
    python -m fluxtuner --clear-active-profile

Profile resolution order is:

    1. Explicit `--profile NAME` or Web `?profile=NAME`
    2. Persisted active profile
    3. Internal default profile

### Legacy CLI profile scope

The legacy numbered CLI honors `--profile NAME` for favorites operations:

    python -m fluxtuner --cli --profile work

This scopes saving favorites from search, listing/removing favorites and random
favorite playback to the selected profile.

When `--profile NAME` is omitted, the legacy numbered CLI uses the persisted
active profile if one is configured, otherwise it falls back to the internal
default profile.

### Profile-aware import and export

Import and export commands accept `--profile NAME` to target a named profile:

    python -m fluxtuner --profile work --export-favs work-favorites.json
    python -m fluxtuner --profile work --import-favs work-favorites.json
    python -m fluxtuner --profile work --export-playlists work-playlists.json
    python -m fluxtuner --profile work --import-playlists work-playlists.json

When `--profile NAME` is omitted, FluxTuner uses the persisted active profile
if one is configured, otherwise it falls back to the internal default profile.

### Profile-aware interfaces

The persisted active profile is used by CLI import/export commands, the legacy
numbered CLI favorites flow, the Textual TUI, GTK GUI and Web mode.

Web API endpoints also accept `?profile=NAME` as a per-request override:

    /api/favorites?profile=work
    /api/history?profile=work
    /api/playlists?profile=work

Web profile overrides have the highest priority for that request, followed by
the persisted active profile and then the internal default profile.
