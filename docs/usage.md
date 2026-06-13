# Usage Guide

This guide covers installing, running and configuring FluxTuner.

## Requirements

FluxTuner requires:

- Python 3.11 or newer.
- At least one playback backend:
  - `mpv` recommended.
  - `ffplay`, provided by FFmpeg, as a lightweight fallback.
- A terminal emulator with good Unicode support for the TUI.

The GTK desktop GUI also requires GTK4 and PyGObject.

## Install player backends

### CRUX Linux

```bash
sudo prt-get depinst mpv
sudo prt-get depinst ffmpeg
```

### Debian / Ubuntu

```bash
sudo apt install mpv ffmpeg
```

### Arch Linux

```bash
sudo pacman -S mpv ffmpeg
```

### Fedora

```bash
sudo dnf install mpv ffmpeg
```

### macOS

```bash
brew install mpv ffmpeg
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

By default, FluxTuner uses automatic backend detection.

```bash
fluxtuner --player auto
fluxtuner --player mpv
fluxtuner --player ffplay
```

List supported and available backends:

```bash
fluxtuner --list-players
```

Backend notes:

- `mpv` supports play/stop, live volume and live mute controls.
- `ffplay` is focused on play/stop and does not provide live volume or live mute control in FluxTuner.

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

FluxTuner stores user data in XDG-style locations.

The base directories respect `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` when they are set.

Default locations:

- Config: `~/.config/fluxtuner/config.json`
- Favorites: `~/.local/share/fluxtuner/favorites.json`
- Playlists: `~/.local/share/fluxtuner/playlists.json`
- History: `~/.local/share/fluxtuner/history.json`
- Data usage: `~/.local/share/fluxtuner/usage.json`
- Search cache: `~/.cache/fluxtuner/search_cache.json`

Legacy files such as `~/.fluxtuner_favorites.json`, `~/.fluxtuner_playlists.json`, `~/.fluxtuner_history.json` and `~/.fluxtuner_usage.json` are copied into the current XDG locations when needed and kept in place as a conservative migration.

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
