# FluxTuner v0.2.0

FluxTuner v0.2.0 is the first major usability-focused milestone of the project.

## Highlights

- Experimental GTK4 desktop GUI with improved dark theme and responsive layout.
- Modular playback backend support with `mpv` and `ffplay`.
- Automatic backend detection with `mpv > ffplay` priority.
- New `--list-players` diagnostic command.
- Live ICY stream metadata support for artist and track when available.
- Smart metadata polling in the GTK GUI.
- Improved favorites and tag playlist workflows.
- Estimated data usage tracking.
- Improved README, CHANGELOG and smoke test documentation.

## Playback backends

FluxTuner now supports:

- `mpv` as the recommended backend
- `ffplay` as a lightweight fallback backend

Check available backends with:

```bash
fluxtuner --list-players
