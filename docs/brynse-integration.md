# Brynse integration: first headless slice

The optional `BrynseRipper` adapter translates Brynse's radio runner into
FluxTuner requests, observations and results. GTK, the existing FFmpeg session
recorder, user configuration and the database are unchanged.

The source contract was inspected at Brynse commit
[`d7047eda161b861bfb7bfe56c99dfe7e26e014fa`](https://github.com/pitill0/brynse/tree/d7047eda161b861bfb7bfe56c99dfe7e26e014fa),
which prepares version 0.1.0. The adapter uses the public
`brynse.integrations.radio` package, not the generic CLI or private segmentation
internals. Only the adapter reads Brynse's callback payloads.

## Contract

- `RippingRequest.from_station(...)` snapshots an explicit station's name,
  preferred stream URL and profile. It does not mutate UI selection or station
  data. The caller supplies the output directory; no default path is created
  merely by importing the module or checking availability.
- `availability()` checks the optional import, callable config/runner exports
  and FFmpeg in PATH. Missing Brynse is distinguished from a broken dependency
  or incompatible API. This is local readiness, not proof that a stream supports
  ripping. Brynse currently requires ICY metadata and MP3/AAC.
- `run(...)` blocks and creates a fresh runner per operation. The caller must
  schedule it outside a future GTK event loop. Callback handlers execute in the
  calling thread. `on_started` means the stream has opened; it is not emitted
  merely because a job was submitted.
- Finalized tracks are translated to `RippedTrack(title, path)` and accumulated
  in `RippingResult`. The incomplete current track stays separate. The adapter
  trusts Brynse's finalized-track callback and does not rename or rewrite files.
- Backend or callback failures raise `RippingError` with the original cause and
  references to tracks already finalized. Persistence and retries belong to a
  later coordinator/store.
- Overlapping `run` calls on one adapter are rejected. `stop()` delegates to
  the active runner and is a no-op while idle. It sends no process signals and
  does not wait for the worker to finish.

## Deliberate limits before GTK wiring

There is no worker, state machine, bounded shutdown guarantee, SQLite migration,
new CLI command or UI action in this slice. Stop before `run`, during dependency
loading or during stream opening is not guaranteed to cancel the operation.
The coordinator must define those semantics and test them with synchronization
barriers, together with stale events, double start and shutdown. A worker that
has not terminated must not be treated as an idle backend.

Brynse's inspected runner passes its FFmpeg setting to analysis, while the
default output writer creates finalizers with the default `ffmpeg` command.
This adapter only resolves `ffmpeg` from PATH; it does not offer a custom binary
setting or claim that upstream propagation is fixed.

Brynse and NumPy are not added as mandatory dependencies. Packaging an optional
extra, selecting a release/pin, testing a real installed runner against a local
ICY fixture, and checking Python 3.14 and Flatpak remain separate work. The
current unit tests use an injected module and runner; they establish the adapter
contract, not an executed end-to-end Brynse integration.

## Validation

Run the focused deterministic tests with:

```sh
python -m pytest tests/test_brynse_ripper.py
```

Before UI wiring, follow these with a real-runner contract test, a headless
smoke, and lifecycle tests. Keep session recording and ripping capabilities
independent of player codec capabilities. Output ownership must preserve the
profile captured in the request.
