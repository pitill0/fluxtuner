> Licensing note: FluxTuner Web/server and multi-user components are licensed under the FluxTuner Web Non-Commercial License. Commercial hosted or SaaS use requires a separate written commercial license. See [`docs/licensing.md`](licensing.md).

<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

# Local multi-user web authentication design

FluxTuner 0.9.0 introduces real multi-user behavior in Web/server mode while
keeping CLI, TUI and GTK GUI local and filesystem-based.

This document defines the security model before implementation. The goal is a
small, maintainable and secure local account system, not a shortcut-based auth
layer.

## Scope

### In scope for 0.9.0

- Local users for Web/server mode.
- Password-based authentication for Web/server mode.
- Secure password hashing.
- Server-side sessions with hardened cookies.
- Authenticated Web API access.
- Profile ownership by authenticated web user.
- Migration path from existing profile-scoped storage.
- Docker and container configuration for secure deployment defaults.
- Tests for authentication, authorization and cross-user isolation.

### Out of scope for 0.9.0

- OAuth, OpenID Connect or external identity providers.
- Password recovery by email.
- Multi-factor authentication.
- Public hosted multi-tenant service mode.
- Sharing playlists or favorites between users.
- Complex roles or permissions beyond admin/user.

## Interface model

CLI, TUI and GTK GUI remain local interfaces. They use the existing filesystem
configuration and data locations. Local user selection can exist for convenience,
but it is not treated as a strong security boundary because anyone with local
filesystem access can read the SQLite database.

Web/server mode is different. It exposes an HTTP interface and API, so it must
enforce real authentication and authorization.

Summary:

    CLI/TUI/GTK
    └── local filesystem trust model

    Web/server mode
    ├── login required
    ├── server-side session required
    ├── authenticated API required
    └── user-owned profiles

## Data model

Current 0.8.x model:

    installation
    └── profiles
        ├── default
        ├── work
        └── terrace

Current 0.9.x web model:

    installation
    └── users
        ├── default
        │   ├── default
        │   ├── work
        │   └── terrace
        └── guest
            ├── default
            └── bedtime

Implemented data model:

    users
    - id
    - username
    - display_name
    - password_hash
    - is_admin
    - is_active
    - approval_status (`approved`, `pending`, `rejected`, `disabled`)
    - signup_note
    - reviewed_at
    - reviewed_by_user_id
    - created_at
    - updated_at

    profiles
    - id
    - user_id
    - name
    - created_at
    - updated_at

Profile names are unique per user, not globally unique:

    UNIQUE(user_id, name)

Existing favorites, playback history and manual playlists continue to belong to
profiles through profile_id.

## Migration strategy

The migration must be safe and reversible during development.

Migration target:

1. Create an internal default web user.
2. Add user ownership to profiles.
3. Attach all existing profiles to the default web user.
4. Preserve existing profile IDs where possible.
5. Preserve all favorites, playback history and manual playlists.

The migration must not delete existing profile data.

## Authentication design

Web/server mode uses local username/password authentication.

Requirements:

- Passwords are never stored in plaintext.
- Password hashes use a modern password hashing algorithm.
- Password verification uses constant-time safe verification provided by the
  password hashing library.
- Login responses do not reveal whether the username or password was wrong.
- Login attempts are rate-limited.
- Users can change their password only after re-entering their current password.
- Disabled, rejected and pending users cannot access the Web app.
- Pending users only see `Account pending approval.` after providing the correct password.

Preferred password hashing option:

    Argon2id

Fallback if dependency constraints make Argon2id impractical:

    bcrypt

The implementation uses Argon2id through `argon2-cffi`.

## Session design

Use server-side sessions. The browser cookie stores only an opaque random session
identifier, never user data or authorization claims.

Session requirements:

- Random session IDs generated with a cryptographically secure random source.
- Session IDs stored hashed in SQLite.
- Session rotation after login.
- Session deletion on logout.
- Expiration with max age.
- Optional idle timeout.
- Cookie attributes:
  - HttpOnly
  - SameSite=Lax
  - Secure by default in production/container mode
  - Path=/

Development mode may allow non-Secure cookies only when explicitly configured for
localhost HTTP development.

## Authorization model

Every Web API request that reads or writes library data must resolve the current
user from the authenticated session.

The API must never trust a user identifier from a query parameter or request body
for normal user operations.

Allowed:

    /api/favorites?profile=work

Not allowed for normal user access:

    /api/favorites?user=alice

The profile override selects a profile inside the authenticated user only.

Authorization rule:

    session user -> owned profiles -> favorites/history/playlists

Any attempt to access another user's profile must return a generic 404 or 403
without leaking whether that profile exists.

## CSRF strategy

Cookie-based session authentication requires CSRF protection for unsafe methods.

Unsafe methods include:

- POST
- PUT
- PATCH
- DELETE

Initial strategy:

- SameSite=Lax session cookie.
- CSRF token for unsafe API requests.
- Login form and authenticated unsafe requests include a CSRF token.
- The server validates token presence and session binding.

## Web routes

Public routes:

- GET /login
- POST /api/auth/login

Authenticated routes:

- POST /api/auth/logout
- GET /api/auth/me
- POST /api/auth/change-password
- GET /api/profiles
- POST /api/profiles
- GET /api/favorites
- POST /api/favorites
- DELETE /api/favorites
- GET /api/history
- POST /api/history
- GET /api/playlists
- POST /api/playlists
- DELETE /api/playlists
- GET /api/playlists/{name}/stations
- POST /api/playlists/{name}/stations
- DELETE /api/playlists/{name}/stations

Admin-only routes are implemented for Web user management. They require an
authenticated active administrator session. Administrators can approve or reject
pending account requests from the Admin UI/API.

## Bootstrap strategy

There must be no default password.

Accepted bootstrap options:

1. Create the first administrator through the first-run Web setup wizard.
2. Protect remote first-run setup with `FLUXTUNER_WEB_SETUP_TOKEN`.
3. Use the emergency `fluxtuner web users ...` CLI for recovery and manual
   administration.

Rejected bootstrap options:

- Hardcoded admin/admin.
- Auto-created web admin with a generated password printed to normal logs.
- Hidden bypass tokens.
- Auth disabled by default in container mode.

Web user CLI commands:

    fluxtuner web users list
    fluxtuner web users create alice --admin
    fluxtuner web users password alice
    fluxtuner web users activate alice
    fluxtuner web users deactivate alice
    python -m fluxtuner --web-disable-user alice
    python -m fluxtuner --web-reset-password alice

The exact CLI shape can change during implementation, but first-user bootstrap
must be explicit.

## Container and deployment requirements

Container mode should be secure by default.

Requirements:

- No default credentials.
- Persistent data volume for SQLite and app data.
- Required secret for session signing or session key derivation.
- Clear environment variables for production/development mode.
- Secure cookie enabled by default unless explicit development mode is set.
- Bind to localhost by default where appropriate.
- Document reverse proxy TLS expectations.

Potential environment variables:

    FLUXTUNER_WEB_SECRET_KEY
    FLUXTUNER_WEB_SECURE_COOKIES=true
    FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400
    FLUXTUNER_WEB_TRUST_PROXY=false

## Testing requirements

Minimum tests before release:

- User creation stores a password hash, not the password.
- Correct password logs in.
- Wrong password fails with a generic error.
- Disabled user cannot log in.
- Logout invalidates the session.
- Session cookie has expected security attributes.
- Unauthenticated Web API requests are rejected.
- Unsafe authenticated requests require CSRF protection.
- Two users can have a profile with the same name.
- User A cannot read user B favorites.
- User A cannot mutate user B playlists.
- Existing 0.8.x profile data migrates to the default web user.

## Security non-goals

- CLI/TUI/GTK local user selection is not a hard security boundary.
- SQLite encryption at rest is not part of 0.9.0.
- Browser extension compromise is not solved by this model.
- HTTPS termination is expected from a reverse proxy or deployment layer.

## Implementation order

Recommended commit sequence:

1. Add this design document.
2. Add users table and migration.
3. Add user/profile ownership helpers.
4. Add password hashing utilities.
5. Add server-side session storage.
6. Add web login/logout endpoints.
7. Require authenticated sessions for Web API.
8. Add CSRF protection for unsafe methods.
9. Add web login UI.
10. Add Docker/container secure defaults.
11. Add docs and release notes.

## References

- OWASP Authentication Cheat Sheet
- OWASP Password Storage Cheat Sheet
- OWASP Session Management Cheat Sheet
- OWASP Cross-Site Request Forgery Prevention Cheat Sheet

## Secure deployment documentation

Operational deployment guidance now lives in [`docs/secure-web-deployment.md`](secure-web-deployment.md). That document covers reverse proxy usage, secure cookies, setup tokens, persistent data, backups and post-deploy verification.
