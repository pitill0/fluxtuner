# FluxTuner

FluxTuner is a terminal internet radio player powered by Python, Textual and `mpv`.

It provides a comfortable TUI for searching internet radio stations, playing streams, managing favorites, launching random stations, using tag-based dynamic playlists and customizing the interface with themes.

## Features

- Textual-based terminal UI
- Search stations by name or genre/tag
- Live search with debounce while typing
- Filter searches by country and minimum bitrate
- Play streams with `mpv`
- Persistent favorites with custom names and user tags
- Random favorite playback
- Favorite tag filtering
- Tag-based dynamic playlists
- Smart Play random station from a selected tag playlist
- Favorites import/export
- Recently played history
- Configurable bundled themes
- Theme-aware buttons, footer shortcuts and control states
- In-app theme selector
- Theme preview while browsing themes
- mpv JSON IPC controls for pause, mute, volume and smooth stream switching
- Richer Now Playing panel with status, visual volume bar and mute state
- Active station marker in station, favorites and history lists
- Local search cache for repeated/live searches
- Restores last station, volume and mute preferences
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
| `Enter` | Play selected station, smart play selected playlist, or apply selected theme in theme mode |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `h` | Show recently played history |
| `l` | Play last restored station |
| `d` | Remove selected favorite |
| `e` | Rename selected favorite |
| `g` | Edit selected favorite tags |
| `u` | Filter favorites by user tag |
| `r` | Play random favorite, or smart play the selected playlist in playlist mode |
| `p` | Open dynamic playlists / Smart Play |
| `Space` | Pause/resume playback |
| `+` | Increase volume |
| `-` | Decrease volume |
| `m` | Toggle mute |
| `x` | Stop playback |
| `t` | Open theme selector |
| `y` | Save active theme as default |
| `q` | Quit |

## Search behavior

FluxTuner starts a live search automatically once the query has at least 3 characters.
For shorter searches, type the query and press `Enter`.

Searches are debounced, so FluxTuner waits briefly while you type before calling the Radio Browser API. Repeated searches are cached locally for a short period to keep live search fast and reduce unnecessary API calls.


## Search cache

FluxTuner stores repeated search results in a local cache:

```text
~/.cache/fluxtuner/search_cache.json
```

The cache is transparent in normal use. To clear it manually:

```bash
python -m fluxtuner --clear-cache
```

## Search filters

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
| `a` | Add the selected station to favorites |
| `d` | Remove selected favorite |
| `e` | Rename selected favorite |
| `g` | Edit comma-separated favorite tags |
| `u` | Filter favorites by a user tag |

Favorite tags are personal labels such as `work`, `focus`, `morning` or `lofi`. They are separate from Radio Browser tags.

When editing a favorite name or tags, FluxTuner reuses the search input as a small command field. Type the new value and press `Enter`. Leaving the value empty clears the custom name or tags.

### Import / export favorites

Export favorites:

```bash
python -m fluxtuner --export-favs favorites-backup.json
```

Import favorites:

```bash
python -m fluxtuner --import-favs favorites-backup.json
```

## Dynamic playlists and Smart Play

FluxTuner automatically creates dynamic playlists from favorite tags. For example, favorites tagged with `work` become the `#work` playlist, and favorites tagged with `focus` become the `#focus` playlist.

From the TUI:

| Key | Action |
| --- | --- |
| `p` | Open dynamic playlists |
| `Enter` | Smart Play a random station from the selected playlist |
| `r` | Smart Play the selected playlist while in playlist mode |
| `f` | Show the favorites matching the selected playlist tag |

Dynamic playlists are not stored separately. They are generated from favorite tags, so editing tags with `g` updates playlists immediately.

## History

FluxTuner stores recently played stations locally and shows them with `h` from the TUI.

History is stored in:

```text
~/.fluxtuner_history.json
```

Each repeated play updates the station timestamp and increases its `play_count`.

## Now Playing and active station

FluxTuner marks the station currently playing in the visible list with a `▶` marker.
This works in search results, favorites and history when the current station is present in that list.

The Now Playing panel also shows a compact visual volume bar, playback state, mute state, bitrate, codec, country and tags.


## Playback state restore

FluxTuner remembers:

- the last played station
- the last known volume
- mute state

On startup, the last station is shown in the Now Playing panel and can be played with `l`. FluxTuner does **not** autoplay on launch. When playback starts, the saved volume and mute state are applied to the new `mpv` session.

Playback state is stored in:

```text
~/.config/fluxtuner/config.json
```

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
  "playback": {
    "last_station": {
      "name": "BBC Radio 1",
      "url": "https://..."
    },
    "muted": false,
    "volume": 70
  },
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
- `Enter` applies/previews the selected theme.
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

Button roles used by the TUI:

- `.primary-button`: main actions such as Search and Add favorite.
- `.secondary-button`: neutral actions such as Clear filters.
- `.success-button`: Play.
- `.warning-button`: Remove favorite.
- `.danger-button`: Stop.

When previewing themes in-app, FluxTuner also applies these button roles at runtime.

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

Search cache is stored in:

```text
~/.cache/fluxtuner/search_cache.json
```

User configuration and playback state are stored in:

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

- Toolbar and side-panel buttons use rounded borders, readable minimum sizes and theme-aware role colors.
- The footer shortcut/help bar can be styled per theme with `Footer` selectors.
- If your terminal is very narrow, increase the window width so the right action panel can keep labels visible.


## v10 visual theming note

Button colors, action roles and footer shortcut styling now live in theme files, so custom themes can control more of the TUI without Python changes.
