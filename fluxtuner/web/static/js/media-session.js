/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const DEFAULT_ARTWORK = [
  { src: "/static/icons/icon-192.png", sizes: "192x192", type: "image/png" },
  { src: "/static/icons/icon-512.png", sizes: "512x512", type: "image/png" },
];

function stationTitle(station) {
  return station?.name || station?.custom_name || station?.title || station?.url || "Unknown station";
}

export function createMediaSessionController({
  getCurrentStation,
  logPlayerEvent,
  pauseCurrentStationPlayback,
  startCurrentStationPlayback,
  stopPlayback,
}) {
  function setMediaSessionMetadata(station) {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window) || !station) return;

    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: stationTitle(station),
        artist: "FluxTuner Web",
        album: "Internet radio",
        artwork: DEFAULT_ARTWORK,
      });
    } catch (_error) {
      // MediaMetadata is optional even when mediaSession exists.
    }
  }

  function clearMediaSessionMetadata() {
    if (!("mediaSession" in navigator)) return;

    try {
      navigator.mediaSession.metadata = null;
      navigator.mediaSession.playbackState = "none";
    } catch (_error) {
      // Some browsers expose mediaSession only partially.
    }
  }

  function updateMediaSessionState(state) {
    if (!("mediaSession" in navigator)) return;

    try {
      const currentStation = getCurrentStation();
      if (currentStation) {
        setMediaSessionMetadata(currentStation);
      }

      if (state === "playing" || state === "loading") {
        navigator.mediaSession.playbackState = "playing";
      } else if (state === "paused" || currentStation) {
        navigator.mediaSession.playbackState = "paused";
      } else {
        navigator.mediaSession.playbackState = "none";
      }
    } catch (_error) {
      // Media Session support varies across desktop and mobile browsers.
    }
  }

  function setupMediaSessionHandlers() {
    if (!("mediaSession" in navigator)) return;

    try {
      navigator.mediaSession.setActionHandler("play", () => {
        logPlayerEvent("media-session-play");
        if (getCurrentStation()) {
          void startCurrentStationPlayback("Starting stream from system controls...");
        }
      });
      navigator.mediaSession.setActionHandler("pause", () => {
        logPlayerEvent("media-session-pause");
        pauseCurrentStationPlayback();
      });
      navigator.mediaSession.setActionHandler("stop", () => {
        logPlayerEvent("media-session-stop", { behavior: "stop-playback" });
        stopPlayback();
      });
    } catch (_error) {
      // Some browsers expose mediaSession without supporting all handlers.
    }
  }

  return {
    clearMediaSessionMetadata,
    setMediaSessionMetadata,
    setupMediaSessionHandlers,
    updateMediaSessionState,
  };
}
