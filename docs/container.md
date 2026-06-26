# FluxTuner container usage

FluxTuner Web can run in a container using Docker or Podman.

The web/server mode plays streams in the browser, so the container does not need
access to a host audio device.

## Build

From the repository root:

```bash
podman build -t fluxtuner-web:dev -f Containerfile .
```

Or with Docker:

```bash
docker build -t fluxtuner-web:dev -f Containerfile .
```

## Run with Podman

```bash
podman volume create fluxtuner-data

podman run --rm \
  --name fluxtuner-web \
  -p 8080:8080 \
  -e FLUXTUNER_DATA_DIR=/data \
  -v fluxtuner-data:/data \
  fluxtuner-web:dev
```

Open:

```text
http://127.0.0.1:8080
```

## Run with Docker

```bash
docker volume create fluxtuner-data

docker run --rm \
  --name fluxtuner-web \
  -p 8080:8080 \
  -e FLUXTUNER_DATA_DIR=/data \
  -v fluxtuner-data:/data \
  fluxtuner-web:dev
```

Open:

```text
http://127.0.0.1:8080
```

## Compose

A sample `compose.yaml` is included.

With Podman Compose or Docker Compose:

```bash
docker compose up --build
```

Or, if your system uses the standalone Compose command:

```bash
docker-compose up --build
```

## Persistent data

The container sets:

```text
FLUXTUNER_DATA_DIR=/data
```

Files such as `history.json`, `favorites.json`, and `playlists.json` are stored
inside `/data`.

Mount `/data` as a volume if you want to keep your FluxTuner Web library between
container restarts.

## Why browser playback works well in containers

The container runs the FluxTuner web server and exposes the API/UI. Audio playback
happens in the user's browser, not inside the container.

That keeps the container lightweight and avoids host audio-device permissions.

## Isolated development data

For local development without containers, you can also use a temporary data
directory:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

See `docs/web.md` for the general web/server mode documentation.
