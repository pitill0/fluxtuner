# Custom stations

Related issue: https://github.com/pitill0/fluxtuner/issues/224

## First delivery: manual creation in GTK

The existing application menu exposes Add station without adding permanent
controls to the main window. Stations use the normal favorites, playlist,
playback and history infrastructure.

The shared core entry point is
`custom_stations.add_custom_station(conn, profile_id=..., name=..., url=...)`.
It requires an existing explicit profile and a prepared database connection.
Web callers separately authorize access to that profile.

A successful new favorite returns True. An existing favorite returns False.
The caller owns the transaction and commits successful operations.
A savepoint rolls back partial station/favorite writes on failure without
discarding earlier work in the caller's transaction.

## Manual creation in TUI and Web

TUI exposes the shared service through Ctrl+N. Saving checks that the selected
profile is still current, commits the transaction and refreshes favorites.
Invalid input remains available for correction.

Web exposes a native dialog from the main navigation menu and Library actions
in Favorites. It supports Escape, focus restoration, cancellation and protection
against repeated submissions. Stale responses cannot update a reopened dialog
or a different session.

POST /api/stations/custom requires authentication and CSRF protection and accepts
only string fields name and url. An explicit profile must exist and belong to
the authenticated user; an unavailable profile returns 404. Without a selector,
Web uses that user's default profile. Web library operations do not inherit
the desktop's active profile.

Saving performs no outbound request. Browser playback and server-side metadata
retain their existing network policies.

## Identity and conflict handling

The playable URL remains the station key. Surrounding spaces are removed;
query strings, paths and schemes are otherwise preserved. HTTP and HTTPS
or different query strings are not automatically merged.

Existing shared station records are never overwritten by manual creation.
A newly added favorite receives its requested name as a profile-specific
custom name. Existing favorite names and tags remain unchanged.
No playlist memberships are modified by the creation service.

## Validation and network behavior

Names are required, limited to 200 characters and reject control characters.
Stream URLs are required, limited to 2048 characters and must have an HTTP
or HTTPS scheme and host. Embedded credentials, invalid ports, control
characters, internal whitespace and backslashes are rejected.

Saving performs no DNS resolution, redirect lookup or availability request.
Private and local HTTP/HTTPS streams are supported by desktop creation.
This validation is not a replacement for server-side network access policy.

## Validation evidence

Automated coverage includes duplicate preservation, independent profile names,
existing directory metadata, invalid input, transaction ownership and rollback,
and GTK dialog cancellation, profile changes, errors and success.

Native macOS GTK validation used isolated data directories and two launches.
A manually entered station and its Personal playlist membership persisted
across restart; a second profile remained empty. The tester confirmed the
dialog and requested workflow behaved correctly.

TUI validation on macOS used two launches with isolated storage and confirmed
creation, cancellation, duplicate protection, persistence and playback.

Web validation used isolated storage and two accounts with a different desktop
profile selected. Manual checks confirmed creation, account isolation and menu
access, including keyboard and mobile-menu behavior. Automated coverage includes
authentication, CSRF, profile ownership, invalid payloads, session changes,
stale responses and repeated submissions.

## Remaining issue scope

- Import local M3U/M3U8 station collections with preview and a result summary.
- Preserve user metadata and resolve duplicates deterministically during import.
- Evaluate PLS, export and remote catalog subscriptions as subsequent work.

This delivery does not close issue #224 or change Brynse.
