> Licensing note: FluxTuner Web/server and multi-user components are licensed under the FluxTuner Web Non-Commercial License. Commercial hosted or SaaS use requires a separate written commercial license. See [`docs/licensing.md`](licensing.md).

<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

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

On first run, FluxTuner Web shows a setup wizard to create the first
administrator. After setup, the Web UI requires login before search, playback,
favorites, history, playlists or dashboard data are available.

The app shell includes an authenticated dashboard, quick navigation, isolated
Admin user management, browser playback, a compact server-health summary inside
Admin, an admin-only opt-in player debug panel, and a local light/dark theme
preference stored as `fluxtuner.theme`. The browser client is loaded as a
no-build ES module entrypoint (`/static/app.js`) that composes focused modules
under `/static/js/`.

The dashboard shows each user their own favorite, playlist and history counts,
recent playback and favorite highlights. Administrators also see compact global
metrics such as total users, new users and pending approvals.

Users can request an account from the login screen. Public registration never
grants immediate access: the account is created as pending and inactive until an
administrator approves it. FluxTuner does not send email notifications, so users
should try signing in later; pending users with the correct password see
`Account pending approval.`


For network-accessible deployments, see [`docs/secure-web-deployment.md`](secure-web-deployment.md).

## Web playback

FluxTuner Web plays streams directly in the browser using the browser audio
engine.

This makes the web/server mode useful from Linux, macOS, Windows, Android, iOS,
tablets, or any other device on your network with a modern browser.

Some streams may still fail because of browser codec support, CORS, mixed-content
rules, or the way a radio station exposes its stream. When that happens, the
interface keeps a direct stream URL as a fallback.

FluxTuner Web keeps the current station available after pause so `Resume` can
restart a live stream cleanly. Mobile lock-screen and status-bar controls are
mediated by the browser and operating system, so their persistence can vary by
platform and may appear a few seconds after playback starts on some browsers.
FluxTuner sets Media Session metadata and artwork where supported, and
administrator sessions can enable the local player debug panel from Admin to
inspect playback, Media Session and page-lifecycle events when diagnosing
browser-specific issues.

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

Favorites are FluxTuner's saved station library. Manual playlists reference saved
stations instead of owning a separate station copy. In Web mode, adding a station
to a playlist also saves it to the user's favorites/library if it is not already
there. This is intentional and matches the shared core model used by the local
interfaces.

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

## Users and profiles

FluxTuner Web uses local username/password accounts. Each authenticated user owns
their Web profiles and private library data. Account requests created from the
login screen are pending by default and require administrator approval before
login succeeds.

Profile names are scoped to the authenticated user. API endpoints can still use a
`?profile=NAME` override, but the selected profile must belong to the current
session user:

    /api/favorites?profile=work
    /api/history?profile=work
    /api/playlists?profile=work

Profiles separate favorites, manual playlists and playback history by context.
They are not login accounts by themselves; Web users provide authentication,
ownership and administrator permissions.
