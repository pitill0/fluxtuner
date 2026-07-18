# Contributing to FluxTuner

Thanks for considering a contribution to FluxTuner.

FluxTuner is a lightweight internet radio platform with a Textual terminal UI, GTK GUI, browser-based Web/server mode and modular playback backends.

This document explains the preferred workflow for local development, pull requests, validation and releases.

## Engineering process

Before contributing, review the project's [engineering process](docs/ENGINEERING-PROCESS.md).

FluxTuner uses an AI-assisted development workflow under human direction. AI tools may assist with implementation, refactoring, testing, documentation and analysis, but proposed changes remain subject to human review, project validation and human acceptance.

---

## Project direction

FluxTuner aims to remain:

- terminal-first, while keeping the GTK GUI and Web/server mode useful and coherent
- keyboard-friendly
- lightweight
- themeable
- explicit about playback backend capabilities
- respectful of user control during playback
- stable across `mpv`, `ffplay`, `mpg123` and `ogg123` where supported

When in doubt, prefer small, focused changes over broad refactors.

---

## Local development

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the project in editable mode with development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run FluxTuner:

```bash
python -m fluxtuner
```

Useful commands:

```bash
python -m fluxtuner --version
python -m fluxtuner --help
python -m fluxtuner --list-players
python -m fluxtuner --list-themes
python -m fluxtuner --player mpv
python -m fluxtuner --player ffplay
python -m fluxtuner --gui --player mpv
python -m fluxtuner --gui --player ffplay
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Legacy CLI mode:

```bash
python -m fluxtuner --cli
```

---

## Development workflow

Use a feature branch for any functional, UX, packaging or documentation change:

```bash
git checkout main
git pull
git checkout -b feature/<short-description>
```

Make the change locally, then run the checks and manual validation relevant to the change.

Commit with a clear message:

```bash
git add ...
git commit -m "feat(gui): add history view"
```

Push the branch and open a pull request:

```bash
git push -u origin feature/<short-description>
```

Preferred flow:

```text
feature branch → local checks → pull request → CI green → squash and merge → clean branch
```

Avoid pushing functional changes directly to `main`.

---

## Pull request checklist

Before opening a pull request, check that:

- The change has a clear and limited scope.
- The branch is up to date with `main`.
- New user-facing text is in English.
- `CHANGELOG.md` is updated when the change affects users, behavior, packaging or documentation.
- The relevant UI flow has been manually validated.
- The PR description includes a short validation summary.

Suggested PR description format:

```markdown
## Summary

- What changed.
- Why it changed.

## Validation

- Ran `python -m ruff check .`
- Ran `python -m ruff format --check .`
- Ran `python -m compileall fluxtuner tests`
- Ran `python -m pytest`
- Ran `python -m mypy --follow-imports=skip fluxtuner/`
- Ran `pip-audit --local`
- Ran `bandit -r fluxtuner -c pyproject.toml`
- Ran `node --check fluxtuner/web/static/app.js` when Web UI JavaScript changed
- Manual validation performed:
  - ...
```

---

## Required checks

For a full local release-quality gate, run:

```bash
make gate
```


Run these before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m compileall fluxtuner tests
python -m pytest
```

If the change is documentation-only, these checks may not always be required, but they are recommended before merging anything that touches code, packaging, tests or project metadata.

---

## Manual validation

Automated tests do not replace manual validation for playback and UI changes.

Choose the smallest validation scope that covers the change.

### TUI validation

Use when touching TUI, playback, favorites, playlists, history, station display helpers, metadata or data usage:

```bash
python -m fluxtuner --player mpv
python -m fluxtuner --player ffplay
```

Common checks:

- Search for a station, for example `bbc`.
- Select a station.
- Play and stop.
- Confirm the `▶` marker reflects the current station.
- Confirm `★` reflects favorite state.
- Check favorites if affected.
- Check playlists if affected.
- Check history if affected.
- Check data usage and metadata if affected.
- Confirm `mpv` live volume/mute behavior when relevant.
- Confirm `ffplay` does not expose misleading live controls.

### GTK GUI validation

Use when touching GUI, playback, favorites, history, playlists or status messages:

```bash
python -m fluxtuner --gui --player mpv
python -m fluxtuner --gui --player ffplay
```

Common checks:

- Search results render correctly.
- Selecting a row updates details.
- Double-click or Play starts playback.
- Stop stops playback.
- Only one station is marked as current.
- Favorite markers remain coherent.
- Favorites can be shown and edited if affected.
- History can be shown if affected.
- Tag playlist flow works if affected.
- `mpv` volume and mute controls work live.
- `ffplay` volume and mute controls are disabled or clearly unsupported.
- Closing the window does not leave backend processes running.

### Web/server validation

Use when touching Web routes, browser controllers, authentication, sessions,
metadata, account administration or responsive layout:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Use an isolated data directory and validate the smallest affected authenticated,
administrator and browser playback flows.

---

## Playback backend expectations

FluxTuner supports multiple playback backends. Changes should preserve their different capabilities.

### mpv

`mpv` is the recommended backend.

Expected behavior:

- Play/Stop works.
- Live volume works.
- Live mute works.
- Process/socket cleanup works when playback stops or the app exits.

### ffplay

`ffplay` is a lightweight fallback.

Expected behavior:

- Play/Stop works.
- Live volume is not advertised as supported.
- Live mute is not advertised as supported.
- User-facing messages should explain unsupported live changes clearly.
- Process cleanup should be reliable when replacing or stopping streams.

---

## Tests

Prefer tests for pure logic and persistence behavior.

Good candidates:

- Core helpers.
- Station normalization/display helpers.
- Player backend capability semantics.
- Persistence and migration behavior.
- Import/export behavior.
- CLI flows that can be tested non-interactively.

Usually avoid heavy tests for:

- Real GTK windows.
- Visual Textual rendering.
- Real network calls to Radio Browser.
- Real playback with `mpv` or `ffplay` in CI.

For UI changes, use focused manual validation and add unit tests only if the change extracts testable logic.

---

## Changelog policy

Update `CHANGELOG.md` under `[Unreleased]` when a change is user-visible.

Use:

- `Added` for new features.
- `Changed` for behavior or UX changes.
- `Fixed` for bug fixes.

Examples:

```markdown
### Added

- Added a History view to the GTK GUI, matching the existing TUI history flow.

### Changed

- Improved GTK GUI status messages for search, favorites, history and tag playlist views.

### Fixed

- Fixed GTK GUI playback history persistence so played stations are available from the shared history.
```

Do not create a new version section until preparing a release.

---

## Release workflow

A release should have at least one clear reason:

- User-visible feature.
- Bug fix.
- Player backend fix.
- Packaging/Flatpak improvement.
- Meaningful documentation or validation update.
- Small coherent UX polish batch.

Before preparing a release, start from an up-to-date, clean `main` branch:

```bash
git switch main
git pull --ff-only
git status --short
```

Prepare the release metadata:

1. Update the version in `pyproject.toml`. This is the package version source;
   `fluxtuner.__version__` is resolved from installed package metadata and must
   not be edited separately.
2. Move the relevant `[Unreleased]` entries into a dated release section in
   `CHANGELOG.md`.
3. Add the release to
   `flatpak/io.github.pitill0.Fluxtuner.metainfo.xml` when publishing a new
   Flatpak-facing release.
4. Update Flatpak source metadata or validation evidence only when that release
   changes the Flatpak package or its permissions.

Run the complete release-quality gate and build both distribution artifacts:

```bash
make gate
rm -rf build dist *.egg-info
python -m build
python -m pip install --force-reinstall dist/*.whl
fluxtuner --version
fluxtuner --help
fluxtuner --list-players
fluxtuner --list-themes
```

Perform the smallest relevant manual validation from the sections above for
TUI, GTK, Web/server and Flatpak behavior affected by the release.

Commit the release preparation and open a pull request. Create the release tag
only after that pull request has passed CI and has been merged:

```bash
git switch main
git pull --ff-only
git tag -a vX.Y.Z -m "FluxTuner X.Y.Z"
git push origin vX.Y.Z
```

Then:

1. Publish the GitHub release from the pushed tag.
2. Attach or verify the generated source and wheel artifacts as appropriate.
3. Update the Flathub manifest to the immutable release tag and source checksum
   when the release is intended for Flathub.
4. Build and validate the resulting Flatpak before submitting the Flathub
   change.

---

## Flatpak and AppStream

Flatpak-related files live under `flatpak/` and the Flathub manifest references tagged upstream releases.

When changing Flatpak metadata:

```bash
appstreamcli validate flatpak/io.github.pitill0.Fluxtuner.metainfo.xml
```

A known pedantic warning may appear because the current app-id contains uppercase letters:

```text
cid-contains-uppercase-letter io.github.pitill0.Fluxtuner
```

Do not rename the app-id just to silence this warning. Keep the app-id consistent unless a deliberate migration is planned.

For local Flatpak builds:

```bash
flatpak-builder --force-clean build-dir flatpak/io.github.pitill0.Fluxtuner.yml
```

On CRUX Linux, use:

```bash
flatpak-builder \
  --force-clean \
  --disable-rofiles-fuse \
  build-dir \
  flatpak/io.github.pitill0.Fluxtuner.yml
```

---

## Documentation and validation logs

Flatpak manual validation records are stored under:

```text
flatpak/docs/validation/
```

Historical release evidence and focused permission reviews use one Markdown
file per validation scope, for example:

```text
flatpak/docs/validation/v0.2.6.md
flatpak/docs/validation/permission-share-ipc.md
```

These files are meant to capture manual QA evidence and should complement, not replace, `CHANGELOG.md`.

---

## Style guidelines

- Keep changes small and reviewable.
- Avoid broad refactors without a concrete reason.
- Keep user-facing text clear and concise.
- Preserve TUI/GUI behavior parity where practical.
- Preserve backend capability honesty.
- Prefer shared helpers only when they reduce duplication without hiding UI-specific behavior.
- Do not remove legacy behavior without a release note or migration plan.

---

## Cleaning up branches

After a PR is merged:

```bash
git checkout main
git pull
git branch --delete feature/<short-description>
git push origin --delete feature/<short-description>
```

Use force deletion only when you are sure the branch was squash-merged or is no longer needed:

```bash
git branch -D feature/<short-description>
```
