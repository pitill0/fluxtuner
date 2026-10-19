# Playlist imports

Related issue: https://github.com/pitill0/fluxtuner/issues/224

## GTK workflow

Choose Import stations from the application menu, select a local file and
review the preview. Choose an existing playlist or enter a new playlist name.
Import saves valid stations to favorites and the chosen playlist.

The filename is proposed as the new playlist name and can be edited.
Canceling file selection or the preview does not write library data.
A successful import opens the destination playlist and reports new and existing
favorites and playlist memberships.

The selected profile is captured for the import. Saving rejects profile changes,
deleted profiles and deleted existing destinations. Creating a new playlist with
an existing name reports a conflict instead of silently merging it.

## Web workflow

Sign in and choose Import stations from the navigation menu. Select a local
M3U/M3U8 file and choose Preview file. Review the stations, repeated URLs and
skipped entries, then choose an existing playlist or name a new one.

Import stations saves the valid entries and opens the destination playlist.
Canceling before confirmation makes no library changes. Selecting a different
file invalidates the preview and requires a new preview before importing.
The browser retains the file bytes used for preview and sends those same bytes
when confirming. The server independently parses and validates confirmation.

The interface uses the signed-in user's default profile. API clients may request
a named profile belonging to that user. Desktop profile selection does not
affect the destination. Missing profiles and deleted existing playlists are
rejected; a new playlist name that already exists reports a conflict.

Both preview and confirmation require authentication and a valid CSRF token.
Uploads are read with a 1 MiB limit; the server does not save uploaded files or
fetch station URLs during import. File parsing and library work run outside
the asynchronous request loop. Confirmation is atomic and serializes destination
checks with persistence.

The preview displays at most 200 stations and 100 skipped-entry details, with
a notice when additional entries are omitted from display. All valid entries
are included in the import. Names and URLs are rendered as text.

Duplicate submissions are blocked while saving. Session changes close the
dialog, and delayed responses cannot overwrite a newer dialog or another
session's interface.

## Supported input

- UTF-8 text, optionally with a BOM, in M3U or M3U8 files.
- Plain HTTP/HTTPS URLs, or extended entries with EXTINF station names.
- CRLF, LF and CR line endings.
- Quoted EXTINF attributes may contain commas.
- Comments are ignored; homepage and group comments do not change metadata.
- Missing names fall back to the URL hostname.

HLS manifests containing EXT-X directives are rejected. Their media segments
and variant playlists are not station collections. A station URL ending in
.m3u8 is supported as an individual playable entry.

Relative paths, local media files, unsupported schemes, embedded credentials,
invalid ports and invalid names or URLs are reported as issues and skipped.
Invalid UTF-8, binary content, HLS manifests and exceeded file limits reject
the whole preview. Empty or entirely invalid collections cannot be imported.

## Limits

| Input | Limit |
| --- | --- |
| File size | 1 MiB |
| Candidate station entries, including duplicates and invalid URLs | 5000 |
| Lines | 25000 |
| Station name | 200 characters |
| Stream URL | 2048 characters |
| Destination playlist name | 120 characters |

## Identity and preservation

The first valid occurrence of an exact playable URL wins within the file.
HTTP and HTTPS variants, paths and query strings retain their existing identity.
No DNS lookup, redirect resolution or stream availability check is performed.

Existing shared station rows are preserved. Existing favorite names and tags
are preserved. New favorites receive the imported name for their profile.
Existing playlist members keep their positions; new members are appended in
file order. Reimporting adds no duplicate favorites or memberships.

## Core services

m3u_import.parse_m3u accepts bounded bytes and returns immutable preview entries,
issues with line numbers, and a repeated-URL count. It performs no database or
network access. load_m3u_file reads at most the byte limit plus one detection byte.

m3u_import.import_m3u requires a prepared connection and an explicit existing
profile. It revalidates entries and saves favorites and memberships atomically.
The caller commits or rolls back. A storage failure rolls back all writes from
the import while preserving earlier writes in the caller's transaction.

The GTK session owns its save transaction and serializes destination checks
with persistence. Failed saves remain retryable; completed or canceled sessions
cannot be submitted again.

## Scope

This delivery provides the shared core, GTK and Web interfaces. The TUI import
interface remains subsequent work. Remote subscriptions, remote fetching, PLS,
export and source-provider abstractions are not implemented here.
Brynse and existing Radio Browser discovery are unchanged.
