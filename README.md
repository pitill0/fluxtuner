# FluxTuner

**FluxTuner** is a themeable terminal internet radio player powered by Python, Textual and `mpv`.

It is designed for people who live in the terminal but still want a comfortable, keyboard-first music/radio experience: search stations, play streams, manage favorites, create playlists, switch themes and control playback without leaving your shell.

> Status: `v0.1.0` release candidate / alpha.

## Highlights

- Textual-based terminal UI
- Search internet radio stations by name, genre/tag, country and minimum bitrate
- Live search with debounce and local cache
- Playback via `mpv`
- Smooth stream switching through `mpv` JSON IPC
- Pause, mute and volume controls from the TUI
- Persistent favorites with custom names and user tags
- Recently played history
- Dynamic playlists generated from favorite tags
- Persistent manual playlists
- Smart Play: random station from a selected playlist
- Theme system with bundled themes and in-app preview/save flow
- Theme-aware buttons, footer shortcuts and control states
- Active station marker and visual volume bar
- Import/export helpers for favorites and playlists
- Legacy numbered CLI available with `--cli`

## Requirements

- Python 3.11+
- `mpv` installed and available in `PATH`

FluxTuner checks for `mpv` at startup and exits with a clear error if it is missing.

## Installation

### Development install

```bash
git clone <your-repo-url> fluxtuner
cd fluxtuner
python -m venv .venv
source .venv/bin/activate
pip install -e .
fluxtuner
```

### pipx-style install from a local checkout

```bash
pipx install .
fluxtuner
```

### Run without installing

```bash
python -m fluxtuner
```

## Quick start

```bash
fluxtuner
```

Useful commands:

```bash
fluxtuner --help
fluxtuner --version
fluxtuner --list-themes
fluxtuner --theme nord
fluxtuner --save-theme ptmtrx
fluxtuner --clear-cache
```

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `/` | Focus search input |
| `Escape` | Return focus to the main list |
| `Enter` | Play selected station, smart play selected playlist, or apply selected theme in theme mode |
| `a` | Add selected station to favorites |
| `f` | Show favorites, or show stations for the selected playlist in playlist mode |
| `h` | Show recently played history |
| `l` | Play last restored station |
| `d` | Remove selected favorite, delete playlist, or remove station from opened playlist |
| `e` | Rename selected favorite |
| `g` | Edit selected favorite tags |
| `u` | Filter favorites by user tag |
| `b` | Add selected station/favorite to a persistent playlist |
| `n` | Create a new persistent playlist |
| `r` | Play random favorite, or smart play selected playlist in playlist mode |
| `p` | Open playlists / Smart Play |
| `Space` | Pause/resume playback |
| `+` | Increase volume |
| `-` | Decrease volume |
| `m` | Toggle mute |
| `x` | Stop playback |
| `t` | Open theme selector |
| `y` | Save active theme as default |
| `q` | Quit |

## Search

FluxTuner starts a live search automatically once the query has at least 3 characters. For shorter searches, type the query and press `Enter`.

Searches are debounced and cached locally so repeated/live searches stay fast and avoid unnecessary API calls.

The TUI includes optional filters below the search bar:

- `Country`: restricts Radio Browser results to a country name, such as `Spain`, `France` or `United Kingdom`.
- `Min kbps`: filters out stations below the selected bitrate.

Use `Clear filters` to reset both fields.

## Favorites

Favorites are stored locally and can be personalized without changing the original Radio Browser station metadata.

From the TUI:

| Key | Action |
| --- | --- |
| `f` | Open favorites |
| `a` | Add selected station to favorites |
| `d` | Remove selected favorite |
| `e` | Rename selected favorite |
| `g` | Edit comma-separated favorite tags |
| `u` | Filter favorites by a user tag |

Favorite tags are personal labels such as `work`, `focus`, `morning` or `lofi`. They are separate from Radio Browser tags.

When editing a favorite name or tags, FluxTuner reuses the search input as a small command field. Type the new value and press `Enter`. Leaving the value empty clears the custom name or tags.

### Import / export favorites

```bash
fluxtuner --export-favs favorites-backup.json
fluxtuner --import-favs favorites-backup.json
```

## Playlists and Smart Play

FluxTuner supports two kinds of playlists:

- **Persistent playlists**: manually created playlists stored in `~/.fluxtuner_playlists.json`.
- **Dynamic tag playlists**: automatically generated from favorite tags. For example, favorites tagged with `work` become the `#work` playlist.

Persistent playlists contain references to favorites, so add stations to favorites first and then organize them into playlists.

From the TUI:

| Key | Action |
| --- | --- |
| `p` | Open playlists |
| `n` | Create a persistent playlist |
| `b` | Add the selected station/favorite to a persistent playlist |
| `Enter` | Smart Play a random station from the selected playlist |
| `r` | Smart Play the selected playlist while in playlist mode |
| `f` | Show stations for the selected playlist |
| `d` | Delete selected persistent playlist, or remove selected station from an opened persistent playlist |

Dynamic playlists are not stored separately. They are generated from favorite tags, so editing tags with `g` updates dynamic playlists immediately. Persistent playlists remain stable until you edit them manually.

### Import / export persistent playlists

```bash
fluxtuner --export-playlists playlists-backup.json
fluxtuner --import-playlists playlists-backup.json
```

## Themes

Bundled themes live in `fluxtuner/themes/`.

List themes:

```bash
fluxtuner --list-themes
```

Run with a specific theme for one session:

```bash
fluxtuner --theme nord
fluxtuner --theme dracula
fluxtuner --theme amber
fluxtuner --theme ptmtrx
```

Save a default theme:

```bash
fluxtuner --theme nord --save-theme
```

This syntax is also supported:

```bash
fluxtuner --save-theme nord
```

Open the in-app selector with `t`:

- Highlighting a theme previews it immediately.
- `Enter` applies/previews the selected theme.
- `y` saves the current active theme as the default.

### Creating a custom theme

Create a new `.tcss` file inside `fluxtuner/themes/`, for example:

```text
fluxtuner/themes/my-theme.tcss
```

Then run:

```bash
fluxtuner --theme my-theme
```

FluxTuner themes can customize the main surface colors, station list, side panel, Now Playing panel, toolbar buttons, side action buttons and the footer shortcuts/help bar.

Recommended selectors for custom themes:

```css
Button { ... }
.toolbar-button { ... }
.side-button { ... }
.primary-button { ... }
.secondary-button { ... }
.success-button { ... }
.warning-button { ... }
.danger-button { ... }
Footer { ... }
Footer .footer--key { ... }
Footer .footer--description { ... }
```

## Data files

FluxTuner stores local data in predictable user-level files:

| Data | Path |
| --- | --- |
| Favorites | `~/.fluxtuner_favorites.json` |
| Recently played history | `~/.fluxtuner_history.json` |
| Persistent playlists | `~/.fluxtuner_playlists.json` |
| Search cache | `~/.cache/fluxtuner/search_cache.json` |
| Config / theme / playback state | `~/.config/fluxtuner/config.json` |

FluxTuner remembers the last played station, volume and mute state, but it does **not** autoplay on launch. Use `l` to play the last restored station.

## mpv IPC controls

In TUI mode, FluxTuner starts `mpv` with a JSON IPC socket. This allows it to control playback without killing the process for every action.

Current controls:

- `Space`: pause/resume
- `+`: volume up
- `-`: volume down
- `m`: mute/unmute
- `x`: stop playback

When a new station is selected while `mpv` is already running, FluxTuner uses `loadfile ... replace` over IPC for smoother stream switching.

## Legacy CLI

```bash
fluxtuner --cli
```

## Development

Install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

Useful commands:

```bash
make run
make cli
make themes
make build
```

Build a wheel/sdist:

```bash
python -m build
```

## Release checklist

Before tagging a release:

```bash
fluxtuner --version
fluxtuner --help
fluxtuner --list-themes
python -m build
```

Then tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## License

MIT. See `LICENSE`.
