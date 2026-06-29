> Licensing note: FluxTuner Web/server and multi-user components are licensed
> under the FluxTuner Web Non-Commercial License. Commercial hosted or SaaS use
> requires a separate written commercial license. See [`docs/licensing.md`](licensing.md).

<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

# FluxTuner container usage

FluxTuner Web can run in a container using Docker or Podman.

The web/server mode plays streams in the browser, so the container does not need
access to a host audio device.

## What the container runs

The container starts:

```text
fluxtuner-web --host 0.0.0.0 --port 8080
```

It serves the browser UI and API. Audio playback happens in the user's browser.

The image defaults to:

```text
FLUXTUNER_DATA_DIR=/data
```

Mount `/data` as a persistent volume to keep the SQLite database, Web users,
sessions, profiles, favorites, history and playlists across restarts.

## Build

From the repository root:

```bash
podman build -t fluxtuner-web:dev -f Containerfile .
```

Or with Docker:

```bash
docker build -t fluxtuner-web:dev -f Containerfile .
```

## Local HTTP smoke run

For local HTTP testing, bind the container to localhost and explicitly disable
Secure cookies because the browser is not using HTTPS:

```bash
podman volume create fluxtuner-data

export FLUXTUNER_WEB_SETUP_TOKEN="$(openssl rand -hex 32)"

podman run --rm \
  --name fluxtuner-web \
  -p 127.0.0.1:8080:8080 \
  -e FLUXTUNER_DATA_DIR=/data \
  -e FLUXTUNER_WEB_SETUP_TOKEN="$FLUXTUNER_WEB_SETUP_TOKEN" \
  -e FLUXTUNER_WEB_SECURE_COOKIES=false \
  -e FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400 \
  -v fluxtuner-data:/data \
  fluxtuner-web:dev
```

Open:

```text
http://127.0.0.1:8080
```

The first-run setup wizard asks for the setup token and creates the first
administrator. After setup, login is required before search, playback, library
data or Admin are available.

Docker equivalent:

```bash
docker volume create fluxtuner-data

export FLUXTUNER_WEB_SETUP_TOKEN="$(openssl rand -hex 32)"

docker run --rm \
  --name fluxtuner-web \
  -p 127.0.0.1:8080:8080 \
  -e FLUXTUNER_DATA_DIR=/data \
  -e FLUXTUNER_WEB_SETUP_TOKEN="$FLUXTUNER_WEB_SETUP_TOKEN" \
  -e FLUXTUNER_WEB_SECURE_COOKIES=false \
  -e FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400 \
  -v fluxtuner-data:/data \
  fluxtuner-web:dev
```

## Secure container deployment

For any LAN or internet-accessible container deployment:

- Put FluxTuner Web behind HTTPS.
- Keep `FLUXTUNER_WEB_SECURE_COOKIES=true`.
- Set `FLUXTUNER_WEB_SETUP_TOKEN` before first exposure.
- Use a persistent `/data` volume.
- Prefer exposing the container only to a reverse proxy network.
- If publishing directly for a local reverse proxy, bind to `127.0.0.1`.

Example for a reverse proxy on the same host:

```bash
podman volume create fluxtuner-data

export FLUXTUNER_WEB_SETUP_TOKEN="$(openssl rand -hex 32)"

podman run --rm \
  --name fluxtuner-web \
  -p 127.0.0.1:8080:8080 \
  -e FLUXTUNER_DATA_DIR=/data \
  -e FLUXTUNER_WEB_SETUP_TOKEN="$FLUXTUNER_WEB_SETUP_TOKEN" \
  -e FLUXTUNER_WEB_SECURE_COOKIES=true \
  -e FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400 \
  -v fluxtuner-data:/data \
  fluxtuner-web:dev
```

Serve the public site through the reverse proxy over HTTPS.

See [`docs/secure-web-deployment.md`](secure-web-deployment.md) for the full
deployment checklist.

## Compose

No Compose file is required. If you use Compose, keep the same deployment rules:

```yaml
services:
  fluxtuner-web:
    image: fluxtuner-web:dev
    build:
      context: .
      dockerfile: Containerfile
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      FLUXTUNER_DATA_DIR: /data
      FLUXTUNER_WEB_SETUP_TOKEN: "${FLUXTUNER_WEB_SETUP_TOKEN}"
      FLUXTUNER_WEB_SECURE_COOKIES: "false"
      FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS: "86400"
    volumes:
      - fluxtuner-data:/data

volumes:
  fluxtuner-data:
```

For HTTPS deployments, set `FLUXTUNER_WEB_SECURE_COOKIES=true` and expose the
service through your reverse proxy rather than directly.

## Persistent data

Back up the full mounted `/data` volume.

At minimum, preserve:

```text
/data/fluxtuner.db
```

During migrations or upgrades, legacy JSON files may also exist in `/data` and
should be backed up with the database.

## Healthcheck

The `Containerfile` includes a healthcheck that calls:

```text
http://127.0.0.1:8080/api/health
```

You can inspect it with Podman or Docker:

```bash
podman ps
podman inspect --format '{{json .State.Health}}' fluxtuner-web
```

or:

```bash
docker ps
docker inspect --format '{{json .State.Health}}' fluxtuner-web
```

## Useful local validation

Check that the Web static assets are packaged correctly:

```bash
curl -I http://127.0.0.1:8080/static/app-icon.png
```

Check first-run setup state:

```bash
curl -s http://127.0.0.1:8080/api/setup/status | python -m json.tool
```

## Why browser playback works well in containers

The container runs the FluxTuner web server and exposes the API/UI. Audio
playback happens in the user's browser, not inside the container.

That keeps the container lightweight and avoids host audio-device permissions.

## Isolated development data without containers

For local development without containers, you can also use a temporary data
directory:

```bash
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

See [`docs/web.md`](web.md) for the general web/server mode documentation.
