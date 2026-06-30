# Development Guide

This guide explains how to set up a local FluxTuner development environment, run the app, execute tests, and validate changes before opening a pull request.

## Requirements

FluxTuner is a Python application with CLI, TUI, and optional GTK GUI entry points.

Recommended local tools:

- Python 3.11 or newer.
- `pip`.
- `venv`.
- `mpv` and/or `ffplay` for broad manual playback testing.
- Optional lightweight players: `mpg123` and `ogg123`.
- Git.
- Optional: Flatpak tooling if you work on packaging.

The CI currently validates supported Python versions, package builds, dependency audits, static security checks, and tests.

## Clone the repository

```bash
git clone https://github.com/pitill0/fluxtuner.git
cd fluxtuner
```

## Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## Install development dependencies

Install FluxTuner in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

If you only want to install runtime dependencies:

```bash
python -m pip install -e .
```

## Run FluxTuner locally

Default TUI:

```bash
python -m fluxtuner
```

Legacy CLI:

```bash
python -m fluxtuner --cli
```

GTK GUI:

```bash
python -m fluxtuner --gui
```

List player backends:

```bash
python -m fluxtuner --list-players
```

List available themes:

```bash
python -m fluxtuner --list-themes
```


Web/server mode with isolated development data:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Run with debug logging:

```bash
python -m fluxtuner --verbose
```

or:

```bash
FLUXTUNER_DEBUG=1 python -m fluxtuner
```

Debug logs are intended for development and diagnostics. They should not expose stream URLs, station names, full local paths, imported data contents, or unnecessary user data.

## Player backends

FluxTuner supports external player backends such as:

- `mpv`
- `ffplay`
- `mpg123`
- `ogg123`

Install at least one backend locally for manual playback testing.

Examples:

```bash
sudo apt install mpv
```

or:

```bash
sudo apt install ffmpeg
```

`ffplay` is usually provided by FFmpeg packages.

The automated test suite mocks player execution and should not require external player binaries to be installed.

## Project structure

Commonly edited areas:

```text
fluxtuner/
  __main__.py              CLI entry point and import/export commands
  config.py                User configuration and playback state
  logging_config.py        Project logging configuration
  paths.py                 XDG/user data path helpers
  theme_runtime.py         Runtime theme application helpers

fluxtuner/core/
  api.py                   Radio Browser API integration
  cache.py                 Search cache
  data_usage.py            Playback data usage tracking
  favorites.py             Favorites persistence and updates
  history.py               Playback history
  importers.py             Import validation for favorites/playlists
  manual_playlists.py      User-managed playlists
  playlists.py             Built-in playlist/tag helpers
  stations.py              Station normalization helpers
  storage.py               Atomic JSON writes
  stream_metadata.py       ICY stream metadata parsing

fluxtuner/web/
  app.py                   FastAPI Web/server entry point and routes
  auth.py                  Password hashing, sessions and Web auth helpers
  admin_cli.py             Emergency Web user administration CLI
  templates/               Browser UI shell
  static/                  Web CSS, JS and static assets

fluxtuner/players/
  base.py                  Player interface and errors
  ffplay.py                ffplay backend
  mpv.py                   mpv backend
  security.py              Player executable and stream URL validation

fluxtuner/gui/
  app.py                   GTK GUI entry point
  window.py                GTK GUI window

tests/
  test_*.py                Unit and regression tests
```

## Local validation commands

Before opening a pull request, run the same core checks used in CI.

### Formatting and linting

```bash
ruff check .
ruff format --check .
```

To apply formatting:

```bash
ruff format .
```

### Compile check

```bash
python -m compileall fluxtuner tests
```

### Tests

```bash
python -m pytest
```

Run a focused subset while developing:

```bash
python -m pytest tests/test_api.py
python -m pytest tests/test_main.py
python -m pytest tests/test_players_mpv.py tests/test_players_ffplay.py
```

### Build package

```bash
python -m build
```

### Dependency audit

Run this from a clean virtual environment to avoid auditing unrelated system packages:

```bash
python -m pip install pip-audit
pip-audit --local
```

Expected note for editable local installs:

```text
fluxtuner Dependency not found on PyPI and could not be audited
```

That is expected because the local project itself is not a published PyPI dependency. The important result is that no known vulnerabilities are found in installed dependencies.

### Static security analysis

```bash
bandit -r fluxtuner -c pyproject.toml
```

Bandit scans production code only. Subprocess-related skips are limited to the external player backends, which intentionally launch `mpv` or `ffplay`.

## Full local check

A useful pre-PR sequence:

```bash
ruff check .
ruff format --check .
python -m compileall fluxtuner tests
python -m pytest
python -m mypy --follow-imports=skip fluxtuner/
node --check fluxtuner/web/static/app.js
python -m build
pip-audit --local
bandit -r fluxtuner -c pyproject.toml
```

## Working with branches and pull requests

Recommended workflow:

```bash
git checkout main
git pull
git checkout -b area/short-description
```

Make focused changes, then run validation.

Commit message examples:

```bash
git commit -m "Validate imported favorites and playlists"
git commit -m "Add Bandit security analysis to CI"
git commit -m "Add persistence error logging"
```

Push and open a PR:

```bash
git push -u origin area/short-description
```

A good PR should include:

- Summary of what changed.
- Validation commands run locally.
- Linked issue, for example `Closes #15` or `Part of #20`.
- Notes about scope or intentional follow-up work.

## Testing guidelines

Prefer small, focused tests that cover behavior rather than implementation details.

Good candidates for tests:

- Web authentication, authorization, CSRF and account approval flows.
- User/profile isolation in Web/server mode.
- Dashboard payload privacy for normal users and administrators.
- URL validation.
- Import validation.
- Atomic persistence.
- Error handling and fallback behavior.
- Player command construction without requiring real player binaries.
- Radio Browser API failure handling.
- ICY metadata parsing limits.
- Runtime theme parsing and application.

Avoid tests that depend on:

- A real network call.
- Installed player binaries.
- User-specific local paths.
- A specific terminal size, unless isolated/mocked.
- GUI availability unless the test is explicitly marked or isolated as a smoke test.

## Logging guidelines

FluxTuner uses opt-in debug logging through:

```bash
python -m fluxtuner --verbose
```

or:

```bash
FLUXTUNER_DEBUG=1 python -m fluxtuner
```

When adding logs:

- Use `get_logger(__name__)`.
- Prefer `debug` for diagnostic details.
- Use `warning` or `error` when a fallback or failure matters operationally.
- Avoid logging stream URLs.
- Avoid logging station names unless there is a strong reason.
- Avoid logging full local paths.
- Avoid logging imported/exported data contents.
- Use `exc_info=True` for debugging exceptions when useful.

Example:

```python
from fluxtuner.logging_config import get_logger

logger = get_logger(__name__)

try:
    ...
except OSError:
    logger.warning("Could not read favorites data; returning empty favorites", exc_info=True)
    return []
```

## Security guidelines

Security-sensitive areas include:

- Player subprocess execution.
- Stream URL validation.
- Imported JSON files.
- Local user data persistence.
- ICY stream metadata parsing.
- Dependency updates.
- Packaging and Flatpak permissions.
- Web sessions, cookies, CSRF, account registration and administrator actions.

When changing these areas:

- Keep validation explicit.
- Avoid broad exception swallowing without logs.
- Avoid `shell=True`.
- Do not pass unvalidated URLs to player backends.
- Keep local writes atomic where possible.
- Add tests for failure paths.
- Run Bandit and dependency audit before opening a PR.

See also:

```text
SECURITY.md
```

## Import/export notes

Favorites and playlists can be imported/exported as JSON from the CLI.

Exports should preserve user data.

Imports should validate incoming structures before persisting them. Invalid items should be skipped, and imports with no valid items should fail safely.

Relevant commands:

```bash
python -m fluxtuner --export-favs favorites.json
python -m fluxtuner --import-favs favorites.json
python -m fluxtuner --export-playlists playlists.json
python -m fluxtuner --import-playlists playlists.json
```

## Runtime theme notes

FluxTuner themes are TCSS files.

At startup, Textual loads the selected theme directly. At runtime, FluxTuner also supports applying a practical subset of TCSS declarations without relying on Textual development CSS watching.

Runtime theme support intentionally parses only a limited subset:

- Supported selectors are listed in `fluxtuner/theme_runtime.py`.
- Variables such as `$surface` are ignored at runtime.
- Unsupported selectors are ignored.
- Unsupported style properties are logged at debug level and skipped.

## Flatpak notes

Flatpak work may require additional local tooling.

The exact Flatpak workflow depends on the manifest and packaging setup. If you work on Flatpak permissions or packaging, validate the package manually in addition to normal Python checks.

## Troubleshooting

### `pip-audit --local` reports unrelated system packages

Make sure your virtual environment is active:

```bash
which python
which pip
which pip-audit
```

If the audit reports unrelated packages such as system tools, recreate a clean virtual environment and reinstall the project:

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install pip-audit
pip-audit --local
```

### Player tests fail because `mpv` or `ffplay` is missing

Automated tests should mock player executable resolution. If a test requires real player binaries, adjust the test to mock:

```python
monkeypatch.setattr("fluxtuner.players.mpv.resolve_executable", lambda _name: "/usr/bin/mpv")
monkeypatch.setattr("fluxtuner.players.ffplay.resolve_executable", lambda _name: "/usr/bin/ffplay")
```

### Logs are not visible

Enable debug logging:

```bash
python -m fluxtuner --verbose
```

or:

```bash
FLUXTUNER_DEBUG=1 python -m fluxtuner
```

### Runtime theme changes do not apply as expected

Check that the selector and property are supported by `fluxtuner/theme_runtime.py`.

Runtime theme application is intentionally limited and may not support every TCSS feature.
