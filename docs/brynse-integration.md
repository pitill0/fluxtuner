# Brynse integration: headless contract

FluxTuner consumes the public `brynse.integrations.radio` API. Brynse owns
ingestion, metadata interpretation, boundary resolution, finalization, file
naming and stream closure. FluxTuner owns requests, profile context, destination
policy, worker scheduling and observations.

The installed contract was tested against Brynse commit
[`d7047eda161b861bfb7bfe56c99dfe7e26e014fa`](https://github.com/pitill0/brynse/tree/d7047eda161b861bfb7bfe56c99dfe7e26e014fa),
which reports version 0.1.0.

## Components

| Component | Responsibility |
| --- | --- |
| `core/ripping.py` | Requests, backend protocol, results and errors |
| `core/ripping_paths.py` | Destination calculation without filesystem writes |
| `core/ripping_requests.py` | Explicit station/profile/destination snapshot |
| `recorders/brynse.py` | Optional API loading and payload translation |
| `core/ripping_service.py` | Background run/stop workers and job snapshots |

These modules do not import GTK. Session recording remains a separate capability.

## Optional installation

From the intended checkout, using its chosen virtual environment:

```sh
python -m pip install -e .
python -m pip install -r requirements-brynse.txt
python -m pip check
```

FFmpeg must be available in PATH. The requirements file pins the tested Brynse
revision; it is not a complete transitive dependency lock. Brynse and NumPy are
not mandatory dependencies of the base FluxTuner installation.

Run commands from the intended worktree. Another checkout in the current
directory can take precedence over an editable installation.

## Availability

`BrynseRipper.availability()` checks optional imports, callable config/runner
exports and FFmpeg in PATH, without constructing a runner. It distinguishes
absence from a broken dependency or incompatible API.

This establishes local readiness, not station compatibility. The inspected
radio runner requires ICY metadata and MP3 or AAC audio.

## Requests and destinations

`build_ripping_request(...)` requires an explicit station, data directory,
persistent profile ID, profile name and operation UUID. It captures these values
without mutating the station, consulting UI selection or querying SQLite.

The caller must resolve the profile ID and name from the same profile context
and generate a fresh UUID for each new operation. Positive-ID validation does
not establish database existence or authorization.

The destination is:

```text
<data_directory>/rips/profile-<id>/<uuid.hex>/
```

The application supplies its configured data directory, including the existing
`FLUXTUNER_DATA_DIR` policy. Path calculation expands `~`, captures an absolute
destination and creates no directories. Brynse creates output directories when
the run starts. Naming within each operation remains Brynse's responsibility.

Direct `RippingRequest` construction supports caller-supplied destinations.
Its profile fields remain optional for compatibility.

## Lifecycle

`BrynseRipper.run(...)` blocks. `RippingService.start(request)` schedules it
outside the caller thread and returns a job ID. Snapshots expose `starting`,
`running`, `stopping`, `completed`, `stopped` or `failed`.

`on_started` means Brynse has opened and initialized the stream. Adapter
callbacks execute in the run thread; UI code must dispatch widget updates to
its main thread.

`RippingService.stop()` records startup cancellation or delegates
`backend.stop()` in a separate worker. Repeated requests while stopping do not
launch additional stop workers.

- During backend construction, cancellation skips `run()` after construction.
- After entering `run()` but before `on_started`, cancellation is delivered
  when that callback arrives.
- During active reading, Brynse requests stop and closes its stream.

Opening or initialization must finish or fail before deferred cancellation can
complete. There is no bounded shutdown guarantee for a blocked opening call.
FluxTuner does not replace Brynse's stop machinery or send process signals.

`wait(timeout=...)` uses one total time budget and includes a stop worker
created during the wait. Blocking waits belong outside the UI thread.
A terminal snapshot alone does not establish worker termination: check
`wait(timeout=0)`. New jobs are rejected while either worker remains alive.

## Outputs and errors

Finalized callbacks become `RippedTrack(title, path)` entries in the final
`RippingResult`. FluxTuner does not rename or rewrite those files.
`incomplete_track_title` remains separate from finalized outputs.

Adapter failures raise `RippingError` with the original cause and references
to already finalized tracks. The service exposes failures in its snapshot.
Results remain in memory; no ripping history store or SQLite migration exists.

The inspected runner passes its FFmpeg setting to analysis, while the default
output writer constructs finalizers using the default `ffmpeg` command.
The adapter resolves FFmpeg from PATH and offers no custom-binary setting.

## Validation and pending work

With the project's development dependencies installed:

```sh
python -m pytest \
  tests/test_brynse_ripper.py \
  tests/test_brynse_ripper_contract.py \
  tests/test_ripping_service.py \
  tests/test_ripping_paths.py \
  tests/test_ripping_requests.py
```

Real-runner tests skip when Brynse or FFmpeg is absent. A run with skips does
not establish the installed integration contract.

Executed on native macOS with Python 3.14: stop during reads, deferred stop
during opening, and a synthetic ICY/MP3 pipeline producing finalized files
verified by FFmpeg decoding. The opener is controlled locally; these tests
do not establish real-network or GTK behavior.

GTK wiring, application shutdown integration, Linux/Flatpak validation and
distribution packaging remain pending. No Flatpak permissions have changed.
Focused tests do not replace the full repository quality gate.

## Headless validation checkpoint: 2026-10-17

Validated on M1/native macOS with Python 3.14.4, at FluxTuner commit
`6d0041061bf15913e6790bf0708d214a8869c74b` and the Brynse revision pinned above:

- Full suite: 1099 passed, no skips; one PyGObject deprecation warning.
- Ruff formatting and lint, compileall, mypy, JavaScript syntax, Bandit and
  git diff whitespace checks passed.
- After updating only the worktree's pip to 26.2.1, pip-audit returned zero
  with no known vulnerabilities in audited packages. Brynse and FluxTuner
  were skipped because they could not be audited through PyPI.

The full suite required application data/config/cache directories dedicated to
the test run and a temporary pytest plugin redirecting these legacy sources
to nonexistent files under an empty test directory:

- `favorites.LEGACY_FAVORITES_FILE`
- `history.LEGACY_HISTORY_FILE`
- `manual_playlists.LEGACY_PLAYLISTS_FILE`
- `data_usage.LEGACY_USAGE_FILE`

XDG and `FLUXTUNER_DATA_DIR` overrides alone do not isolate these sources:
their defaults use `Path.home()`. Without legacy-source isolation, three web
tests imported personal legacy data and failed; all three passed after
isolation, followed by the full suite. Migration functions remained enabled.
The plugin was validation tooling outside the repository; repository test
isolation has not been changed. This result is not an unmodified `make gate`
run on a populated user account.

For dependency audits, select the worktree consistently through its Python,
`VIRTUAL_ENV`, PATH and `PIPAPI_PYTHON_LOCATION`.

M1 evidence files: `fluxtuner-brynse-gates-01.txt`,
`fluxtuner-brynse-legacy-isolation-check-01.txt`,
`fluxtuner-brynse-full-pytest-02.txt` and
`fluxtuner-brynse-pip-audit-03.txt`, under Downloads.

GTK, real-network behavior, application shutdown, Linux/Flatpak and packaging
remain pending as described above.
