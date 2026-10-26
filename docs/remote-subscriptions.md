# Remote catalog subscriptions — Issue #255

## Scope

Manual refresh of profile-owned remote M3U/PLS catalogs.

Scheduled synchronization and authenticated remote catalogs are excluded.

## Identity

Stream URL is the identity available from conventional M3U/PLS entries.
A URL change is shown as removal plus addition. No speculative matching.

The catalog's remote URL is distinct from the opaque source reference.

## Refresh contract

1. Resolve the authenticated user's selected profile.
2. Verify that the subscription belongs to that profile.
3. Fetch through the existing protected remote transport and limits.
4. Parse and validate the complete candidate snapshot.
5. Reject failures and empty or invalid catalogs without modifying storage.
6. Compare candidate and last committed snapshot.
7. Present added, removed, changed and unchanged entries.
8. Confirm an exact, authorized candidate snapshot before applying it.
9. Apply catalog and membership changes atomically.
10. Retain the previous committed snapshot on any failure.

Changes to a shared station record must not overwrite profile-owned favorite
names, tags, playlist membership or other users' data.

A refreshed catalog must not silently add every entry to favorites or an
existing user-managed playlist.

Confirmation must reject stale snapshots and cross-profile requests.

Removing a subscription deletes only subscription-owned data and links;
independently saved favorites, playlists and shared stations survive.

## HTTP caching

ETag and Last-Modified revalidation uses the existing protected transport.
Validators are scoped to the original subscribed URL and are not forwarded
to redirected destinations. Redirected responses do not provide reusable
origin validators.

A complete HTTP 200 candidate is parsed and held in a session-bound,
single-use preview receipt together with its validators. Its snapshot and
validators become committed only after confirmation.

A validated HTTP 304 returns "not_modified" and preserves the previous
snapshot, membership timestamps, revision and committed validators.
An unsolicited HTTP 304 is rejected. Network errors, malformed remote
collections, unsafe validators and failed confirmation do not overwrite
the committed catalog.

Scheduled polling remains out of scope: refresh is initiated manually.

## Implementation phases

1. Pure catalog comparison and tests.
2. Versioned SQLite migration and profile-owned subscription state.
3. Protected refresh preview and atomic confirmation.
4. Manual subscription UI, shared interface contracts and documentation.
