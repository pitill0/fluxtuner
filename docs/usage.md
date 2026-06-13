# Usage Guide

This guide covers installation, launch modes, player backend selection, themes, keybindings and user data locations.

## Requirements

FluxTuner requires:

- Python 3.11 or newer.
- At least one supported player backend:
  - `mpv`, recommended.
  - `ffplay`, provided by FFmpeg, as a lightweight fallback.
- A terminal emulator with good Unicode support for the TUI.

The optional GTK desktop GUI also requires:

- GTK4.
- PyGObject.

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

Verify `ffplay` when using the fallback backend:

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

Install a specific tag:

```bash
pipx install git+https://github.com/pitill0/fluxtuner.git@v0.3.0
```

Upgrade or uninstall:

```bash
pipx upgrade fluxtuner
pipx uninstall fluxtuner
```

## Launch modes

FluxTuner provides three entry modes through the same `fluxtuner` command.

```bash
fluxtuner              # default Textual TUI
fluxtuner --gui        # GTK4 desktop GUI
fluxtuner --cli        # legacy numbered CLI
```

When running from source, replace `fluxtuner` with:

```bash
python -m fluxtuner
```

## Player backends

FluxTuner supports:

- `mpv`, recommended.
- `ffplay`, lightweight fallback.

Automatic backend selection uses the first available supported backend in this order:

1. `mpv`
2. `ffplay`

Inspect detected backends:

```bash
fluxtuner --list-players
```

Select a backend explicitly:

```bash
fluxtuner --player auto
fluxtuner --player mpv
fluxtuner --player ffplay
fluxtuner --gui --player mpv
fluxtuner --gui --player ffplay
```

Backend capability notes:

- `mpv` supports play, stop, live volume and live mute controls.
- `ffplay` is focused on play and stop. FluxTuner does not currently expose live volume or mute controls through the `ffplay` backend.

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
fluxtuner --verbose
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
| `Esc` | Focus station list |
| `Enter` | Play/apply selected item |
| `Space` | Play/stop selected station |
| `x` | Stop playback |
| `+` / `-` | Volume up/down when supported |
| `m` | Mute/unmute when supported |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `d` | Delete/remove selected favorite |
| `e` | Rename favorite |
| `g` | Edit favorite tags |
| `u` | Filter favorites by tag |
| `h` | Show history |
| `l` | Play last station |
| `p` | Show playlists |
| `n` | Create playlist |
| `b` | Add selected station to playlist |
| `r` | Play random favorite |
| `t` | Show themes |
| `y` | Save selected theme |
| `q` | Quit |

## Data storage

FluxTuner stores user data in XDG-style locations and respects `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` when set.

Default locations:

- Config: `~/.config/fluxtuner/config.json`
- Favorites: `~/.local/share/fluxtuner/favorites.json`
- Playlists: `~/.local/share/fluxtuner/playlists.json`
- History: `~/.local/share/fluxtuner/history.json`
- Data usage: `~/.local/share/fluxtuner/usage.json`
- Search cache: `~/.cache/fluxtuner/search_cache.json`

Legacy files such as `~/.fluxtuner_favorites.json`, `~/.fluxtuner_playlists.json`, `~/.fluxtuner_history.json` and `~/.fluxtuner_usage.json` are copied into the new XDG locations when needed and kept in place to avoid data loss.

## macOS GTK note

When using a Python virtual environment, PyGObject installed through Homebrew may not be visible from inside the venv.

Install dependencies:

```bash
brew install gtk4 pygobject3 mpv ffmpeg
```

If the GUI fails with:

```text
ModuleNotFoundError: No module named 'gi'
```

find the Homebrew PyGObject path:

```bash
find "$(brew --prefix)" -path "*site-packages/gi/__init__.py" 2>/dev/null
```

Then run FluxTuner with that path in `PYTHONPATH`. On Apple Silicon this is often similar to:

```bash
PYTHONPATH=/opt/homebrew/lib/python3.14/site-packages \
python -m fluxtuner --gui --player mpv
```
