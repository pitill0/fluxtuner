# FluxTuner

**FluxTuner** is a lightweight internet radio player for the terminal, powered by Python and `mpv`.

The goal is to start with a clean CLI foundation and evolve into a full TUI application with search, favorites, random playback, and later GUI-friendly architecture.

## Features

- Search internet radio stations by name
- Play streams using `mpv`
- Validate `mpv` availability at startup
- Save favorite stations locally
- Play a random favorite station
- Modular Python structure, ready to grow into a TUI

## Requirements

System dependencies:

```bash
mpv
python3.11+
```

FluxTuner checks for `mpv` at startup and exits with a clear error message if it is not available in `PATH`.

Example installation:

```bash
# Debian/Ubuntu
sudo apt install mpv

# macOS
brew install mpv
```

Python dependencies:

```bash
pip install -r requirements.txt
```

## Quick start

```bash
git clone <your-repo-url>
cd fluxtuner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m fluxtuner
```

## Project structure

```text
fluxtuner/
├── fluxtuner/
│   ├── __init__.py
│   ├── __main__.py
│   └── core/
│       ├── __init__.py
│       ├── api.py
│       ├── favorites.py
│       └── player.py
├── README.md
├── requirements.txt
└── .gitignore
```

## Roadmap

- [x] CLI MVP
- [x] Search stations
- [x] Favorites
- [x] Random favorite
- [x] Startup dependency check for `mpv`
- [ ] Search by genre/tag
- [ ] Search by country
- [ ] Better station detail view
- [ ] Textual-based TUI
- [ ] Config file support
- [ ] Export/import favorites

## Data source

FluxTuner uses the public Radio Browser API to discover internet radio stations.

## License

Pending.
