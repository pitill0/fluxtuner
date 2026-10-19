# GTK persistent playlists validation

Validated on 2026-10-19 on native M1/macOS with Python 3.14.4.
Implementation base: FluxTuner `f530b65`.

## Automated checks

- Focused GTK and playlist tests: 194 passed.
- Full repository suite: 1252 passed, no skips or deselections.
- One known PyGObject deprecation warning.
- Ruff formatting/lint, compileall, mypy, JavaScript syntax, pip check,
  Bandit and git diff whitespace checks passed.
- pip-audit found no known vulnerabilities in audited packages.
  Brynse could not be audited through PyPI.

The full suite used dedicated application directories and an external pytest
plugin redirecting legacy favorites, history, playlists and usage files to
nonexistent paths in an isolated directory. Migration functions remained
enabled. This was not an unmodified make gate run on a populated account.

## Native GTK smoke

The manual M1 smoke used a separate data directory. The tester confirmed
playlist navigation, creation, invalid/duplicate names, cancellation,
explicit clicked-station targeting, membership removal, confirmed deletion
and the collapsed favorite-tag filters.

The application closed normally. Its final data retained the test favorites.
Automated storage contracts separately verify profile isolation and that
removing membership or deleting a playlist preserves favorites.

## Evidence

Files under the M1 Downloads directory:

- `fluxtuner-playlists-contracts-docs-10.txt`
- `fluxtuner-playlists-validation-11.txt`
- `fluxtuner-playlists-gtk-smoke-09.txt`
