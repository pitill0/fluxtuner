# FluxTuner

FluxTuner is a terminal internet radio player powered by Python, Textual and `mpv`.

It provides a comfortable TUI for searching public radio stations, playing streams, managing favorites and starting a random favorite station.

## Features

- Search internet radio stations by name or genre/tag.
- Play stations through `mpv`.
- Textual-based terminal UI.
- Favorites stored locally in JSON.
- Random favorite playback.
- Non-blocking playback controller for TUI usage.
- Early `mpv` availability check.

## Requirements

- Python 3.11+
- `mpv` installed and available in `PATH`

Install `mpv` with your system package manager, for example:

```bash
sudo apt install mpv
```

On non-systemd or custom desktop sessions, make sure your audio stack is running before starting FluxTuner.

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the TUI

```bash
python -m fluxtuner
```

## Run the legacy CLI

```bash
python -m fluxtuner --cli
```

## TUI shortcuts

| Key | Action |
| --- | --- |
| `/` or `s` | Focus search input |
| `Enter` | Play selected station |
| `a` | Add selected station to favorites |
| `f` | Show favorites |
| `d` | Remove selected favorite |
| `r` | Play random favorite |
| `x` | Stop playback |
| `q` | Quit |

## Favorites file

Favorites are stored at:

```text
~/.fluxtuner_favorites.json
```

## Project structure

```text
fluxtuner/
├── fluxtuner/
│   ├── __main__.py
│   ├── tui.py
│   └── core/
│       ├── api.py
│       ├── favorites.py
│       └── player.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Notes

FluxTuner uses the public Radio Browser API for station discovery.
