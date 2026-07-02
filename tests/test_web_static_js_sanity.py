from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_static_js_initializes_setup_before_auth() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadAuthState();\nasync function initializeAuthFlow" not in response.text
    assert "await loadSetupState();" in response.text
    assert "if (setupAvailable)" in response.text
    assert "await loadAuthState();" in response.text


def test_web_static_js_sanitizes_external_station_urls() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "function safeExternalUrl(value)" in response.text
    assert "/^https?:\\/\\//i.test(rawUrl)" in response.text
    assert '["http:", "https:"].includes(parsed.protocol)' in response.text
    assert "function stationHomepage(station)" in response.text
    assert "const homepage = stationHomepage(station);" in response.text


def test_web_static_js_limits_playlist_names_client_side() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "const MAX_PLAYLIST_NAME_LENGTH = 120;" in response.text
    assert "playlistName.length > MAX_PLAYLIST_NAME_LENGTH" in response.text
    assert "cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH" in response.text


def test_web_static_js_keeps_station_available_after_media_pause() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert (
        "const hasStream = Boolean(currentStation && stationUrl(currentStation));" in response.text
    )
    assert "playerToggleButton.disabled = !hasStream;" in response.text
    assert "function pauseCurrentStationPlayback" in response.text
    assert "function stopPlayback()" in response.text
    assert "currentStation = null;" in response.text
    assert "async function startCurrentStationPlayback(" in response.text
    assert 'audioNode.removeAttribute("src");' in response.text
    assert "audioNode.currentSrc" not in response.text
    assert 'audioNode.addEventListener("pause"' in response.text


def test_web_static_js_sets_media_session_metadata_and_handlers() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "navigator.mediaSession.metadata" in response.text
    assert "new MediaMetadata" in response.text
    assert "function setupMediaSessionHandlers()" in response.text
    assert 'navigator.mediaSession.setActionHandler("play"' in response.text
    assert 'navigator.mediaSession.setActionHandler("pause"' in response.text
    assert 'navigator.mediaSession.setActionHandler("stop"' in response.text
    assert 'pauseCurrentStationPlayback("Playback paused by system controls.");' in response.text
    assert 'navigator.mediaSession.setActionHandler("stop", stopPlayback)' not in response.text
    assert response.text.count('navigator.mediaSession.setActionHandler("play"') == 1
    assert response.text.count('navigator.mediaSession.setActionHandler("pause"') == 1
    assert response.text.count('navigator.mediaSession.setActionHandler("stop"') == 1


def test_web_static_js_restarts_live_stream_from_system_controls() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "function waitForAudioPlaybackStart" in response.text
    assert "function attemptCurrentStationPlayback" in response.text
    assert response.text.count("function updateMediaSessionState") == 1
    assert response.text.count("function waitForAudioPlaybackStart") == 1
    assert response.text.count("function attemptCurrentStationPlayback") == 1
    assert response.text.count("function setupMediaSessionHandlers") == 1
    assert 'startCurrentStationPlayback("Starting stream from system controls...")' in response.text
    assert "stream did not start after reload" in response.text
    assert 'navigator.mediaSession.playbackState = "paused";' in response.text
    assert 'navigator.mediaSession.playbackState = "none";' in response.text


def test_web_static_js_has_opt_in_player_debug_logging() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'const PLAYER_DEBUG_STORAGE_KEY = "fluxtunerPlayerDebug";' in response.text
    assert 'const PLAYER_DEBUG_QUERY_KEY = "player_debug";' in response.text
    assert "function initializePlayerDebug()" in response.text
    assert "function logPlayerEvent(eventName, details = {})" in response.text
    assert "params.get(PLAYER_DEBUG_QUERY_KEY)" in response.text
    assert 'window.localStorage.setItem(PLAYER_DEBUG_STORAGE_KEY, "1")' in response.text
    assert "window.localStorage.removeItem(PLAYER_DEBUG_STORAGE_KEY)" in response.text
    assert 'console.debug("[FluxTuner player]"' in response.text


def test_web_static_js_logs_player_lifecycle_events_when_debug_enabled() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    for event_name in [
        "media-session-play",
        "media-session-pause",
        "media-session-stop",
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
        assert event_name in response.text

    assert (
        '["abort", "canplay", "emptied", "ended", "loadstart", "stalled", "suspend"]'
        in response.text
    )
    assert "function audioDebugSnapshot()" in response.text
    assert "function mediaSessionDebugSnapshot()" in response.text
    assert "readyState: audioNode.readyState" in response.text
    assert "networkState: audioNode.networkState" in response.text
    assert 'currentSrc: audioNode["currentSrc"] || ""' in response.text
    assert "errorCode: audioNode.error?.code || null" in response.text


def test_web_static_js_has_admin_player_debug_panel() -> None:
    client = TestClient(create_app())

    js_response = client.get("/static/app.js")
    html_response = client.get("/")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert html_response.status_code == 200
    assert css_response.status_code == 200

    assert "data-admin-panel" in html_response.text
    assert "data-player-debug-panel" in html_response.text
    assert "data-player-debug-summary" in html_response.text
    assert "data-player-debug-toggle" in html_response.text
    assert "data-player-debug-copy" in html_response.text
    assert "data-player-debug-clear" in html_response.text
    assert "data-player-debug-download" in html_response.text
    assert "data-player-debug-snapshot" in html_response.text
    assert "data-player-debug-log" in html_response.text
    assert "data-player-debug-export" in html_response.text
    assert "Playback diagnostics" in html_response.text

    assert "const PLAYER_DEBUG_EVENT_LIMIT = 80;" in js_response.text
    assert (
        'const playerDebugPanel = document.querySelector("[data-player-debug-panel]");'
        in js_response.text
    )
    assert "function playerDebugSnapshot(details = {})" in js_response.text
    assert "function renderPlayerDebugPanel()" in js_response.text
    assert "function copyPlayerDebugLog()" in js_response.text
    assert "function downloadPlayerDebugLog()" in js_response.text
    assert "function clearPlayerDebugLog()" in js_response.text
    assert "function togglePlayerDebugDetails()" in js_response.text
    assert "playerDebugPanel.hidden = !playerDebugEnabled" in js_response.text
    assert "playerDebugEvents.length > PLAYER_DEBUG_EVENT_LIMIT" in js_response.text
    assert "showPlayerDebugExport(payload);" in js_response.text
    assert "playerDebugExportNode.select();" in js_response.text
    assert (
        "Clipboard unavailable. Select and copy the log below, or use Download log."
        in js_response.text
    )
    assert 'new Blob([payload], { type: "text/plain;charset=utf-8" })' in js_response.text
    assert "link.download = filename;" in js_response.text
    assert "Player debug log download started:" in js_response.text

    assert ".player-debug-panel" in css_response.text
    assert ".player-debug-actions" in css_response.text
    assert ".player-debug-export" in css_response.text
