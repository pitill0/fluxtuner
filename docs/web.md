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
FLUXTUNER_WEB_SECURE_COOKIES=false fluxtuner-web --host 127.0.0.1 --port 8080 --reload
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

## Static asset compression and caching

FluxTuner Web uses a no-build JavaScript ES-module entrypoint,
`/static/app.js`, with supporting modules under `/static/js/`.

### Compression

The application selectively compresses public JS, CSS, SVG and
Webmanifest assets when worthwhile. Large public text assets support
gzip without applying the same middleware to authenticated API routes
or private responses. PNG files are not additionally compressed.

Gzip responses carry `Vary: Accept-Encoding` and representation-specific
weak ETags. Matching conditional GET requests return `304 Not Modified`
without retransmitting the resource body.

The application preserves native `StaticFiles` behavior for HEAD,
byte-range requests and small uncompressed resources.

### Cache invalidation and deployments

By default, FluxTuner serves stable `/static/` URLs. JavaScript,
CSS and Webmanifest responses use `Cache-Control: no-cache`, allowing
storage while requiring revalidation before reuse.

Set `FLUXTUNER_WEB_VERSIONED_STATIC=1` to enable persistent,
content-addressed snapshots of the complete Web static tree.
The HTML references `/static/build/<build-id>/` assets, which use
`Cache-Control: public, max-age=31536000, immutable`.

The build identifier is derived from the snapshot manifest, including
the hashes of all files. Every version has its own URLs, so a new
deployment does not reuse stale module paths.

The snapshot directory is
`FLUXTUNER_DATA_DIR/web/static-builds/`. Its storage must be writable
by the service user, persistent across container replacements and free
of symbolic links in the storage path. Published snapshots are verified
before reuse; failed publication falls back to legacy URLs and logs
an error. Preserve historical builds while older browser pages may
still reference them.

The publisher removes temporary `.tmp-*` directories older than one
hour under its publication lock. Valid published builds are not
automatically pruned; plan disk capacity and retention separately.

If a published snapshot fails verification, inspect the service logs,
stop all publishers sharing the data directory, preserve the damaged
directory for diagnosis, and recover through a controlled operator
procedure. Do not manually delete or rename live builds.

Never apply long-lived `immutable` caching to unversioned `/static/`
URLs.

A successful HTTP revalidation protects new resource loads from stale
content. It does not make a multi-file deployment atomic or guarantee
that tabs already running an older module graph will update in place.
After upgrading, perform a new page load and verify that the browser
successfully loads the new module graph.

Deployment proxies may separately compress small resources; this does
not require applying gzip twice to assets already encoded by the
application. Check real response headers instead of assuming a
particular proxy behavior.

### Production measurement: issue #262

Measured on Lokalix on 2026-10-24 after deploying FluxTuner 1.3.0
through the production HTTPS reverse proxy:

| Asset | Identity bytes | HTTPS gzip bytes | Reduction |
| --- | ---: | ---: | ---: |
| `app.js` | 17,901 | 3,599 | 79.9% |
| `js/player.js` | 25,747 | 5,289 | 79.5% |
| `player.css` | 12,384 | 2,653 | 78.6% |
| `site.webmanifest` | 682 | 307 | 55.0% |
| `app-icon.png` | 132,383 | 132,383 | 0.0% |

These are individual HTTP response-body transfer measurements,
not a browser-wide page-load benchmark.

The earlier FluxTuner 1.2.3 deployment had no application-level
gzip compression. Its HTTPS proxy already compressed public text
resources. For example, the previous `app.js` transferred 3,282
bytes via HTTPS gzip, compared with 3,599 bytes for version 1.3.0;
the source file also changed between versions. Accordingly, the
79.9% figure compares gzip with identity **within version 1.3.0**,
not the total improvement over version 1.2.3.

Direct ASGI and HTTPS delivery both returned the expected gzip
representation for large text assets. Conditional gzip GETs returned
`304` with zero response-body bytes; byte-range requests returned
`206`. The proxy compressed the small Webmanifest independently.

All 31 JavaScript files delivered through the production HTTPS proxy
matched the deployed image byte-for-byte and successfully returned
`304` on conditional identity GET requests. A browser reload and
navigation check after the 1.2.3 to 1.3.0 deployment also succeeded.

### Icon delivery

The 512-pixel application icon is 132,383 bytes. A prior lossless
optimization experiment across the icon set offered approximately
3% combined savings. The original artwork and PWA icon variants
are retained to preserve the existing branding and packaged assets.
Icons continue to support HTTP validator-based revalidation.

For deployment validation steps, see
[`secure-web-deployment.md`](secure-web-deployment.md).

## Unified library and station collection workflows

After signing in, open **My library** to access Favorites, Playlists,
My stations, Remote catalogs and History. The desktop sidebar and mobile
navigation drawer provide the same authenticated destinations.

### Import a station collection

1. Open **Import stations…** from the library actions.
2. Select a local M3U/M3U8/PLS file or supply an HTTP/HTTPS collection URL.
3. Preview the collection and review duplicate and invalid entries.
4. Choose an existing destination playlist or create a new one.
5. Confirm **Import stations**.

Imported entries are saved to Favorites and the selected playlist.
A preview alone does not save any stations.

### Subscribe to a remote catalog

1. Open **Manage subscriptions…** from the library actions.
2. Subscribe to a supported remote collection.
3. Navigate to **My library → Remote catalogs**.
4. Select **Browse stations** on the subscribed catalog.
5. Select a station to play it in the browser.

A subscription stores a committed remote catalog snapshot; it does
not bulk-import entries into Favorites or personal playlists.

Use **Manage subscriptions** to check for updates, review the
candidate changes before confirmation, or unsubscribe. Refresh
failures preserve the committed snapshot. Unsubscribing preserves
independently saved favorites and playlist memberships.

**My stations** shows manually added stations, not the entire content
of imported playlists or subscribed catalogs.

### Navigation and privacy

Browser Back/Forward and supported deep links restore authorized views.
Normal library navigation preserves playback state. Protected views
remain scoped to the authenticated user and selected owned profile.
Reload the page after deploying a new version to obtain its current
JavaScript module graph.

See [navigation architecture](web-navigation-architecture.md) and
[remote subscription contracts](remote-subscriptions.md).


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
FLUXTUNER_DATA_DIR=/tmp/fluxtuner-web-dev \
FLUXTUNER_WEB_SECURE_COOKIES=false \
fluxtuner-web --host 127.0.0.1 --port 8080 --reload
```

This keeps the entire Web instance database and migrated library data outside
your normal FluxTuner data directory.

`FLUXTUNER_DATA_DIR` only changes the data directory. Config and cache still use
their XDG locations unless `XDG_CONFIG_HOME` or `XDG_CACHE_HOME` are also set.

## Containers

FluxTuner Web can also run in Docker or Podman. The repository includes a
`compose.yaml` configured for localhost HTTP development. It requires
`FLUXTUNER_WEB_SETUP_TOKEN`, binds to `127.0.0.1` and explicitly disables
Secure cookies for that local HTTP origin.

See [`docs/container.md`](container.md) for direct container runs, Compose,
persistent volumes and production deployment differences.

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
