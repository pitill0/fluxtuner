# Station provenance and unified discovery investigation

Related: #256, #224, #252, #253, #254.
Follow-up: #255.

## Purpose

Evaluate discovery across Radio Browser, the local library and future
community catalogs. Separate station identity, provenance, library
membership and discovery without introducing a generic provider framework
before it is justified.

This document proposes an incremental design. It does not implement
provider registration, persistent provenance or database migration.

## Current architecture

### Radio Browser

`fluxtuner/core/api.py` implements the Radio Browser HTTP API,
including request filters, response validation, diagnostics,
deduplication, caching and relevance ranking.

The configured API base is currently a Radio Browser endpoint.
Provider-specific behavior is concentrated primarily in this module.

`fluxtuner/core/search_service.py` contains `SearchRequest`,
`SearchResult`, `StationSearchBackend` and `SearchService`.

The backend is injectable, but the default backend delegates directly
to `search_stations_filtered` from `core/api.py`. The service handles
input normalization and playback capability filtering.

### Interface coupling

GTK and TUI instantiate and call the shared `SearchService`.

Web uses Radio Browser search functions through `web/library.py`,
bypassing `SearchService`. A common discovery policy therefore does not
yet apply equally across all interfaces.

### Station identity

`station_key()` in `core/stations.py` returns the preferred playable
URL (`url_resolved`, falling back to `url`).

The `stations.station_key` database column is unique. Favorites,
history and playlist memberships refer to shared station rows.

This identity preserves legacy behavior, but represents stream identity
rather than a verified real-world broadcaster identity.

The Radio Browser `stationuuid` is useful provider metadata, not a
universal identifier. Different stream URLs are not automatically
equivalent, even if they describe the same radio station.

Conversely, the same playable URL may be discovered through multiple
catalogs or imported collections. Matching that URL may identify one
FluxTuner station record, but must not collapse or discard the
different source observations.

### Local stations and imported collections

Custom stations and M3U/M3U8/PLS imports enter the existing library.
The import workflow preserves existing favorite names, tags and
playlist memberships.

Local library membership does not make a station searchable through
the Radio Browser discovery path.

The original import collection is not retained as structured station
provenance. A destination playlist is not a reliable substitute:
multiple collections can import into one playlist.

## Concepts and contracts

- Identity: the existing playable-URL key used by FluxTuner.
- Provenance: one or more sources in which a station was observed.
- Membership: a user's favorite or playlist relationship.
- Discovery: a query against selected local or external sources.

These concepts must remain independent.

A station may have multiple provenance records, multiple playlist
memberships and different names in different sources.

Provenance must not overwrite user-edited names or favorite tags.

## Unified discovery proposal

Begin with two explicit scopes:

1. Radio Browser: preserve existing search behavior.
2. Local library: query saved stations for the active profile.

A later combined scope can merge results using the existing
`station_key()` semantics.

Never merge distinct playable URLs merely because their names,
homepages or Radio Browser metadata are similar.

Display source information separately from the station name.
Preserve stable list selection, pagination/limits and player
compatibility checks.

Local searching must obey profile ownership, especially in Web.

### Search filters

Text search should cover station names and suitable tags.
Country and bitrate filters should be applied only where reliable
metadata exists.

Missing local metadata should be represented as unknown rather than
fabricated.

The treatment of unknown bitrate and codecs must be explicit, and
compatible with the selected player.

### Errors and partial results

An unavailable external provider must not hide successful local
results.

Results should distinguish empty matches from remote request errors.

Cache entries must be scoped to source selection and query filters.
Local updates must not leave stale local search results.

### Ranking and result limits

Preserve Radio Browser relevance behavior within its scope.
Define local relevance independently before combining results.

For combined results, merge deterministically, deduplicate by
existing station key, retain source membership and enforce a final
result limit.

Avoid arbitrary provider-priority rules presented as relevance.

## Provenance proposal

A future persistent model may separate:

- Source: kind, stable source reference and optional display name,
  scoped appropriately to a profile or external catalog.
- Station-source relationship: station ID, source ID and observation
  metadata, allowing many sources per station.

Collection provenance should identify the collection URL or a
suitable local-file descriptor, not the stream URL.

Local filesystem paths and URLs may contain private information.
Avoid displaying or logging them indiscriminately. Do not persist
secrets embedded in URLs.

A source record must not imply automatic subscription or refresh.

Repeated observations should not erase historical source association.
Deletion and retention semantics need explicit tests.

Unknown historical provenance must remain unknown; do not invent
Radio Browser origins for previously saved stations.

## Provider abstraction decision

Do not introduce a generic provider plugin system at this stage.

The existing `SearchService` is the narrowest useful search
boundary. Its injectable backend currently represents one search
operation; it does not aggregate multiple providers automatically.

The next implementation should add a local search operation and
compose it explicitly with Radio Browser search, preserving the
current public `SearchRequest` behavior and existing callers.

Reconsider a provider protocol only after at least two independent
external catalogs require shared discovery lifecycle, configuration
or authentication behavior.

Fetching a remote M3U/PLS collection for import is not equivalent to
searching a live catalog.

## UI proposal

Keep existing navigation and avoid adding multiple persistent panels.

- GTK: use a compact source selector in the search controls.
- TUI: expose source choice within the search form or a small modal.
- Web: reuse the search controls and clearly distinguish local from
  remote results.

Default behavior should remain Radio Browser until a dedicated
compatibility review agrees otherwise.

Source badges or metadata should be accessible without crowding the
station list. Do not confuse provenance with the search scope.

## Incremental implementation plan

These steps are candidate follow-up issues, not implementation work
included in #256. Each requires its own scope, acceptance criteria
and independent validation before development begins.

### Step 1: local discovery backend

Implement read-only local station search scoped to one profile,
with deterministic ordering and bounded results.

Test query, profile isolation, metadata gaps and duplicate streams.
No database migration should be needed.

### Step 2: opt-in combined discovery

Compose local and Radio Browser results through the existing search
service boundary.

Define merge order, identity deduplication, partial failures,
filter semantics, cache keys and compatibility filtering.

Preserve the legacy default search behavior.

### Step 3: interface integration

Introduce source selection in GTK, TUI and Web incrementally.

Remove the direct Web-to-Radio-Browser coupling when the shared
service offers the necessary diagnostics and authorization boundary.

Test keyboard access, small screens, selection stability and
backward compatibility.

### Step 4: provenance storage

Design an additive SQLite migration only after the exact data and
retention contract is agreed.

Preserve existing station IDs, URL-based identity, favorites, history
and playlists. Do not infer historical origins.

Test fresh databases, upgrades, repeated imports, multi-source
membership, profile isolation, deletion and transactional rollback.

### Step 5: future community catalogs

Evaluate real community catalog requirements before generalizing the
external search backend.

Remote refresh/subscriptions belong to #255 or a separate follow-up.

## Compatibility and rollout

Preserve existing search signatures where possible.
Preserve URL-based station identity and user-edited metadata.
Do not change Brynse or playback behavior.

Keep database migrations additive, reversible at the transaction
boundary and covered by fresh-install and upgrade tests.

Avoid changing the default search scope without a deliberate
interface compatibility decision.

## Non-goals for issue #256

- No generic provider framework.
- No persistent schema changes.
- No automatic remote synchronization.
- No import workflow rewrite.
- No cross-URL station matching.
- No Brynse changes.

## Conclusion

The immediate opportunity is unified discovery using the existing
search service, starting with the local library.

Persistent provenance is valuable but independent and requires its
own explicit storage and privacy contract.

A generic external-provider abstraction is not yet justified.
