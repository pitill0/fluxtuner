# FluxTuner

FluxTuner is a terminal internet radio player powered by Python, Textual and `mpv`.

It provides a comfortable TUI for searching internet radio stations, playing streams, managing favorites, launching a random favorite station and customizing the interface with themes.

## Features

- Textual-based terminal UI
- Search stations by name or genre/tag
- Play streams with `mpv`
- Persistent favorites
- Random favorite playback
- Configurable bundled themes
- In-app theme selector
- Theme preview while browsing themes
- CSS/theme hot reload from the TUI
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
| `d` | Remove selected favorite |
| `r` | Play random favorite |
| `x` | Stop playback |
| `t` | Open theme selector |
| `p` | Preview/apply selected theme |
| `y` | Save active theme as default |
| `Ctrl+R` | Reload current theme CSS file |
| `q` | Quit |

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
- `Ctrl+R` reloads the active `.tcss` file from disk.

This makes theme editing much faster: edit a `.tcss` file in your editor, return to FluxTuner and press `Ctrl+R`.

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
~/.radio_favs.json
```

User configuration is stored in:

```text
~/.config/fluxtuner/config.json
```
