# FluxTuner

FluxTuner is a terminal internet radio player powered by Python, Textual and `mpv`.

It provides a comfortable TUI for searching internet radio stations, playing streams, managing favorites, launching a random favorite station and customizing the interface with themes.

## Features

- Textual-based terminal UI
- Search stations by name or genre/tag
- Live search with debounce while typing
- Filter searches by country and minimum bitrate
- Play streams with `mpv`
- Persistent favorites
- Random favorite playback
- Recently played history
- Configurable bundled themes
- In-app theme selector
- Theme preview while browsing themes
- mpv JSON IPC controls for pause, mute, volume and smooth stream switching
- Richer Now Playing panel with status, volume and mute state
- Legacy numbered CLI available with `--cli`

## Requirements

- Python 3.11+
- `mpv` installed and available in `PATH`

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m fluxtuner
```

Or, after installing the package:

```bash
fluxtuner
```

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `/` | Focus search input |
| `Escape` | Return focus to the main list |
| `Enter` | Play selected station, or apply selected theme in theme mode |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `h` | Show recently played history |
| `d` | Remove selected favorite |
| `r` | Play random favorite |
| `Space` | Pause/resume playback |
| `+` | Increase volume |
| `-` | Decrease volume |
| `m` | Toggle mute |
| `x` | Stop playback |
| `t` | Open theme selector |
| `p` | Preview/apply selected theme |
| `y` | Save active theme as default |
| `q` | Quit |

## Search behavior

FluxTuner starts a live search automatically once the query has at least 3 characters.
For shorter searches, type the query and press `Enter`.

Searches are debounced, so FluxTuner waits briefly while you type before calling the Radio Browser API.

## Search filters

The TUI includes optional filters below the search bar:

- `Country`: restricts Radio Browser results to a country name, such as `Spain`, `France` or `United Kingdom`.
- `Min kbps`: filters out stations below the selected bitrate.

Use `Clear filters` to reset both fields.

## History

FluxTuner stores recently played stations locally and shows them with `h` from the TUI.

History is stored in:

```text
~/.fluxtuner_history.json
```

Each repeated play updates the station timestamp and increases its `play_count`.

## Themes

Bundled themes live in:

```text
fluxtuner/themes/
```

Available themes:

```bash
python -m fluxtuner --list-themes
```

Run with a specific theme for this session:

```bash
python -m fluxtuner --theme nord
python -m fluxtuner --theme dracula
python -m fluxtuner --theme amber
python -m fluxtuner --theme ptmtrx
```

Save a theme as the default:

```bash
python -m fluxtuner --theme nord --save-theme
```

This syntax is also supported:

```bash
python -m fluxtuner --save-theme nord
```

The default config file is stored at:

```text
~/.config/fluxtuner/config.json
```

Example:

```json
{
  "theme": "nord"
}
```

## In-app theme selector

Open the theme selector from the TUI:

```text
t
```

While browsing themes:

- Highlighting a theme previews it immediately.
- `Enter` or `p` applies/previews the selected theme.
- `y` saves the current active theme as the default.

## Creating a custom theme

Create a new `.tcss` file inside `fluxtuner/themes/`, for example:

```text
fluxtuner/themes/my-theme.tcss
```

Then run:

```bash
python -m fluxtuner --theme my-theme
```

Or open the in-app selector with `t` and preview it there.

A theme is a Textual CSS file. The included themes are good starting points.

## Legacy CLI

```bash
python -m fluxtuner --cli
```

## Data files

Favorites are stored in:

```text
~/.fluxtuner_favorites.json
```

Recently played history is stored in:

```text
~/.fluxtuner_history.json
```

User configuration is stored in:

```text
~/.config/fluxtuner/config.json
```

## mpv IPC controls

FluxTuner starts `mpv` with its JSON IPC socket enabled in TUI mode. This allows the app to control the active playback session without killing and restarting the process for every action.

Current TUI controls:

- `Space`: pause/resume
- `+`: volume up
- `-`: volume down
- `m`: mute/unmute
- `x`: stop playback

When a new station is selected while mpv is already running, FluxTuner uses `loadfile ... replace` over IPC instead of killing and restarting mpv. This makes stream switching smoother.


## UI notes

- Toolbar and side-panel buttons use rounded borders and readable minimum sizes.
- If your terminal is very narrow, increase the window width so the right action panel can keep labels visible.
