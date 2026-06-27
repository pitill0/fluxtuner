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

FluxTuner provides three interfaces that share the same core services, playback layer and user data.

```bash
fluxtuner              # Textual TUI, default
fluxtuner --gui        # GTK4 desktop GUI
fluxtuner --cli        # legacy numbered CLI
```

When running from source, replace `fluxtuner` with:

```bash
python -m fluxtuner
```

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

## Themes

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
normalized station records for the internal `default` profile.

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

### Persistent active profile

FluxTuner can persist an active profile for profile-aware CLI commands:

    python -m fluxtuner --profile work --set-active-profile
    python -m fluxtuner --show-active-profile
    python -m fluxtuner --clear-active-profile

Profile resolution order is:

    1. Explicit --profile NAME
    2. Persisted active profile
    3. Internal default profile

The persisted active profile is currently used by CLI import/export commands and
the legacy numbered CLI favorites flow. Textual TUI, GTK GUI and Web mode do not
use active profile selection yet.


### Legacy CLI profile scope

The legacy numbered CLI honors `--profile NAME` for favorites operations:

    python -m fluxtuner --cli --profile work

This scopes saving favorites from search, listing/removing favorites and random
favorite playback to the selected profile.

Profile selection is not active in the Textual TUI, GTK GUI or Web mode yet.


### Profile-aware import and export

Import and export commands accept `--profile NAME` to target a named profile.
When omitted, FluxTuner uses the internal `default` profile.

    python -m fluxtuner --profile work --export-favs work-favorites.json
    python -m fluxtuner --profile work --import-favs work-favorites.json
    python -m fluxtuner --profile work --export-playlists work-playlists.json
    python -m fluxtuner --profile work --import-playlists work-playlists.json

This does not change the active TUI, GTK GUI or Web profile yet. It only scopes
CLI import/export operations.

