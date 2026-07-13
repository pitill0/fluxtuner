/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const DEFAULT_ARTWORK = [
  { src: "/static/icons/icon-192.png", sizes: "192x192", type: "image/png" },
  { src: "/static/icons/icon-512.png", sizes: "512x512", type: "image/png" },
  { src: "/static/app-icon.png", sizes: "512x512", type: "image/png" },
];

function stationTitle(station) {
  return station?.name || station?.custom_name || station?.title || station?.url || "Unknown station";
}

function defaultStationUrl(station) {
  return cleanText(station?.url_resolved || station?.url);
}


function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function nowPlayingValues(metadata, fallbackTitle) {
  const station = cleanText(fallbackTitle) || "Unknown station";
  const artist = cleanText(metadata?.artist);
  const title = cleanText(metadata?.title);
  const raw = cleanText(metadata?.raw);

  return {
    station,
    title: title || raw || station,
    artist: artist || station,
  };
}

function absoluteArtworkUrl(src) {
  try {
    return new URL(src, window.location.href).href;
  } catch (_error) {
    return src;
  }
}

function resolvedArtwork() {
  return DEFAULT_ARTWORK.map((item) => ({
    ...item,
    src: absoluteArtworkUrl(item.src),
  }));
}

function metadataSnapshot() {
  if (!("mediaSession" in navigator)) {
    return {
      supported: false,
      mediaMetadataSupported: "MediaMetadata" in window,
    };
  }

  try {
    const metadata = navigator.mediaSession.metadata;
    return {
      supported: true,
      mediaMetadataSupported: "MediaMetadata" in window,
      playbackState: navigator.mediaSession.playbackState || "",
      hasMetadata: Boolean(metadata),
      title: metadata?.title || "",
      artist: metadata?.artist || "",
      album: metadata?.album || "",
      artwork: Array.from(metadata?.artwork || []).map((item) => ({
        src: item.src || "",
        sizes: item.sizes || "",
        type: item.type || "",
      })),
    };
  } catch (error) {
    return {
      supported: true,
      mediaMetadataSupported: "MediaMetadata" in window,
      unavailable: true,
      error: String(error),
    };
  }
}

export function createMediaSessionController({
  getCurrentStation,
  logPlayerEvent,
  pauseCurrentStationPlayback,
  startCurrentStationPlayback,
  stopPlayback,
  stationUrl = defaultStationUrl,
}) {
  let nowPlaying = null;
  let nowPlayingStationTitle = "";
  let nowPlayingStreamUrl = "";

  let lastUpdate = {
    reason: "",
    state: "",
    stationTitle: "",
    error: "",
    snapshot: metadataSnapshot(),
  };

  function rememberMediaSessionUpdate(reason, state = "") {
    lastUpdate = {
      reason,
      state,
      stationTitle: stationTitle(getCurrentStation()),
      error: "",
      snapshot: metadataSnapshot(),
    };
  }

  function rememberMediaSessionError(reason, error) {
    lastUpdate = {
      reason,
      state: "",
      stationTitle: stationTitle(getCurrentStation()),
      error: String(error),
      snapshot: metadataSnapshot(),
    };
  }

  function setMediaSessionMetadata(station, reason = "metadata") {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window) || !station) {
      rememberMediaSessionUpdate(`${reason}:unsupported`);
      return false;
    }

    try {
      const fallbackTitle = stationTitle(station);
      const currentStreamUrl = stationUrl(station);
      const activeNowPlaying =
        nowPlaying && nowPlayingStreamUrl === currentStreamUrl ? nowPlaying : null;

      navigator.mediaSession.metadata = new MediaMetadata({
        title: activeNowPlaying?.title || fallbackTitle,
        artist: activeNowPlaying?.artist || "FluxTuner Web",
        album: fallbackTitle,
        artwork: resolvedArtwork(),
      });
      rememberMediaSessionUpdate(reason);
      logPlayerEvent("media-session-metadata", lastUpdate);
      return true;
    } catch (error) {
      rememberMediaSessionError(reason, error);
      logPlayerEvent("media-session-metadata-error", lastUpdate);
      return false;
    }
  }

  function updateNowPlayingMetadata(
    metadata,
    fallbackTitle,
    streamUrl,
    reason = "now-playing",
  ) {
    const currentStation = getCurrentStation();
    const currentTitle = stationTitle(currentStation);

    if (!metadata) {
      nowPlaying = null;
      nowPlayingStationTitle = "";
      nowPlayingStreamUrl = "";
    } else {
      nowPlaying = nowPlayingValues(metadata, fallbackTitle);
      nowPlayingStationTitle = cleanText(fallbackTitle) || currentTitle;
      nowPlayingStreamUrl = cleanText(streamUrl);
    }

    if (!currentStation) {
      rememberMediaSessionUpdate(`${reason}:no-station`);
      return false;
    }

    return setMediaSessionMetadata(currentStation, reason);
  }

  function reapplyCurrentMetadata(reason = "reapply") {
    const currentStation = getCurrentStation();
    if (!currentStation) {
      rememberMediaSessionUpdate(`${reason}:no-station`);
      return false;
    }

    return setMediaSessionMetadata(currentStation, reason);
  }

  function clearMediaSessionMetadata() {
    if (!("mediaSession" in navigator)) {
      rememberMediaSessionUpdate("clear:unsupported");
      return;
    }

    try {
      nowPlaying = null;
      nowPlayingStationTitle = "";
      nowPlayingStreamUrl = "";
      navigator.mediaSession.metadata = null;
      navigator.mediaSession.playbackState = "none";
      rememberMediaSessionUpdate("clear", "none");
      logPlayerEvent("media-session-clear", lastUpdate);
    } catch (error) {
      rememberMediaSessionError("clear", error);
      logPlayerEvent("media-session-clear-error", lastUpdate);
    }
  }

  function updateMediaSessionState(state, reason = "state") {
    if (!("mediaSession" in navigator)) {
      rememberMediaSessionUpdate(`${reason}:unsupported`, state);
      return;
    }

    try {
      const currentStation = getCurrentStation();
      if (currentStation) {
        setMediaSessionMetadata(currentStation, `${reason}:metadata`);
      }

      if (state === "playing" || state === "loading") {
        navigator.mediaSession.playbackState = "playing";
      } else if (state === "paused" || state === "error" || currentStation) {
        navigator.mediaSession.playbackState = "paused";
      } else {
        navigator.mediaSession.playbackState = "none";
      }

      rememberMediaSessionUpdate(reason, state);
      logPlayerEvent("media-session-state", lastUpdate);
    } catch (error) {
      rememberMediaSessionError(reason, error);
      logPlayerEvent("media-session-state-error", lastUpdate);
    }
  }

  function debugSnapshot() {
    return {
      ...metadataSnapshot(),
      lastUpdate,
      nowPlaying,
      nowPlayingStationTitle,
      nowPlayingStreamUrl,
      defaultArtwork: resolvedArtwork(),
    };
  }

  function setupMediaSessionHandlers() {
    if (!("mediaSession" in navigator)) return;

    try {
      navigator.mediaSession.setActionHandler("play", () => {
        logPlayerEvent("media-session-play");
        if (getCurrentStation()) {
          reapplyCurrentMetadata("media-session-play");
          void startCurrentStationPlayback("Starting stream from system controls...");
        }
      });
      navigator.mediaSession.setActionHandler("pause", () => {
        logPlayerEvent("media-session-pause");
        reapplyCurrentMetadata("media-session-pause");
        pauseCurrentStationPlayback();
      });
      navigator.mediaSession.setActionHandler("stop", () => {
        logPlayerEvent("media-session-stop", { behavior: "stop-playback" });
        stopPlayback();
      });
    } catch (error) {
      rememberMediaSessionError("setup-handlers", error);
      logPlayerEvent("media-session-handler-error", lastUpdate);
    }
  }

  return {
    clearMediaSessionMetadata,
    debugSnapshot,
    reapplyCurrentMetadata,
    setMediaSessionMetadata,
    setupMediaSessionHandlers,
    updateMediaSessionState,
    updateNowPlayingMetadata,
  };
}
