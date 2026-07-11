import json

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_static_js_uses_module_entrypoint() -> None:
    client = TestClient(create_app())

    html_response = client.get("/")
    app_response = client.get("/static/app.js")
    api_response = client.get("/static/js/api.js")

    assert html_response.status_code == 200
    assert app_response.status_code == 200
    assert api_response.status_code == 200
    assert '<script type="module" src="/static/app.js"></script>' in html_response.text
    assert 'import { createApiFetch } from "/static/js/api.js";' in app_response.text
    assert "export function createApiFetch" in api_response.text
    assert "X-FluxTuner-CSRF" in api_response.text
    assert "response.status === 401" in api_response.text
    assert app_response.headers["cache-control"] == "no-cache"
    assert api_response.headers["cache-control"] == "no-cache"


def test_web_static_js_uses_application_dom_registry() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    elements_response = client.get("/static/js/app-elements.js")

    assert app_response.status_code == 200
    assert elements_response.status_code == 200
    assert 'import { createAppElements } from "/static/js/app-elements.js";' in app_response.text
    assert "export function createAppElements(root = document)" in elements_response.text
    assert "} = createAppElements();" in app_response.text
    assert 'root.querySelector("[data-app-header]")' in elements_response.text
    assert 'root.querySelectorAll("[data-private-action]")' in elements_response.text
    assert 'root.querySelectorAll("[data-dashboard-action]")' in elements_response.text
    assert "document.querySelector(" not in app_response.text
    assert "document.querySelectorAll(" not in app_response.text
    assert "document.getElementById(" not in app_response.text
    assert "document.getElementsByClassName(" not in app_response.text
    assert "document.getElementsByTagName(" not in app_response.text


def test_web_static_js_uses_theme_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    theme_response = client.get("/static/js/theme.js")

    assert app_response.status_code == 200
    assert theme_response.status_code == 200
    assert 'import { createThemeController } from "/static/js/theme.js";' in app_response.text
    assert "export function createThemeController" in theme_response.text
    assert 'const THEME_STORAGE_KEY = "fluxtuner.theme";' in theme_response.text
    assert "themeController.initializeTheme();" in app_response.text
    assert 'themeToggleButton.addEventListener("click", toggleTheme);' in app_response.text
    assert "function systemThemePreference()" not in app_response.text


def test_web_static_js_uses_ui_shell_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert 'import { createUiShellController } from "/static/js/ui-shell.js";' in app_response.text
    assert "export function createUiShellController" in module_response.text
    assert "function setResultsHeader" in module_response.text
    assert "function resetRadioBrowserView" in module_response.text
    assert "function showDashboardView" in module_response.text
    assert "const uiShellController = createUiShellController({" in app_response.text
    assert "function setResultsHeader" not in app_response.text
    assert "function resetRadioBrowserView" not in app_response.text
    assert "function showDashboardView" not in app_response.text


def test_web_static_js_uses_public_stats_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    public_stats_response = client.get("/static/js/public-stats.js")

    assert app_response.status_code == 200
    assert public_stats_response.status_code == 200
    assert (
        'import { createPublicStatsController } from "/static/js/public-stats.js";'
        in app_response.text
    )
    assert "export function createPublicStatsController" in public_stats_response.text
    assert 'fetchImpl("/api/public/stats"' in public_stats_response.text
    assert "publicStatsController.loadPublicStats();" in app_response.text
    assert "function renderPublicStats" not in app_response.text


def test_web_static_js_uses_account_requests_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/account-requests.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createAccountRequestsController } from "/static/js/account-requests.js";'
        in app_response.text
    )
    assert "export function createAccountRequestsController" in module_response.text
    assert 'fetchImpl("/api/auth/register"' in module_response.text
    assert 'fetchImpl("/api/auth/password-change-requests"' in module_response.text
    assert "authMessageNode.hidden = false;" in module_response.text
    assert module_response.text.count("authMessageNode.hidden = false;") == 2
    assert "function errorMessage" in module_response.text
    assert "setPasswordChangeMessage(errorMessage(error));" in module_response.text
    assert "setRegisterMessage(errorMessage(error));" in module_response.text
    assert "function focusFirstDialogControl" in module_response.text
    assert "function setRegisterMessage" not in app_response.text
    assert "function setPasswordChangeMessage" not in app_response.text


def test_web_static_js_uses_admin_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    admin_response = client.get("/static/js/admin.js")

    assert app_response.status_code == 200
    assert admin_response.status_code == 200
    assert 'import { createAdminController } from "/static/js/admin.js";' in app_response.text
    assert "export function createAdminController" in admin_response.text
    assert 'apiFetch("/api/admin/users"' in admin_response.text
    assert 'apiFetch("/api/admin/password-change-requests"' in admin_response.text
    assert "data-admin-user-action" in admin_response.text
    assert "function renderUsers" in admin_response.text
    assert "function renderPasswordChangeRequests" in admin_response.text
    assert "if (usersLoaded) {" in admin_response.text
    assert "await loadPasswordChangeRequests({ silent: true });" in admin_response.text
    assert "await loadDashboard({ preserveView: true, silent: true });" in admin_response.text
    assert "function renderUsers" not in app_response.text


def test_web_static_js_initializes_setup_before_auth() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadAuthState();\nasync function initializeAuthFlow" not in response.text
    assert "await loadSetupState();" in response.text
    assert "if (setupController.isSetupAvailable())" in response.text
    initialize_body = response.text.split("async function initializeAuthFlow()", 1)[1]
    assert "await loadAuthState();" not in initialize_body


def test_web_static_js_sanitizes_external_station_urls() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    stations_response = client.get("/static/js/stations.js")
    renderer_response = client.get("/static/js/station-renderer.js")

    assert app_response.status_code == 200
    assert stations_response.status_code == 200
    assert renderer_response.status_code == 200
    assert 'from "/static/js/stations.js"' in app_response.text
    assert 'from "/static/js/station-renderer.js"' in app_response.text
    assert "export function safeExternalUrl(value)" in stations_response.text
    assert "/^https?:\\/\\//i.test(rawUrl)" in stations_response.text
    assert '["http:", "https:"].includes(parsed.protocol)' in stations_response.text
    assert "export function stationHomepage(station)" in stations_response.text
    assert "export function formatDisplayDateTime(value)" in stations_response.text
    assert "export function createStationRenderer" in renderer_response.text
    assert "formatDisplayDateTime," in renderer_response.text
    assert "const homepage = stationHomepage(station);" in renderer_response.text
    assert (
        "const lastPlayedAt = formatDisplayDateTime(station.last_played_at);"
        in renderer_response.text
    )
    assert (
        "const lastPlayedAt = formatDisplayDateTime(station.last_played_at);"
        not in app_response.text
    )


def test_web_static_js_uses_station_renderer_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/station-renderer.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createStationRenderer } from "/static/js/station-renderer.js";'
        in app_response.text
    )
    assert "export function createStationRenderer" in module_response.text
    assert "function renderStation(station)" in module_response.text
    assert "function bindResultActions()" in module_response.text
    assert "function parseStationButton(button)" in module_response.text
    assert 'button.dataset.stationActionBound === "true"' in module_response.text
    assert "const stationRenderer = createStationRenderer({" in app_response.text
    assert "const { bindResultActions, renderStation } = stationRenderer;" in app_response.text
    assert "function renderStation(station)" not in app_response.text
    assert "function parseStationButton(button)" not in app_response.text


def test_web_static_js_defers_dashboard_station_renderer_callbacks() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "renderStation: (station) => renderStation(station)," in response.text
    assert "bindResultActions: () => bindResultActions()," in response.text
    dashboard_index = response.text.index("const dashboardController = createDashboardController({")
    station_renderer_index = response.text.index("const stationRenderer = createStationRenderer({")
    assert dashboard_index < station_renderer_index


def test_web_manifest_is_valid_json() -> None:
    client = TestClient(create_app())

    response = client.get("/static/site.webmanifest")

    assert response.status_code == 200
    manifest = json.loads(response.text)
    assert manifest["name"] == "FluxTuner Web"
    assert manifest["categories"] == ["music", "entertainment"]
    assert response.headers["cache-control"] == "no-cache"


def test_web_static_js_uses_playlists_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/playlists.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createPlaylistController } from "/static/js/playlists.js";' in app_response.text
    )
    assert "export function createPlaylistController" in module_response.text
    assert "const MAX_PLAYLIST_NAME_LENGTH = 120;" in module_response.text
    assert "playlistName.length > MAX_PLAYLIST_NAME_LENGTH" in module_response.text
    assert "cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH" in module_response.text
    assert "const playlistController = createPlaylistController({" in app_response.text
    assert "function setPlaylistDialogMessage" not in app_response.text


def test_web_static_js_uses_playlist_renderer_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/playlist-renderer.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createPlaylistRenderer } from "/static/js/playlist-renderer.js";'
        in app_response.text
    )
    assert "export function createPlaylistRenderer" in module_response.text
    assert "function renderPlaylists(payload)" in module_response.text
    assert "function bindPlaylistActions()" in module_response.text
    assert "data-create-playlist-form" in module_response.text
    assert "data-open-playlist" in module_response.text
    assert "data-delete-playlist" in module_response.text
    assert "const playlistRenderer = createPlaylistRenderer({" in app_response.text
    assert "const { bindPlaylistActions, renderPlaylists } = playlistRenderer;" in app_response.text
    assert "function renderPlaylists(payload)" not in app_response.text
    assert "function bindPlaylistActions()" not in app_response.text


def test_web_static_js_uses_favorites_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/favorites.js")
    player_response = client.get("/static/js/player.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert player_response.status_code == 200
    assert (
        'import { createFavoriteController } from "/static/js/favorites.js";' in app_response.text
    )
    assert "export function createFavoriteController" in module_response.text
    assert 'apiFetch("/api/history"' in module_response.text
    assert 'apiFetch("/api/favorites"' in module_response.text
    assert "apiFetch(`/api/favorites?url=${encodeURIComponent(url)}`" in module_response.text
    assert "const favoriteController = createFavoriteController({" in app_response.text
    assert "resetRecordedHistory();" in player_response.text
    assert "function recordHistory" not in app_response.text
    assert "function addFavorite" not in app_response.text
    assert "function removeFavorite" not in app_response.text


def test_web_static_js_uses_search_limit_from_form() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    search_response = client.get("/static/js/search.js")

    assert app_response.status_code == 200
    assert search_response.status_code == 200
    assert 'from "/static/js/search.js"' in app_response.text
    assert "const searchController = createSearchController({" in app_response.text
    assert "const { renderResults, renderSearchError } = searchController;" in app_response.text
    assert 'params.set("limit", String(formData.get("limit") || "25"));' in search_response.text
    assert 'params.set("limit", "25");' not in search_response.text


def test_web_static_js_uses_library_views_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/library-views.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createLibraryViewsController } from "/static/js/library-views.js";'
        in app_response.text
    )
    assert "export function createLibraryViewsController" in module_response.text
    assert 'apiFetch("/api/history?limit=25"' in module_response.text
    assert 'apiFetch("/api/favorites"' in module_response.text
    assert 'apiFetch("/api/playlists"' in module_response.text
    assert "function loadHistory" in module_response.text
    assert "function loadFavorites" in module_response.text
    assert "function loadPlaylists" in module_response.text
    assert "function loadPlaylistStations" in module_response.text
    assert "function loadHistory" not in app_response.text
    assert "function loadFavorites" not in app_response.text
    assert "function loadPlaylists" not in app_response.text
    assert "function loadPlaylistStations" not in app_response.text


def test_web_search_form_has_optional_debug_panel() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    search_response = client.get("/static/js/search.js")
    html_response = client.get("/")
    stations_css_response = client.get("/static/stations.css")

    assert app_response.status_code == 200
    assert search_response.status_code == 200
    assert html_response.status_code == 200
    assert stations_css_response.status_code == 200

    assert 'from "/static/js/search.js"' in app_response.text
    assert 'name="debug" type="checkbox" value="1"' in html_response.text
    assert "Search debug" in search_response.text
    assert 'params.set("debug", "1");' in search_response.text
    assert "function renderSearchDebug(debug)" in search_response.text
    assert "payload.debug" in search_response.text
    assert "cache_bypassed" in search_response.text
    assert "name returned" in search_response.text
    assert "tag returned" in search_response.text
    assert ".search-debug-panel" in stations_css_response.text
    assert ".search-debug-label" in stations_css_response.text
    assert "min-width: 0;" in stations_css_response.text
    assert "minmax(9rem, 0.85fr)" in stations_css_response.text


def test_web_static_js_allows_min_bitrate_only_search() -> None:
    client = TestClient(create_app())

    response = client.get("/static/js/search.js")

    assert response.status_code == 200
    assert 'const minBitrate = String(formData.get("min_bitrate") || "0").trim();' in response.text
    assert (
        'const hasMinBitrateFilter = Number(params.get("min_bitrate") || "0") > 0;' in response.text
    )
    assert "Search text, country, or minimum bitrate is required." in response.text
    assert "Search text or country is required." not in response.text


def test_web_static_js_keeps_station_available_after_media_pause() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    player_response = client.get("/static/js/player.js")

    assert app_response.status_code == 200
    assert player_response.status_code == 200
    assert 'import { createPlayerController } from "/static/js/player.js";' in app_response.text
    assert (
        "const hasStream = Boolean(currentStation && stationUrl(currentStation));"
        in player_response.text
    )
    assert "toggleButton.disabled = !hasStream || isLoading;" in player_response.text
    assert 'toggleButton.textContent = "Retry";' in player_response.text
    assert "function pauseCurrentStationPlayback" in player_response.text
    assert "function stopPlayback()" in player_response.text
    assert "currentStation = null;" in player_response.text
    assert "async function startCurrentStationPlayback(" in player_response.text
    assert 'audioNode.removeAttribute("src");' in player_response.text
    assert "let playbackRunId = 0;" in player_response.text
    assert "function isCurrentPlaybackRun(runId)" in player_response.text
    assert 'audioNode.addEventListener("pause"' in player_response.text


def test_web_static_js_sets_media_session_metadata_and_handlers() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/media-session.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createMediaSessionController } from "/static/js/media-session.js";'
        in app_response.text
    )
    assert "export function createMediaSessionController" in module_response.text
    assert "navigator.mediaSession.metadata" in module_response.text
    assert "new MediaMetadata" in module_response.text
    assert "artwork: resolvedArtwork()" in module_response.text
    assert "function resolvedArtwork()" in module_response.text
    assert "new URL(src, window.location.href).href" in module_response.text
    assert "/static/icons/icon-192.png" in module_response.text
    assert "/static/icons/icon-512.png" in module_response.text
    assert "function stationTitle(station)" in module_response.text
    assert "function setupMediaSessionHandlers()" in module_response.text
    assert 'navigator.mediaSession.setActionHandler("play"' in module_response.text
    assert 'navigator.mediaSession.setActionHandler("pause"' in module_response.text
    assert 'navigator.mediaSession.setActionHandler("stop"' in module_response.text
    assert "stopPlayback();" in module_response.text
    assert 'behavior: "stop-playback"' in module_response.text
    assert module_response.text.count('navigator.mediaSession.setActionHandler("play"') == 1
    assert module_response.text.count('navigator.mediaSession.setActionHandler("pause"') == 1
    assert module_response.text.count('navigator.mediaSession.setActionHandler("stop"') == 1
    assert "function setupMediaSessionHandlers()" not in app_response.text


def test_web_static_js_restarts_live_stream_from_system_controls() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    player_response = client.get("/static/js/player.js")
    module_response = client.get("/static/js/media-session.js")

    assert app_response.status_code == 200
    assert player_response.status_code == 200
    assert module_response.status_code == 200
    assert "function waitForAudioPlaybackStart" in player_response.text
    assert "function attemptCurrentStationPlayback" in player_response.text
    assert player_response.text.count("updateMediaSessionState") >= 1
    assert "function updateMediaSessionState" not in app_response.text
    assert player_response.text.count("function waitForAudioPlaybackStart") == 1
    assert player_response.text.count("function attemptCurrentStationPlayback") == 1
    assert "function setupMediaSessionHandlers" not in app_response.text
    assert (
        'startCurrentStationPlayback("Starting stream from system controls...")'
        in module_response.text
    )
    assert "stream did not start in time" in player_response.text
    assert 'audioNode.addEventListener("timeupdate", handleStarted' in player_response.text
    assert 'audioNode.addEventListener("canplay", handleStarted' not in player_response.text
    assert "scheduleBufferingNotice" in player_response.text
    assert "Still buffering stream..." in player_response.text
    assert 'navigator.mediaSession.playbackState = "paused";' in module_response.text
    assert 'navigator.mediaSession.playbackState = "none";' in module_response.text


def test_web_static_js_has_opt_in_player_debug_logging() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/player-debug.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert (
        'import { createPlayerDebugController } from "/static/js/player-debug.js";'
        in app_response.text
    )
    assert 'const PLAYER_DEBUG_STORAGE_KEY = "fluxtunerPlayerDebug";' in module_response.text
    assert 'const PLAYER_DEBUG_QUERY_KEY = "player_debug";' in module_response.text
    assert "function initialize()" in module_response.text
    assert "function logEvent(eventName, details = {})" in module_response.text
    assert "params.get(PLAYER_DEBUG_QUERY_KEY)" in module_response.text
    assert 'window.localStorage.setItem(PLAYER_DEBUG_STORAGE_KEY, "1")' in module_response.text
    assert "window.localStorage.removeItem(PLAYER_DEBUG_STORAGE_KEY)" in module_response.text
    assert 'console.debug("[FluxTuner player]"' in module_response.text


def test_web_static_js_logs_player_lifecycle_events_when_debug_enabled() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")
    player_response = client.get("/static/js/player.js")
    media_session_response = client.get("/static/js/media-session.js")

    assert response.status_code == 200
    assert player_response.status_code == 200
    assert media_session_response.status_code == 200
    for event_name in [
        "media-session-play",
        "media-session-pause",
        "media-session-stop",
    ]:
        assert event_name in media_session_response.text

    for event_name in [
        "audio-play",
        "audio-playing",
        "audio-pause",
        "audio-waiting",
        "audio-error",
        "document-visibilitychange",
        "window-pagehide",
        "window-pageshow",
        "window-online",
        "window-offline",
    ]:
        assert event_name in player_response.text

    for event_name in ["loadedmetadata", "audio-timeupdate-first"]:
        assert event_name in player_response.text
    assert "reapplyMediaSessionMetadata" in player_response.text
    assert '[\n      "abort",' in player_response.text
    assert "function audioDebugSnapshot()" in player_response.text
    assert "function mediaSessionDebugSnapshot()" in player_response.text
    assert "readyState: audioNode.readyState" in player_response.text
    assert "networkState: audioNode.networkState" in player_response.text
    assert 'currentSrc: audioNode["currentSrc"] || ""' in player_response.text
    assert "errorCode: audioNode.error?.code || null" in player_response.text


def test_web_static_js_has_admin_player_debug_panel() -> None:
    client = TestClient(create_app())

    js_response = client.get("/static/app.js")
    module_response = client.get("/static/js/player-debug.js")
    player_response = client.get("/static/js/player.js")
    html_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")

    assert js_response.status_code == 200
    assert module_response.status_code == 200
    assert player_response.status_code == 200
    assert html_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200

    assert "data-admin-panel" in html_response.text
    assert "data-player-debug-panel" in html_response.text
    assert "data-player-debug-summary" in html_response.text
    assert "data-player-debug-enable" in html_response.text
    assert "Enable player debug on this browser" in html_response.text
    assert "data-player-debug-toggle" in html_response.text
    assert "data-player-debug-copy" in html_response.text
    assert "data-player-debug-clear" in html_response.text
    assert "data-player-debug-download" in html_response.text
    assert "Download" in html_response.text
    assert "data-player-debug-snapshot" in html_response.text
    assert "data-player-debug-log" in html_response.text
    assert "data-player-debug-export" in html_response.text
    assert "Playback diagnostics" in html_response.text
    assert "Current snapshot" in html_response.text
    assert "Current audio, player and Media Session state." in html_response.text
    assert "Recent events" in html_response.text
    assert "Last captured playback and Media Session events." in html_response.text
    assert "Exported debug log" in html_response.text

    assert "const PLAYER_DEBUG_EVENT_LIMIT = 80;" in module_response.text
    elements_response = client.get("/static/js/app-elements.js")
    assert elements_response.status_code == 200
    assert (
        'playerDebugPanel: root.querySelector("[data-player-debug-panel]"),'
        in elements_response.text
    )
    assert "debugSnapshot(details = {})" in player_response.text
    assert "function applyState(nextEnabled, persist = true)" in module_response.text
    assert "function updateVisibility()" in module_response.text
    assert "function render()" in module_response.text
    assert "function copyLog()" in module_response.text
    assert "function downloadLog()" in module_response.text
    assert "function clearLog()" in module_response.text
    assert "function toggleDetails()" in module_response.text
    assert "panel.hidden = !showAdminDebug;" in module_response.text
    assert "enableInput.checked = enabled;" in module_response.text
    assert "playerDebugController.applyState(playerDebugEnableInput.checked);" in js_response.text
    assert "events.length > PLAYER_DEBUG_EVENT_LIMIT" in module_response.text
    assert "showExport(data);" in module_response.text
    assert "exportNode.select();" in module_response.text
    assert (
        "Clipboard unavailable. Select and copy the log below, or use Download log."
        in module_response.text
    )
    assert 'new Blob([data], { type: "text/plain;charset=utf-8" })' in module_response.text
    assert "link.download = filename;" in module_response.text
    assert "window.setTimeout(() => URL.revokeObjectURL(url), 1000);" in module_response.text
    media_session_response = client.get("/static/js/media-session.js")

    assert media_session_response.status_code == 200
    assert (
        'logPlayerEvent("media-session-stop", { behavior: "stop-playback" });'
        in media_session_response.text
    )
    assert "Player debug log download started:" in module_response.text

    combined_css = styles_response.text + admin_response.text
    assert ".player-debug-panel" in admin_response.text
    assert ".player-debug-enable" in admin_response.text
    assert ".player-debug-actions" in admin_response.text
    assert ".player-debug-export" in admin_response.text
    assert ".player-debug-panel" not in styles_response.text
    assert ".player-debug-enable" not in styles_response.text
    assert ".player-debug-actions" not in styles_response.text
    assert "\n.player-debug-export {" not in styles_response.text
    assert ".player-debug-section" in combined_css
    assert ".player-debug-export-section:has(.player-debug-export[hidden])" in combined_css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in admin_response.text


def test_web_setup_form_layout_keeps_password_fields_together() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    auth_response = client.get("/static/auth.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert auth_response.status_code == 200

    auth_link = '<link rel="stylesheet" href="/static/auth.css">'
    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    assert auth_link in page_response.text
    assert admin_link in page_response.text
    assert page_response.text.index(auth_link) < page_response.text.index(admin_link)

    assert '"username token"' in auth_response.text
    assert '"password confirm"' in auth_response.text
    assert "grid-area: token;" in auth_response.text
    assert ".auth-panel" in auth_response.text
    assert ".setup-panel" in auth_response.text
    assert ".auth-form" in auth_response.text
    assert ".setup-form" in auth_response.text
    assert "@media (max-width: 58rem)" in auth_response.text
    assert "@media (max-width: 42rem)" in auth_response.text
    assert '"username token"' not in styles_response.text
    assert "\n.setup-form {" not in styles_response.text
    assert "\n.auth-form," not in styles_response.text
    assert "/* Auth panels and compact player */" not in styles_response.text


def test_web_dialog_and_admin_forms_keep_password_fields_together() -> None:
    client = TestClient(create_app())

    styles_response = client.get("/static/styles.css")
    dialogs_response = client.get("/static/dialogs.css")
    admin_response = client.get("/static/admin.css")

    assert styles_response.status_code == 200
    assert dialogs_response.status_code == 200
    assert admin_response.status_code == 200

    assert "[data-password-change-form]" in dialogs_response.text
    assert '"username note"' in dialogs_response.text
    assert '"password confirm"' in dialogs_response.text
    assert "[data-register-form]" in dialogs_response.text
    assert '"username display"' in dialogs_response.text
    assert ".register-form" in dialogs_response.text
    assert ".register-dialog-message" in dialogs_response.text
    assert "@media (max-width: 58rem)" in dialogs_response.text
    assert "@media (max-width: 760px)" in dialogs_response.text

    assert "[data-admin-create-user-form]" in admin_response.text
    assert "[data-admin-password-form]" in admin_response.text
    assert ".admin-forms" in admin_response.text
    assert ".admin-users-table" in admin_response.text
    assert ".admin-user-actions" in admin_response.text
    assert ".admin-user-danger-zone" in admin_response.text
    assert "@media (max-width: 60rem)" in admin_response.text
    assert "@media (max-width: 24rem)" in admin_response.text

    assert "[data-password-change-form]" not in styles_response.text
    assert "[data-register-form]" not in styles_response.text
    assert "\n.register-form {" not in styles_response.text
    assert "\n.register-dialog-message {" not in styles_response.text
    assert "[data-admin-create-user-form]" not in styles_response.text
    assert "[data-admin-password-form]" not in styles_response.text
    assert "\n.admin-forms {" not in styles_response.text
    assert "\n.admin-users-table {" not in styles_response.text
    assert "\n.admin-user-danger-zone {" not in styles_response.text


def test_web_media_session_metadata_debug_and_reapply() -> None:
    client = TestClient(create_app())

    media_response = client.get("/static/js/media-session.js")
    player_response = client.get("/static/js/player.js")

    assert media_response.status_code == 200
    assert player_response.status_code == 200
    assert "debugSnapshot" in media_response.text
    assert "defaultArtwork: resolvedArtwork()" in media_response.text
    assert "new URL(src, window.location.href).href" in media_response.text
    assert "media-session-metadata" in media_response.text
    assert "reapplyCurrentMetadata" in media_response.text
    assert "mediaSessionController.debugSnapshot()" in player_response.text
    assert "reapplyMediaSessionMetadata" in player_response.text
    assert "audio-playing-event" in player_response.text
    assert "audio-timeupdate-first" in player_response.text
    assert "window-pageshow" in player_response.text


def test_web_player_prepares_audio_for_mobile_media_handoff() -> None:
    client = TestClient(create_app())

    response = client.get("/static/js/player.js")

    assert response.status_code == 200
    assert "function prepareAudioElementForMediaHandoff()" in response.text
    assert 'audioNode.crossOrigin = "anonymous";' in response.text
    assert "audioNode.title = title;" in response.text
    assert 'audioNode.setAttribute("aria-label", title);' in response.text
    assert "document-hidden" in response.text
    assert "window-pagehide" in response.text
    assert "visibilityReason" in response.text
    assert "crossOrigin:" in response.text


def test_web_static_js_keeps_production_console_clean() -> None:
    client = TestClient(create_app())

    favorites_response = client.get("/static/js/favorites.js")
    player_debug_response = client.get("/static/js/player-debug.js")

    assert favorites_response.status_code == 200
    assert player_debug_response.status_code == 200
    assert "console." not in favorites_response.text
    assert 'console.debug("[FluxTuner player]"' in player_debug_response.text


def test_web_shared_dialog_styles_are_isolated() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    dialogs_response = client.get("/static/dialogs.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert dialogs_response.status_code == 200

    dialogs_link = '<link rel="stylesheet" href="/static/dialogs.css">'
    auth_link = '<link rel="stylesheet" href="/static/auth.css">'
    assert dialogs_link in page_response.text
    assert auth_link in page_response.text
    assert page_response.text.index(dialogs_link) < page_response.text.index(auth_link)

    assert ".playlist-dialog" in dialogs_response.text
    assert ".playlist-dialog-card" in dialogs_response.text
    assert ".playlist-dialog-form" in dialogs_response.text
    assert ".playlist-dialog[hidden]" in dialogs_response.text
    assert ".register-dialog[hidden]" in dialogs_response.text
    assert ".password-change-dialog[hidden]" in dialogs_response.text
    assert "@media (max-width: 42rem)" in dialogs_response.text

    assert "\n.playlist-dialog {" not in styles_response.text
    assert "\n.playlist-dialog-card {" not in styles_response.text
    assert "\n.playlist-dialog-form {" not in styles_response.text
    assert ".register-form {" in dialogs_response.text
    assert ".register-dialog-message {" in dialogs_response.text
    assert "[data-register-form]" in dialogs_response.text
    assert "[data-password-change-form]" in dialogs_response.text

    assert "\n.register-form {" not in styles_response.text
    assert "\n.register-dialog-message {" not in styles_response.text
    assert "[data-register-form]" not in styles_response.text
    assert "[data-password-change-form]" not in styles_response.text
