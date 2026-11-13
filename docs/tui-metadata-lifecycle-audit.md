# TUI metadata lifecycle audit

## Status

**COMPLETED — historical audit, not an implementation backlog.**

The original findings were addressed before FluxTuner v1.5.0.
The current implementation was rechecked on 2026-11-12 at
FluxTuner commit `5bdcd4d`.

All 23 focused TUI metadata lifecycle tests passed, along with
Ruff lint and formatting checks. The review also confirmed request
identity, station identity, cancellation, throttling, deduplication,
exception containment and the corresponding regression contracts.

No outstanding implementation work was identified by this review.
The findings and branch plan below describe the historical baseline,
not work remaining for v1.5.1.

The recommended sequence was delivered through contracts, race hardening and
the `MetadataLifecycle` extraction. Request identity, throttling, active-task
ownership, cancellation, stale-result rejection, deduplication and projection
fallbacks now live behind the focused lifecycle boundary. Textual scheduling,
fetch delegation, logging and widget rendering remain in `tui.py`.

## Purpose

This document audits the stream-metadata lifecycle as it existed before the
hardening and extraction sequence.

The goal is to identify a safe extraction boundary after playback coordination
and view-state transitions were centralized.

## Historical responsibilities (before extraction)

At the audited baseline, the TUI owned metadata display state, duplicate suppression, polling
throttling, the active async task, eligibility checks, task creation, blocking
fetch delegation, fallback projection, widget updates, reset behavior and
unmount cancellation.

## Historical lifecycle (before hardening)

### Initialization

The TUI initializes artist and track placeholders, no active metadata task, no
last raw value and a zero last-fetch timestamp.

### Periodic refresh

`on_mount()` schedules `update_now_playing()` every 1.5 seconds. That method
clears metadata while idle and otherwise calls `_maybe_fetch_metadata()` before
updating usage and player-state panels.

### Playback start

Successful playback start clears metadata, resets the last-fetch timestamp to
zero and refreshes Now Playing. This makes the next polling pass immediately
eligible.

### Poll eligibility

`_maybe_fetch_metadata()` skips work when there is no playing station, fewer
than 15 seconds have elapsed, another task is active or the station has no URL.

When eligible it records the current monotonic timestamp and stores a task for
`_fetch_metadata(url)`.

### Fetch and projection

`_fetch_metadata()` delegates the blocking request through
`asyncio.to_thread(fetch_stream_metadata, stream_url)`.

It ignores empty results and duplicate non-empty raw metadata, then projects:

- artist from `artist` or `—`;
- track from `title`, then `raw`, then `—`.

The widget is updated only while mounted.

### Stop and unmount

At the audited baseline, idle Now Playing cleared metadata. Stop did not
directly cancel an in-flight metadata task. Unmount canceled the active
task when it was not done.

## Historical risks (addressed)

### Stale-result race

A slow result for station A can overwrite metadata after station B starts
because completion does not verify current station identity.

### Stop race

A task started before stop can finish after metadata was cleared and restore
stale artist/track values.

### Exception propagation

Fetch errors are not explicitly contained inside the background task.

### Coupled state and rendering

Scheduling, acceptance, state mutation and widget rendering are intertwined.

### Poll timestamp semantics

The timestamp is recorded before fetching, so empty or failed requests still
consume the 15-second interval. This is existing behavior and should be
protected before refactoring.

## Invariants worth protecting

1. No request starts without a playing station and URL.
2. At most one request is active.
3. Requests are throttled for 15 seconds from scheduling time.
4. Empty metadata does not change projection.
5. Duplicate non-empty raw metadata does not re-project.
6. Artist falls back to `—`.
7. Track falls back from title to raw to `—`.
8. Playback start clears metadata and makes polling immediately eligible.
9. Idle clears metadata.
10. Unmount cancels active work.
11. Obsolete-station results must not update current metadata.
12. Fetch exceptions must not become unhandled task failures.

Items 11 and 12 were gaps in the original baseline. Both are
covered by the current lifecycle implementation and regression tests.

## Historical extraction decision (implemented)

Do not extract a generic cross-interface service yet.

Use a TUI-specific metadata lifecycle coordinator owning request identity,
throttling, active task, last accepted raw metadata, cancellation, reset and
result acceptance. Keep the Textual interval, widget rendering and playback
integration in `tui.py`.

## Historical implementation sequence (completed)

### 1. Add metadata lifecycle contracts

Branch: `test/tui-metadata-lifecycle-contracts`

Cover scheduling, throttle, overlapping work, empty/duplicate results,
fallbacks, playback reset, unmount cancellation, stale-result rejection and
exception containment.

### 2. Harden request identity and errors

Branch: `fix/tui-metadata-lifecycle-races`

Reject obsolete results, prevent post-stop projection and contain fetch errors.

### 3. Extract the lifecycle coordinator

Branch: `refactor/tui-metadata-lifecycle`

Move request identity, throttling, deduplication, cancellation and acceptance
behind the tested boundary. Keep widgets and periodic Textual integration in
`tui.py`.

### 4. Reassess GTK overlap

Only after the TUI lifecycle is explicit should GTK be audited for genuine
shared behavior.

## Non-goals

- no Web metadata changes;
- no GTK extraction;
- no shared service;
- no polling interval change;
- no parser rewrite;
- no formatting or layout change;
- no player-state or data-usage extraction.

## Validation expectations for future changes

```bash
git diff --check
make gate
```

Future metadata PRs should also run:

```bash
python -m pytest -q tests/test_tui_metadata_lifecycle.py
```
