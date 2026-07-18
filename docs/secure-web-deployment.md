> Licensing note: FluxTuner Web/server and multi-user components are licensed
> under the FluxTuner Web Non-Commercial License. Commercial hosted or SaaS use
> requires a separate written commercial license. See
> [`docs/licensing.md`](licensing.md).

<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

# Secure FluxTuner Web deployment

This document describes the recommended security baseline for running FluxTuner
Web beyond local development.

FluxTuner Web exposes an HTTP interface with local users, sessions, profile-owned
library data and administrator actions. Treat it as a server application.

## Recommended deployment shape

Use this shape for any network-accessible deployment:

```text
internet / LAN
  -> HTTPS reverse proxy
  -> fluxtuner-web bound to localhost or a private container network
  -> persistent FLUXTUNER_DATA_DIR volume
```

Recommended defaults:

- Terminate HTTPS at a reverse proxy.
- Keep `FLUXTUNER_WEB_SECURE_COOKIES=true`.
- Bind `fluxtuner-web` to `127.0.0.1` on bare-metal deployments.
- In containers, expose the service only through the reverse proxy network when possible.
- Use a persistent data directory or volume.
- Set a first-run setup token before exposing the service remotely.
- Back up the SQLite data directory before upgrades.

## Environment variables

### `FLUXTUNER_DATA_DIR`

Sets the directory where FluxTuner stores its SQLite database and migrated
library data.

For containers, `/data` is the recommended mounted volume.

### `FLUXTUNER_WEB_SETUP_TOKEN`

Requires a setup verification token when creating the first administrator through
the web UI.

Set this before exposing a fresh deployment over the network:

```bash
FLUXTUNER_WEB_SETUP_TOKEN="$(openssl rand -hex 32)"
```

Then paste that value into the setup form when creating the first administrator.

Without this variable, first-run setup is limited to local requests only.

### `FLUXTUNER_WEB_SECURE_COOKIES`

Controls the `Secure` attribute on the session cookie.

Production default:

```bash
FLUXTUNER_WEB_SECURE_COOKIES=true
```

Use `false` only for explicit local HTTP development:

```bash
FLUXTUNER_WEB_SECURE_COOKIES=false fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

Do not use `false` for network-accessible deployments.

For local container smoke tests over plain HTTP, set
`FLUXTUNER_WEB_SECURE_COOKIES=false` and bind the port to `127.0.0.1`. Do not use
that setting for shared LAN or internet deployments.

### `FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS`

Controls the maximum session lifetime in seconds.

Example:

```bash
FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400
```

Choose a value that matches your deployment risk. Shorter sessions reduce the
impact of stolen cookies; longer sessions are more convenient.

## First-run setup checklist

For a fresh deployment:

1. Create a persistent data directory.
2. Restrict filesystem permissions to the service user.
3. Set `FLUXTUNER_DATA_DIR`.
4. Set `FLUXTUNER_WEB_SETUP_TOKEN`.
5. Keep `FLUXTUNER_WEB_SECURE_COOKIES=true`.
6. Start `fluxtuner-web` behind HTTPS.
7. Open the web UI.
8. Create the first administrator.
9. Review pending account requests from Admin before granting access.
10. Remove `FLUXTUNER_WEB_SETUP_TOKEN` from the long-running service
    environment after the first administrator exists.
11. Remove the token from shell history or temporary secret notes if it was
    copied there.
12. Confirm that `/api/setup/status` no longer reports setup as available.

Once a configured active administrator exists, the setup endpoint is no longer
available for creating another first admin.

## Bare-metal example

Run the app bound to localhost:

```bash
export FLUXTUNER_DATA_DIR=/var/lib/fluxtuner
export FLUXTUNER_WEB_SETUP_TOKEN="$(openssl rand -hex 32)"
export FLUXTUNER_WEB_SECURE_COOKIES=true
export FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400

fluxtuner-web --host 127.0.0.1 --port 8080
```

Put a reverse proxy in front of `127.0.0.1:8080` and serve it over HTTPS.

## Container example

Use a persistent volume and pass the same security variables:

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

For a public or shared deployment, put HTTPS in front of that local binding.

## Reverse proxy notes

A reverse proxy should provide at least:

- HTTPS certificate management.
- HTTP-to-HTTPS redirect.
- Proxying to the local `fluxtuner-web` listener.
- Request body limits appropriate for the application.
- Conservative connect, read and idle timeouts.
- Access logs suitable for auditing without logging cookies, setup tokens,
  CSRF tokens or request bodies.

Example shape:

```text
https://radio.example.test
  -> reverse proxy
  -> http://127.0.0.1:8080
```

The application should still keep secure cookies enabled because the browser sees
the HTTPS origin.

## Backup checklist

Back up the full `FLUXTUNER_DATA_DIR`, not just exported playlists.

At minimum, preserve:

- `fluxtuner.db`
- any migrated or legacy JSON library files still present during migration
- any future application data created in the same directory

For SQLite, prefer stopping the service or using a SQLite-aware backup method
before copying the database.

## Post-deploy verification

After deployment, verify:

- The site is reachable only through HTTPS.
- Login sets an HttpOnly session cookie.
- The session cookie has `Secure` when served through HTTPS.
- Logout invalidates the current session.
- Unsafe API requests require the CSRF header.
- Web metadata requests reject unsupported schemes, private/reserved
  destinations and unsafe redirects.
- Non-admin users cannot access `/api/admin/users`.
- Public account requests create pending inactive users and do not grant immediate access.
- Pending users are not notified by email; they must try signing in later to check approval state.
- Deactivated users cannot log in.
- The first-run setup UI is no longer available after the first admin exists.
- Backups can be restored into a test data directory.

## Commercial hosting note

FluxTuner Web/server and multi-user components are licensed under `LICENSE-WEB`.

Offering FluxTuner Web as paid hosting, SaaS, managed service, subscription
service, reseller offering, or part of a commercial hosted product requires a
separate written commercial license from the FluxTuner copyright holder.
