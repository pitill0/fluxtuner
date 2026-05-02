# FluxTuner

FluxTuner is a terminal internet radio player powered by Python, Textual and `mpv`.

It provides a comfortable TUI for searching internet radio stations, playing streams, managing favorites and launching a random favorite station.

## Features

- Textual-based terminal UI
- Search stations by name or genre/tag
- Play streams with `mpv`
- Persistent favorites
- Random favorite playback
- Configurable bundled themes
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
| `Escape` | Return focus to the station list |
| `Enter` | Play selected station |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `d` | Remove selected favorite |
| `r` | Play random favorite |
| `x` | Stop playback |
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
```

Save a theme as the default:

```bash
python -m fluxtuner --theme nord --save-theme
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

## Creating a custom theme

Create a new `.tcss` file inside `fluxtuner/themes/`, for example:

```text
fluxtuner/themes/my-theme.tcss
```

Then run:

```bash
python -m fluxtuner --theme my-theme
```

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
