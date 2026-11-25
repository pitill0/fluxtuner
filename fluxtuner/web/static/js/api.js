/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const CSRF_HEADER_NAME = "X-FluxTuner-CSRF";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function createApiFetch({ getCsrfToken, onUnauthorized } = {}) {
  return async function apiFetch(url, options = {}) {
    const requestOptions = { ...options };
    const handleUnauthorized = requestOptions.handleUnauthorized !== false;
    delete requestOptions.handleUnauthorized;

    const method = String(requestOptions.method || "GET").toUpperCase();
    const csrfToken = typeof getCsrfToken === "function" ? getCsrfToken() : "";

    if (!SAFE_METHODS.has(method) && csrfToken) {
      requestOptions.headers = {
        ...(requestOptions.headers || {}),
        [CSRF_HEADER_NAME]: csrfToken,
      };
    }

    const response = await fetch(url, requestOptions);

    if (
      handleUnauthorized &&
      response.status === 401 &&
      typeof onUnauthorized === "function"
    ) {
      onUnauthorized();
    }

    return response;
  };
}

// Exact, documented API details only. Keep raw errors and HTTP behavior unchanged.
const ERROR_KEYS = new Map([
  ["Invalid username or password.", "api.invalid_credentials"],
  ["Too many login attempts. Try again later.", "api.login_rate"],
  ["Account pending approval.", "api.pending_approval"],
  ["Invalid recovery credentials.", "api.invalid_recovery"],
  ["Too many recovery attempts. Try again later.", "api.recovery_rate"],
  ["Authentication required.", "api.authentication_required"],
  ["CSRF token is missing or invalid.", "api.csrf"],
  ["One or more fields exceed the maximum allowed length.", "api.field_too_long"],
  ["Username is unavailable.", "api.username_unavailable"],
  ["Username and password are required.", "api.credentials_required"],
  ["Setup verification failed.", "api.setup_verification"],
  ["Too many reauthentication attempts. Try again later.", "api.reauth_rate"],
  ["Cannot remove the last active administrator.", "api.last_admin"],
  ["Administrators cannot delete their own account.", "api.self_delete"],
  ["Web user already exists.", "api.user_exists"],
  ["Web user not found.", "api.user_missing"],
  ["Station URL must be a valid HTTP or HTTPS URL.", "api.station_url"],
  ["Playlist name is required.", "api.playlist_name"],
  ["Too many setup attempts. Try again later.", "api.setup_rate"],
  ["Administrator access required.", "api.admin_required"],
  ["First-run setup is not available.", "api.setup_unavailable"],
  ["First-run setup requires local access or FLUXTUNER_WEB_SETUP_TOKEN.", "api.setup_local_only"],
  ["A collection URL is required.", "api.collection_required"],
  ["A valid HTTP or HTTPS URL is required.", "api.collection_url"],
  ["Artwork not available.", "api.artwork_missing"],
  ["Catalog is already subscribed.", "api.catalog_subscribed"],
  ["Could not retrieve the remote collection.", "api.collection_retrieve"],
  ["Expected a JSON URL request.", "api.url_request_expected"],
  ["Favorites are unavailable.", "api.favorites_unavailable"],
  ["Favorites cannot be exported.", "api.favorites_export_failed"],
  ["Favorites export is unavailable.", "api.favorites_export_unavailable"],
  ["Initial catalog must return a complete snapshot.", "api.catalog_snapshot"],
  ["Invalid JSON URL request.", "api.url_request_invalid"],
  ["Invalid catalog name.", "api.catalog_name"],
  ["Invalid collection URL length.", "api.collection_url_length"],
  ["Invalid recommendation selection.", "api.recommendation_selection"],
  ["Missing required value.", "api.required_value"],
  ["Playlist cannot be exported.", "api.playlist_export_failed"],
  ["Playlist export is unavailable.", "api.playlist_export_unavailable"],
  ["Playlist is unavailable.", "api.playlist_unavailable"],
  ["Profile unavailable.", "api.profile_unavailable"],
  ["Provide only a station name and stream URL as text.", "api.station_fields"],
  ["Publication unavailable.", "api.publication_unavailable"],
  ["Recommendation could not be sent.", "api.recommendation_send"],
  ["Recommendations unavailable.", "api.recommendations_unavailable"],
  ["Session required.", "api.session_required"],
  ["Station unavailable.", "api.station_unavailable"],
  ["Stream URL must be a valid HTTP or HTTPS URL.", "api.stream_url"],
  ["Stream metadata service is unavailable.", "api.metadata_unavailable"],
  ["The selected profile is unavailable.", "api.selected_profile"],
  ["Too many discovery attempts.", "api.discovery_rate"],
  ["URL request exceeds 4 KiB.", "api.url_request_size"],
  ["Upload the playlist file as raw bytes.", "api.playlist_raw_bytes"],
  ["The playlist exceeds 1 MiB.", "imports.feedback.size"],
]);

export function knownApiErrorKey(message) {
  return ERROR_KEYS.get(message);
}
