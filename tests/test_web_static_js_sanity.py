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
    assert "function renderUsers" not in app_response.text


def test_web_static_js_initializes_setup_before_auth() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadAuthState();\nasync function initializeAuthFlow" not in response.text
    assert "await loadSetupState();" in response.text
    assert "if (setupController.isSetupAvailable())" in response.text
    assert "await loadAuthState();" in response.text


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
    assert "data-create-playlist" in module_response.text
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
    css_response = client.get("/static/styles.css")

    assert app_response.status_code == 200
    assert search_response.status_code == 200
    assert html_response.status_code == 200
    assert css_response.status_code == 200

    assert 'from "/static/js/search.js"' in app_response.text
    assert 'name="debug" type="checkbox" value="1"' in html_response.text
    assert "Search debug" in search_response.text
    assert 'params.set("debug", "1");' in search_response.text
    assert "function renderSearchDebug(debug)" in search_response.text
    assert "payload.debug" in search_response.text
    assert "cache_bypassed" in search_response.text
    assert "name returned" in search_response.text
    assert "tag returned" in search_response.text
    assert ".search-debug-panel" in css_response.text
    assert ".search-debug-label" in css_response.text


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
    assert "toggleButton.disabled = !hasStream;" in player_response.text
    assert "function pauseCurrentStationPlayback" in player_response.text
    assert "function stopPlayback()" in player_response.text
    assert "currentStation = null;" in player_response.text
    assert "async function startCurrentStationPlayback(" in player_response.text
    assert 'audioNode.removeAttribute("src");' in player_response.text
    assert "audioNode.currentSrc" not in player_response.text
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
    assert "artwork: DEFAULT_ARTWORK" in module_response.text
    assert "/static/icons/icon-192.png" in module_response.text
    assert "/static/icons/icon-512.png" in module_response.text
    assert "function stationTitle(station)" in module_response.text
    assert "function setupMediaSessionHandlers()" in module_response.text
    assert 'navigator.mediaSession.setActionHandler("play"' in module_response.text
    assert 'navigator.mediaSession.setActionHandler("pause"' in module_response.text
    assert 'navigator.mediaSession.setActionHandler("stop"' in module_response.text
    assert (
        'pauseCurrentStationPlayback("Playback paused by system controls.");'
        in module_response.text
    )
    assert (
        'navigator.mediaSession.setActionHandler("stop", stopPlayback)' not in module_response.text
    )
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
    assert "stream did not start after reload" in player_response.text
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

    assert (
        '["abort", "canplay", "emptied", "ended", "loadstart", "stalled", "suspend"]'
        in player_response.text
    )
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
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert module_response.status_code == 200
    assert player_response.status_code == 200
    assert html_response.status_code == 200
    assert css_response.status_code == 200

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

    assert "const PLAYER_DEBUG_EVENT_LIMIT = 80;" in module_response.text
    assert (
        'const playerDebugPanel = document.querySelector("[data-player-debug-panel]");'
        in js_response.text
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
        'logPlayerEvent("media-session-stop", { behavior: "pause-with-station-preserved" });'
        in media_session_response.text
    )
    assert "Player debug log download started:" in module_response.text

    assert ".player-debug-panel" in css_response.text
    assert ".player-debug-enable" in css_response.text
    assert ".player-debug-actions" in css_response.text
    assert ".player-debug-export" in css_response.text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css_response.text
