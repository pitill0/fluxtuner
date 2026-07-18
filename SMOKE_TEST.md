# FluxTuner Smoke Test

This document provides a lightweight validation checklist before merging, tagging or preparing a release.

The goal is not to replace automated tests, but to quickly verify that the main user workflows still work across Linux and macOS.

---

# 1. Environment

## From source checkout

```bash
git status
python --version
python -m compileall fluxtuner tests
```

Expected:

- repository is on the expected branch
- no unexpected local changes
- Python version is supported
- `compileall` completes without errors
- Web JavaScript modules pass syntax checks when Web changes are included

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

Expected behavior:

- all four supported backends are listed: `mpv`, `ffplay`, `mpg123` and
  `ogg123`;
- each backend is reported as available or missing;
- the automatically selected available backend is marked;
- capability and installation hints remain readable.

Any subset may be available locally, but at least one backend is required for
manual playback tests.

If no backend is available, install one of:

- `mpv`
- `ffmpeg` / `ffplay`
- `mpg123`
- `vorbis-tools` / `ogg123`

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

# 8. Web/server mode

Use an isolated data directory so the smoke test does not touch your regular
FluxTuner library:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-smoke \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Open:

```text
http://127.0.0.1:8080
```

Expected first-run flow:

- setup screen is shown when no administrator exists
- first administrator can be created
- login succeeds with the new administrator
- dashboard loads after login
- search works from the dashboard quick action and from the top navigation
- playback starts in the browser
- browser player `Pause`, `Resume`, `Stop` and failed-stream `Retry` states are coherent
- Android lock-screen/status-bar media controls show station metadata and artwork after playback starts
- iOS media controls show station metadata after the browser hands playback to the system
- favorites, history and playlists are accessible only after login

Account request and admin user flow:

- log out
- open Request access
- submit a new username/password
- the request is created as pending and does not log in automatically
- logging in with the pending account shows `Account pending approval.`
- log back in as admin
- pending user appears in Admin
- approving the user allows login
- rejected or deactivated users cannot log in
- user deletion is available only from the Admin danger zone
- cancelling or mistyping the delete confirmation keeps the user intact
- deleting a non-current test user removes the user from Admin and does not
  affect the current administrator session

Dashboard/privacy checks:

- normal users see only their own favorites, playlists and history metrics
- normal users do not see Admin navigation or global user metrics
- administrators see Admin, server/user metrics and pending request counts

UI checks:

- desktop and mobile layouts are readable
- light and dark themes have sufficient contrast
- Search navigation resets stale Favorites/History/Playlist results
- Request access uses the modal flow and does not crowd the login form
- public stats remain anonymous and show aggregate platform counts only
- Admin Player debug can be enabled on the current browser, clearly separates
  current snapshot from recent events, remains responsive on mobile, exports logs,
  and can be disabled again without affecting playback

---

# 9. macOS GTK notes

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

# 10. Linux notes

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

# 11. Documentation checks

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
- `docs/architecture.md`, including Mermaid diagrams
- `docs/refactor-roadmap.md`
- screenshots render correctly on GitHub

---

# 12. Pre-commit checklist

Before committing:

```bash
git diff
python -m compileall fluxtuner tests
node --check fluxtuner/web/static/app.js
node --check fluxtuner/web/static/js/*.js
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

# 13. Suggested release smoke test

Before a release candidate:

```bash
python -m compileall fluxtuner tests
node --check fluxtuner/web/static/app.js
node --check fluxtuner/web/static/js/*.js
python -m fluxtuner --version
python -m fluxtuner --help
python -m fluxtuner --list-players
python -m fluxtuner
python -m fluxtuner --gui
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-smoke FLUXTUNER_WEB_SECURE_COOKIES=false fluxtuner-web --host 127.0.0.1 --port 8080
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
