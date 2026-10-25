# Brynse integration: headless contract and GTK usage

FluxTuner consumes the public `brynse.integrations.radio` API. Brynse owns
ingestion, metadata interpretation, boundary resolution, finalization, file
naming and stream closure. FluxTuner owns requests, profile context, destination
policy, worker scheduling and observations.

The optional requirements pin Brynse commit
[`e8418776e54ba7df4f3c5abeca5dc1033c7322c6`](https://github.com/pitill0/brynse/tree/e8418776e54ba7df4f3c5abeca5dc1033c7322c6),
which corresponds to Brynse v0.1.1. Historical validation checkpoints below
retain their original Brynse revisions.

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

## Automatic filename ordering

FluxTuner leaves Brynse's metadata-order setting at its default, `auto`.
Brynse selects a verified stream profile using the requested URL.

For Jazz Radio Classic Jazz, the HTTP and HTTPS URLs at
`jazz-wr01.ice.infomaniak.ch/jazz-wr01-128.mp3` use title-artist metadata.
Brynse saves an unambiguous `Song - Artist` title as `Artist - Song.mp3`.
The profile accepts the default port or no explicit port, with no query
string or URL credentials. Unknown stream URLs preserve the received order;
the profile does not apply to the whole host or other Jazz Radio stations.

Only filenames are reordered. `RippedTrack.title` retains the original
stream metadata, while `RippedTrack.path` identifies the finalized file.
FluxTuner needs no additional setting and performs no renaming.

The synthetic output contract covers both profiled protocols and an unknown
URL through the real Brynse runner, including original metadata preservation
and FFmpeg decoding of finalized files. It uses a local controlled source.

## GTK integration

Launch `python -m fluxtuner --gui` from the intended environment after installing
the optional dependency. GTK checks availability in a worker and delivers the
result through the GLib main context. A menu opened before that check completes
must be reopened to reflect the result.

The station context menu exposes `Rip tracks` when the capability is available
and no previous job has live workers. Actions receive the clicked station
explicitly and preserve the current selection. Requests capture the resolved
stream URL, persistent profile context and a fresh operation UUID.

Only one ripping job can run at a time. `Stop ripping` is offered for the
matching station/profile while starting or running, including when local
availability is no longer reported. During stopping, another job cannot start.

`gui/gtk_ripping.py` provides coordination and projection helpers without GTK
widget construction. `MainWindow` owns widgets, GLib scheduling and status
updates. It polls readiness before reading the snapshot and continues polling
terminal states until both workers finish, including late output updates.

Actual shutdown requests stop once and polls worker readiness without blocking
the UI thread. Window close and explicit tray Quit complete after worker
cleanup. Closing to a compatible Linux tray only hides the window and leaves
the application running. Playback and session recording cannot restart once
actual shutdown begins. The deferred-opening limitation described above still
applies to backend cleanup. GTK now uses a monotonic 12-second waiting
deadline and asks whether to keep waiting or quit anyway. Reaching that
deadline does not kill Python threads or prove that files are finalized.

Errors are contained and reported in the status label. Final statuses show
finalized track counts and, when tracks exist, the destination. Filenames and
incomplete-track decisions remain Brynse's responsibility.

## Automated validation

With the project's development dependencies installed:

```sh
python -m pytest \
  tests/test_brynse_ripper.py \
  tests/test_brynse_ripper_contract.py \
  tests/test_ripping_service.py \
  tests/test_ripping_paths.py \
  tests/test_ripping_requests.py
```


### Mandatory Brynse CI contracts

The dedicated `brynse-contracts` GitHub Actions job runs on Ubuntu
with Python 3.12 and FFmpeg. It installs the exact Brynse revision
from `requirements-brynse.txt`.

The job verifies the installed Brynse commit using distribution
metadata and requires the real radio integration to import.

To reproduce the contracts locally, install FFmpeg and run these
commands inside a dedicated virtual environment:

    python -m pip install -e ".[dev]"
    python -m pip install -r requirements-brynse.txt
    python -m pip install "pytest-json-report>=1.5,<2"
    python -m pytest -q --strict-markers --json-report \
      --json-report-file=brynse-contracts.json \
      tests/test_brynse_ripper_contract.py

The CI requires at least seven collected contracts. Every collected
contract must pass, with no skips, failures or errors.

The general quality matrix continues to test FluxTuner without
requiring optional Brynse.

These contracts use controlled synthetic sources and FFmpeg. They
do not replace native GTK or real-network smoke tests.

Updating the pinned Brynse revision remains dependent on resolving
Brynse issue #5.

Real-runner tests skip when Brynse or FFmpeg is absent. A run with skips does
not establish the installed integration contract.

Executed on native macOS with Python 3.14: stop during reads, deferred stop
during opening, and a synthetic ICY/MP3 pipeline producing finalized files
verified by FFmpeg decoding. The opener is controlled locally; these tests
do not establish real-network or GTK behavior.

GTK orchestration, availability, status projection, menu policy, stop and
shutdown behavior also have automated coverage under `tests/test_gtk_*.py`,
including app/tray quit coordination. These tests complement the controlled
real-runner tests above and the manual validation below.

Focused tests do not replace the full repository quality gate.

## Headless validation checkpoint: 2026-10-17

Validated on M1/native macOS with Python 3.14.4, at FluxTuner commit
`6d0041061bf15913e6790bf0708d214a8869c74b` and Brynse revision
`d7047eda161b861bfb7bfe56c99dfe7e26e014fa`:

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

At this historical checkpoint, GTK, real-network behavior and application
shutdown were still pending. The following checkpoint records their subsequent
implementation and M1 validation.

## GTK validation checkpoint: 2026-10-18

Validated on M1/native macOS with Python 3.14.4 and Brynse revision
`d7047eda161b861bfb7bfe56c99dfe7e26e014fa`:

- Full suite: 1220 passed, no skips; one known PyGObject deprecation warning.
  The renderer smoke test now reloads the module explicitly so its
  initialization check does not depend on test collection/import order.
- Ruff formatting/lint, compileall, mypy, JavaScript syntax, pip check,
  Bandit and git diff whitespace checks passed. The renderer test correction
  was followed by focused tests and another full-suite run.
- pip-audit reported no known vulnerabilities in audited packages; Brynse and
  FluxTuner were skipped because they could not be audited through PyPI.
- A native GTK close test with controlled run/stop workers verified main-loop
  responsiveness, one-time cleanup and deferred close until both workers
  finished, even when the snapshot was already terminal.
- Manual full-GUI validation confirmed explicit clicked-station targeting,
  unchanged selection, station-specific stop, capture, stop/restart readiness
  and close behavior.
- A real Jazz Radio Classic Jazz ICY/MP3 stream produced nine finalized MP3
  tracks. The saved tracks were manually checked and accepted. The final
  incomplete title remained separate; the job stopped and both workers
  finished.
- An earlier station failed because its response lacked the Content-Type
  needed for automatic codec detection. The error appeared in GTK and did
  not prevent starting a subsequent job. A playback timeout was also observed;
  this validation does not establish its cause.

The full suite used dedicated application directories and the external
legacy-source isolation plugin described in the headless checkpoint. These
results are not an unmodified `make gate` run on a populated user account.

M1 evidence under Downloads:

- `fluxtuner-brynse-final-gates-01.txt` records the quality checks and the
  initial renderer import-order failure.
- `fluxtuner-brynse-import-isolation-green-01.txt` records the corrected
  renderer test, nine focused passes and the final 1220-test full-suite pass.
- `fluxtuner-brynse-gtk-close-native-smoke-01.txt` records controlled native
  GTK close behavior.
- `fluxtuner-brynse-gtk-real-smoke-01.txt` records the live GUI capture.

## Filename ordering validation checkpoint: 2026-10-19

Validated on M1/native macOS with Python 3.14.4 and Brynse revision
`23971964c7d53da520351a4bbd322b078fdae07d`:

- Before updating Brynse, the synthetic filename contract failed for both
  profiled protocols and passed for the unknown URL.
- After updating, all 33 adapter and real-runner contract tests passed.
  The contracts preserve original metadata and decode finalized MP3 files.
- Full suite: 1222 passed, no skips; one known PyGObject deprecation warning.
  Validation used dedicated application directories and the external
  legacy-source isolation plugin described in the historical checkpoints.
- Ruff formatting/lint, compileall, mypy, JavaScript syntax, pip check,
  Bandit and git diff whitespace checks passed.
- pip-audit reported no known vulnerabilities in audited packages.
  Brynse was skipped because it could not be audited through PyPI.
- A live native GTK run using the HTTP Jazz Radio Classic Jazz endpoint
  finalized four tracks with artist-first filenames. Observed callbacks
  retained the original title-first metadata. All four files passed FFmpeg
  decoding after stopping the job and closing the application normally.

M1 evidence under Downloads: `fluxtuner-brynse-update-red-03.txt`,
`fluxtuner-brynse-update-green-04.txt`,
`fluxtuner-brynse-update-validation-05.txt` and
`fluxtuner-brynse-update-gtk-06.txt`.

## Remaining scope and limits

- Linux and Flatpak integration, sandbox behavior and distribution packaging
  have not been validated for Brynse. The optional dependency is not bundled
  by this integration and no Flatpak permissions have changed.
- Live AAC capture has not been validated by the M1 network smoke test.
- The service has no persistent ripping history or track browser.
- Additional stream profiles and segmentation or filename refinements belong
  to Brynse. Unknown stream URLs preserve the received metadata order;
  FluxTuner keeps the filenames supplied by Brynse.

## GTK shutdown confirmation and deadlines

When quitting FluxTuner with an active or pending recording, GTK asks for
confirmation before requesting an orderly stop. Cancelling does not stop
recording work. Closing to the system tray does not initiate shutdown.

FFmpeg stopping runs in a supervised worker outside the GTK main thread.
Brynse workers are polled independently. Automatic shutdown requires both
workers to finish without a reported error.

A monotonic 12-second deadline controls the waiting dialog. The deadline
never forces an exit. Users may choose **Keep waiting** to continue supervising
the workers or **Quit anyway** to explicitly authorize termination.

An FFmpeg backend stop may escalate from SIGINT to SIGKILL. A successful
return from the backend does not independently prove that the output file
was finalized gracefully. This limitation requires separate backend-level
handling and should not be interpreted as a guarantee of file integrity.
