# FluxTuner Web

FluxTuner Web is an experimental browser interface for FluxTuner.

It reuses the same core data as the terminal and desktop interfaces, including
favorites and playback history.

## Run locally

Install the web extras:

```bash
python -m pip install -e ".[web]"
```

Start the development server:

```bash
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Open:

```text
http://127.0.0.1:8080
```

## Use a separate data directory

By default, FluxTuner stores user data in the XDG data directory:

```text
~/.local/share/fluxtuner
```

For web development, testing, containers, or isolated instances, set
`FLUXTUNER_DATA_DIR`:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

This keeps files such as `history.json`, `favorites.json`, and playlists outside
your normal FluxTuner profile.

## Container-friendly example

A container should mount a persistent volume and point `FLUXTUNER_DATA_DIR` to it:

```yaml
environment:
  - FLUXTUNER_DATA_DIR=/data
volumes:
  - fluxtuner-data:/data
```

`FLUXTUNER_DATA_DIR` only changes the data directory. Config and cache still use
their XDG locations unless `XDG_CONFIG_HOME` or `XDG_CACHE_HOME` are also set.

## Containers

FluxTuner Web can also run in Docker or Podman.

See [`docs/container.md`](container.md) for build, run, Compose, and persistent
volume examples.
