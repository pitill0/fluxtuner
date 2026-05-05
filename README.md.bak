# 🎧 FluxTuner

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![TUI](https://img.shields.io/badge/TUI-Textual-purple)
![Player](https://img.shields.io/badge/player-mpv-orange)
![GitHub stars](https://img.shields.io/github/stars/pitill0/fluxtuner)
![GitHub forks](https://img.shields.io/github/forks/pitill0/fluxtuner)
![GitHub issues](https://img.shields.io/github/issues/pitill0/fluxtuner)

A modern terminal-based internet radio player with powerful search, playlists, theming, and a clean TUI.

Built with Python, powered by mpv, and designed for daily use.

---

## ✨ Features

* 🔎 Search internet radio stations (name, genre, country)
* ▶️ Play streams with mpv (fast & lightweight)
* ⭐ Favorites with custom names and tags
* 🧠 Smart Play (random by tag or playlist)
* 📂 Persistent playlists + dynamic tag playlists
* 🎨 Full theming system with live preview
* 📊 Structured table view (clean and readable)
* 🎛️ Volume, mute and playback control
* 🧩 Clean modular architecture

---

## 📸 Screenshots

### 🔎 Search & Playback

![Search](screenshots/search.png)

### ⭐ Favorites & Playlists

![Favorites](screenshots/favorites.png)

### 🎨 Theme Selector

![Themes](screenshots/themes.png)

---
## 🚀 Installation & Usage

### Requirements

FluxTuner requires:

- Python 3.10+
- mpv
- A terminal emulator with good Unicode support

The GTK desktop GUI is currently experimental and requires GTK4 + PyGObject.

---

### Install mpv

```bash
# CRUX
sudo prt-get depinst mpv

# Debian / Ubuntu
sudo apt install mpv

# Arch Linux
sudo pacman -S mpv

# Fedora
sudo dnf install mpv

# macOS
brew install mpv
```

Check that mpv is available:

```bash
mpv --version
```

---

## ▶️ Running FluxTuner

### Option 1 — Run directly from source

This is the simplest option for testing or development:

```bash
git clone https://github.com/pitill0/fluxtuner.git
cd fluxtuner
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m fluxtuner
```

This starts the default TUI interface.

---

### Option 2 — Run the installed command

After installing with `pip install -e .`, you can run:

```bash
fluxtuner
```

Equivalent to:

```bash
python -m fluxtuner
```

---

### Option 3 — Install with pipx from GitHub

Recommended if you want to use FluxTuner as a standalone command:

```bash
pipx install git+https://github.com/pitill0/fluxtuner.git
fluxtuner
```

To install a specific release:

```bash
pipx install git+https://github.com/pitill0/fluxtuner.git@v0.1.0
```

To upgrade:

```bash
pipx upgrade fluxtuner
```

To uninstall:

```bash
pipx uninstall fluxtuner
```

---

## 🖥️ Run modes

### TUI mode

FluxTuner starts in TUI mode by default:

```bash
fluxtuner
```

or:

```bash
python -m fluxtuner
```

You can also make it explicit:

```bash
fluxtuner --tui
```

---

### Experimental GTK GUI mode

FluxTuner includes an early GTK desktop GUI scaffold:

```bash
fluxtuner --gui
```

or:

```bash
python -m fluxtuner --gui
```

The GUI is experimental and currently intended for development/testing.

---

### Select player backend

FluxTuner currently supports `mpv`:

```bash
fluxtuner --player mpv
```

The player layer is modular and prepared for future backends such as `mplayer` or `gstreamer`.

---

### Themes

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

---

### Useful commands

```bash
# Show help
fluxtuner --help

# Show version
fluxtuner --version

# Clear search cache
fluxtuner --clear-cache

# Export favorites
fluxtuner --export-favs favorites.json

# Import favorites
fluxtuner --import-favs favorites.json

# Export playlists
fluxtuner --export-playlists playlists.json

# Import playlists
fluxtuner --import-playlists playlists.json
```

---

## 🍎 macOS GTK development note

When using a Python virtual environment, PyGObject installed via Homebrew may not be visible inside the venv.

Install GTK dependencies:

```bash
brew install gtk4 pygobject3 mpv
```

If the GUI fails with:

```text
ModuleNotFoundError: No module named 'gi'
```

run FluxTuner with Homebrew's PyGObject path:

```bash
PYGOBJECT_SITE_PACKAGES="$(dirname "$(find "$(brew --prefix)" -path "*/site-packages/gi/__init__.py" 2>/dev/null | head -n 1)")"
PYTHONPATH="$PYGOBJECT_SITE_PACKAGES" python -m fluxtuner --gui --player mpv
```

On Apple Silicon this often resolves to a path similar to:

```bash
PYTHONPATH=/opt/homebrew/lib/python3.14/site-packages \
python -m fluxtuner --gui --player mpv
```

Your Python version may differ. To find the correct path:

```bash
find "$(brew --prefix)" -path "*site-packages/gi/__init__.py" 2>/dev/null
```

---

## ⌨️ Keybindings

| Key | Action |
|---|---|
| `/` | Focus search |
| `Enter` | Play selected station |
| `x` | Stop playback |
| `Space` | Pause / Resume |
| `+ / -` | Volume up / down |
| `m` | Mute |
| `a` | Add to favorites |
| `f` | Open favorites |
| `d` | Remove favorite |
| `e` | Edit favorite name |
| `g` | Edit favorite tags |
| `p` | Open playlists |
| `n` | New playlist |
| `b` | Add to playlist |
| `t` | Filter by tag / open theme selector depending on context |
| `h` | History |
| `l` | Play last station |
| `q` | Quit |

---

## 🎨 Themes

* Built-in themes: default, nord, dracula, amber, ptmtrx
* Live preview in selector
* Apply with `Enter`
* Save with `y`

---

## 📁 Data storage

* Favorites: `~/.fluxtuner_favorites.json`
* Playlists: `~/.fluxtuner_playlists.json`
* Config: `~/.config/fluxtuner/config.json`

---

## 🤝 Contributing

PRs are welcome.

---

## 💼 Commercial Use

FluxTuner is open source and available under the MIT license.

You are free to use, modify, and distribute it, including for commercial purposes.

That said, if you plan to integrate FluxTuner into a commercial product, service, or distribution, please consider reaching out.

Contributions, attribution, or collaboration are always appreciated.

---

## 📄 License

MIT

---

## 🙌 Support the project

If you find FluxTuner useful:
- ⭐ Star the repository
- 🐛 Report issues
- 💡 Suggest improvements

Your support helps shape the future of the project.

