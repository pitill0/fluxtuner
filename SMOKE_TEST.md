# FluxTuner Smoke Test

This document provides a lightweight validation checklist before merging, tagging or preparing a release.

The goal is not to replace automated tests, but to quickly verify that the main user workflows still work across Linux and macOS.

---

# 1. Environment

## From source checkout

```bash
git status
python --version
python -m compileall fluxtuner
```

Expected:

- repository is on the expected branch
- no unexpected local changes
- Python version is supported
- `compileall` completes without errors

---

# 2. Install / editable mode

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .
```

Expected:

- install completes successfully
- dependencies are installed
- `python -m fluxtuner` can be launched from the repository

---

# 3. Player backend detection

```bash
python -m fluxtuner --list-players
```

Expected example:

```text
Supported player backends:
  ✓ mpv (auto)
  ✓ ffplay
```

Acceptable variants:

- `mpv` only
- `ffplay` only
- both available

If no backend is available, install one of:

- `mpv`
- `ffmpeg` / `ffplay`

---

# 4. Backend factory validation

```bash
python - <<'PY'
from fluxtuner.players import available_players, selected_player_name, create_player

print("Available:", available_players())
print("Selected:", selected_player_name())
print("Class:", type(create_player()).__name__)
PY
```

Expected:

- available backend list is shown
- selected backend matches priority order
- player instance is created without errors

---

# 5. TUI launch

```bash
python -m fluxtuner
```

Expected:

- TUI opens
- station search works
- country filter works
- minimum bitrate filter works
- playback starts with selected station
- playback stops cleanly
- data usage updates while streaming

Optional explicit backend tests:

```bash
python -m fluxtuner --player mpv
python -m fluxtuner --player ffplay
```

---

# 6. GUI launch

```bash
python -m fluxtuner --gui
```

Expected:

- GTK window opens
- search results are readable
- responsive layout keeps playback controls visible
- backend is displayed in the side panel
- playback starts with selected station
- playback stops cleanly
- closing the window stops playback
- data usage updates while streaming
- favorites controls work
- tag playlist controls work

Optional explicit backend tests:

```bash
python -m fluxtuner --gui --player mpv
python -m fluxtuner --gui --player ffplay
```

---

# 7. Live metadata

Run a known stream that exposes ICY metadata.

Example validation helper:

```bash
python - <<'PY'
from fluxtuner.core.stream_metadata import fetch_stream_metadata

url = "https://playerservices.streamtheworld.com/api/livestream-redirect/977_HITS.mp3"
print(fetch_stream_metadata(url))
PY
```

Expected example:

```python
{
    "raw": "Artist - Track",
    "artist": "Artist",
    "title": "Track",
    "source": "icy",
}
```

Notes:

- many stations do not expose ICY metadata
- returning `None` is valid for streams without metadata
- GUI should keep Artist / Track as `—` when metadata is unavailable

---

# 8. macOS GTK notes

Install dependencies:

```bash
brew install gtk4 pygobject3 mpv ffmpeg
```

If using a virtual environment, confirm `python` points to the venv:

```bash
which python
```

Expected:

```text
/path/to/project/.venv/bin/python
```

If your shell aliases `python`, disable it for the current shell:

```bash
unalias python
```

If PyGObject is not visible from the venv:

```bash
PYGOBJECT_SITE_PACKAGES="$(dirname "$(find "$(brew --prefix)" -path "*/site-packages/gi/__init__.py" 2>/dev/null | head -n 1)")"
PYTHONPATH="$PYGOBJECT_SITE_PACKAGES" python -m fluxtuner --gui
```

On Apple Silicon this often resolves to:

```bash
PYTHONPATH=/opt/homebrew/lib/python3.14/site-packages \
python -m fluxtuner --gui
```

---

# 9. Linux notes

## CRUX

```bash
sudo prt-get depinst mpv
sudo prt-get depinst ffmpeg
```

## Debian / Ubuntu

```bash
sudo apt install mpv ffmpeg python3-gi gir1.2-gtk-4.0
```

## Arch Linux

```bash
sudo pacman -S mpv ffmpeg python-gobject gtk4
```

## Fedora

```bash
sudo dnf install mpv ffmpeg python3-gobject gtk4
```

---

# 10. Documentation checks

```bash
python -m fluxtuner --help
python -m fluxtuner --version
python -m fluxtuner --list-players
```

Expected:

- help output is readable
- version matches `pyproject.toml`
- player diagnostics are correct

Review visually:

- `README.md`
- `CHANGELOG.md`
- screenshots render correctly on GitHub

---

# 11. Pre-commit checklist

Before committing:

```bash
git diff
python -m compileall fluxtuner
python -m fluxtuner --list-players
```

Recommended manual checks:

- TUI launches
- GUI launches
- playback starts
- playback stops
- closing GUI stops playback
- no obvious tracebacks
- no unreadable UI text
- README renders correctly on GitHub

---

# 12. Suggested release smoke test

Before a release candidate:

```bash
python -m compileall fluxtuner
python -m fluxtuner --version
python -m fluxtuner --help
python -m fluxtuner --list-players
python -m fluxtuner
python -m fluxtuner --gui
```

If possible, also test:

```bash
python -m fluxtuner --player mpv
python -m fluxtuner --player ffplay
python -m fluxtuner --gui --player mpv
python -m fluxtuner --gui --player ffplay
```

Expected:

- no crashes
- correct backend selection
- playback works
- GUI closes cleanly
- metadata appears when available
