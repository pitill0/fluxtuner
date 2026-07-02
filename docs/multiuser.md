> Licensing note: FluxTuner Web/server and multi-user components are licensed under the FluxTuner Web Non-Commercial License. Commercial hosted or SaaS use requires a separate written commercial license. See [`docs/licensing.md`](licensing.md).

<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

# Web multi-user and pending account model

FluxTuner Web/server mode has real local multi-user behavior while the CLI, TUI
and GTK GUI remain local, filesystem-based interfaces.

This document describes the implemented Web account model for the 1.0 release
line. The goal is a small, maintainable and secure local account system, not a
shortcut-based auth layer or a public SaaS identity system.

## Scope

### In scope for the 1.0 Web/server model

- Local users for Web/server mode.
- Password-based authentication for Web/server mode.
- Secure password hashing with Argon2id.
- Server-side sessions with hardened cookies.
- Authenticated Web API access.
- Profile ownership by authenticated Web user.
- First-run administrator setup.
- Public account requests that remain pending until reviewed by an administrator.
- Admin approval/rejection and activation/deactivation flows.
- Dashboard metrics for authenticated users and additional admin-only metrics.
- Migration path from existing profile-scoped storage.
- Docker and container configuration for secure deployment defaults.
- Tests for authentication, authorization and cross-user isolation.

### Out of scope for the 1.0 Web/server model

- OAuth, OpenID Connect or external identity providers.
- Password recovery by email.
- Email notifications for account approval or rejection.
- Multi-factor authentication.
- Public hosted multi-tenant service mode.
- Sharing playlists or favorites between users.
- Complex roles or permissions beyond admin/user.

## Interface model

CLI, TUI and GTK GUI remain local interfaces. They use the existing filesystem
configuration and data locations. Local profile selection is a convenience
feature, not a strong security boundary, because anyone with local filesystem
access can read the SQLite database.

Web/server mode is different. It exposes an HTTP interface and API, so it must
enforce real authentication and authorization.

Summary:

    CLI/TUI/GTK
    └── local filesystem trust model

    Web/server mode
    ├── login required
    ├── server-side session required
    ├── authenticated API required
    ├── user-owned profiles
    └── administrator review for public account requests

## Data model

Legacy profile-only model:

    installation
    └── profiles
        ├── default
        ├── work
        └── terrace

Current Web account model:

    installation
    └── users
        ├── default
        │   ├── default
        │   ├── work
        │   └── terrace
        └── guest
            ├── default
            └── bedtime

Implemented user model:

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

Implemented profile model:

    profiles
    - id
    - user_id
    - name
    - created_at
    - updated_at

Profile names are unique per user, not globally unique:

    UNIQUE(user_id, name)

Existing favorites, playback history and manual playlists continue to belong to
profiles through `profile_id`.

## Account states

FluxTuner keeps the older active/inactive behavior compatible while adding an
explicit review state.

```text
approved -> is_active=1, login allowed
disabled -> is_active=0, login denied
pending  -> is_active=0, login denied until approved
rejected -> is_active=0, login denied
```

Public account requests always create `pending` users. They never create an
active session and never grant immediate access. Administrators can approve or
reject pending users from the Admin UI/API.

## Migration strategy

The migration must be conservative.

Migration target:

1. Create an internal default web user.
2. Add user ownership to profiles.
3. Attach all existing profiles to the default web user.
4. Preserve existing profile IDs where possible.
5. Preserve all favorites, playback history and manual playlists.
6. Add account review columns without changing existing approved/active users.

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

The implementation uses Argon2id through `argon2-cffi`.

## Session design

Use server-side sessions. The browser cookie stores only an opaque random session
identifier, never user data or authorization claims.

Session requirements:

- Random session IDs generated with a cryptographically secure random source.
- Session IDs stored hashed in SQLite.
- Session rotation after login.
- Session deletion on logout.
- Session revocation when passwords change or users are deactivated.
- Expiration with max age.
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

Within that boundary, favorites act as the user's saved station library. Manual
playlists reference saved stations, so adding a station to a playlist can also
save it to that user's favorites/library. This does not cross user boundaries:
the saved station and playlist entry remain scoped to the authenticated user's
profile.

Any attempt to access another user's profile must return a generic 404 or 403
without leaking whether that profile exists.

## CSRF strategy

Cookie-based session authentication requires CSRF protection for unsafe methods.

Unsafe methods include:

- POST
- PUT
- PATCH
- DELETE

Strategy:

- SameSite=Lax session cookie.
- CSRF token for unsafe API requests.
- Login, setup, registration and authenticated unsafe requests include a CSRF token.
- The server validates token presence and session binding where required.

## Web routes

Public/setup/auth routes:

- `GET /`
- `GET /api/setup/status`
- `POST /api/setup/admin`
- `POST /api/auth/login`
- `POST /api/auth/register`

Authenticated routes:

- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/dashboard`
- `GET /api/favorites`
- `POST /api/favorites`
- `DELETE /api/favorites`
- `GET /api/history`
- `POST /api/history`
- `GET /api/playlists`
- `POST /api/playlists`
- `DELETE /api/playlists`
- `GET /api/playlists/{name}/stations`
- `POST /api/playlists/{name}/stations`
- `DELETE /api/playlists/{name}/stations`

Admin-only routes are implemented for Web user management. They require an
authenticated active administrator session. Administrators can create users,
reset passwords, activate/deactivate users, grant/revoke admin access, approve
or reject pending account requests, and delete users from the Admin UI/API.
Destructive user deletion is kept in a danger zone, requires strong confirmation,
is CSRF-protected, blocks self-delete, and removes related Web sessions,
favorites, playlists, history and password change requests.

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

First-user bootstrap must be explicit.

## Web UX notes

FluxTuner Web 1.0.1 improves the private-server browser experience without
changing the authentication model or storage format:

- The authenticated header displays the user's display name when available.
- The persistent player bar has stronger visual contrast and clearer playback state.
- The external stream action is styled consistently with the rest of the player controls.
- Register and playlist dialogs are scrollable on small mobile screens.
- Hidden dialogs and authenticated header controls remain hidden until the current
  session state makes them visible.

Password change requests and public read-only server stats are implemented for
private server deployments. Public stats remain anonymous aggregate counts only;
they do not expose usernames, stream URLs, IP addresses or detailed timestamps.

## Container and deployment requirements

Container mode should be secure by default.

Requirements:

- No default credentials.
- Persistent data volume for SQLite and app data.
- Clear environment variables for production/development mode.
- Secure cookie enabled by default unless explicit development mode is set.
- Bind to localhost by default where appropriate.
- Document reverse proxy TLS expectations.
- Document the lack of email notifications for public account requests.

Relevant environment variables:

    FLUXTUNER_WEB_SETUP_TOKEN
    FLUXTUNER_WEB_SECURE_COOKIES=true
    FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS=86400
    FLUXTUNER_DATA_DIR=/data

## Testing requirements

Minimum tests before release:

- User creation stores a password hash, not the password.
- Correct password logs in.
- Wrong password fails with a generic error.
- Disabled user cannot log in.
- Pending user cannot log in and only sees pending status with the correct password.
- Rejected user cannot log in.
- Public registration creates a pending inactive user and does not create a session.
- Admin can approve or reject pending users.
- Logout invalidates the session.
- Session cookie has expected security attributes.
- Unauthenticated Web API requests are rejected.
- Unsafe authenticated requests require CSRF protection.
- Two users can have a profile with the same name.
- User A cannot read user B favorites.
- User A cannot mutate user B playlists.
- Non-admin users cannot read admin metrics from the dashboard.
- Existing profile data migrates to the default web user.

## Security non-goals

- CLI/TUI/GTK local profile selection is not a hard security boundary.
- SQLite encryption at rest is not part of the 1.0 Web/server model.
- Browser extension compromise is not solved by this model.
- HTTPS termination is expected from a reverse proxy or deployment layer.

## References

- OWASP Authentication Cheat Sheet
- OWASP Password Storage Cheat Sheet
- OWASP Session Management Cheat Sheet
- OWASP Cross-Site Request Forgery Prevention Cheat Sheet

## Secure deployment documentation

Operational deployment guidance lives in [`docs/secure-web-deployment.md`](secure-web-deployment.md). That document covers reverse proxy usage, secure cookies, setup tokens, persistent data, backups and post-deploy verification.
