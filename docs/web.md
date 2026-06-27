# FluxTuner Web

FluxTuner Web is a browser-based server mode for FluxTuner.

It brings the same internet radio workflow to any device with a browser: search
stations, play streams, review playback history, manage favorites, and organize
stations with playlists.

FluxTuner Web reuses the same core data as the terminal and desktop interfaces,
including favorites, playlists, and playback history.

## Run locally

Install the web extras:

```bash
python -m pip install -e ".[web]"
```

Start the web server:

```bash
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Open:

```text
http://127.0.0.1:8080
```

## Web playback

FluxTuner Web plays streams directly in the browser using the browser audio
engine.

This makes the web/server mode useful from Linux, macOS, Windows, Android, iOS,
tablets, or any other device on your network with a modern browser.

Some streams may still fail because of browser codec support, CORS, mixed-content
rules, or the way a radio station exposes its stream. When that happens, the
interface keeps a direct stream URL as a fallback.

## Shared FluxTuner data

By default, FluxTuner stores user data in the XDG data directory:

```text
~/.local/share/fluxtuner
```

FluxTuner Web uses the same SQLite library database as the TUI, GTK and CLI
interfaces:

```text
fluxtuner.db
```

The shared database contains profile-scoped favorites, playback history, manual playlists and
normalized station records for profile-scoped library data.

Legacy JSON library files are still supported as migration sources, but the
active library store is `fluxtuner.db`.

## Use a separate data directory

For web development, testing, containers, demos, or isolated instances, set
`FLUXTUNER_DATA_DIR`:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

This keeps web playback history, favorites, and playlists outside your normal
FluxTuner profile.

`FLUXTUNER_DATA_DIR` only changes the data directory. Config and cache still use
their XDG locations unless `XDG_CONFIG_HOME` or `XDG_CACHE_HOME` are also set.

## Containers

FluxTuner Web can also run in Docker or Podman.

See [`docs/container.md`](container.md) for build, run, Compose, and persistent
volume examples.

## Profiles

Web mode uses the persisted active profile by default. API endpoints also accept
?profile=NAME as a per-request override:

    /api/favorites?profile=work
    /api/history?profile=work
    /api/playlists?profile=work

Profiles separate favorites, manual playlists and playback history by context.
They are not separate user accounts.
