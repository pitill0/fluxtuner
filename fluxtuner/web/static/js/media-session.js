/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createMediaSessionController({
  getCurrentStation,
  logPlayerEvent,
  pauseCurrentStationPlayback,
  startCurrentStationPlayback,
}) {
  function setMediaSessionMetadata(station) {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window) || !station) return;

    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: station.name || station.custom_name || "Unknown station",
        artist: "FluxTuner Web",
        album: "Internet radio",
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
        logPlayerEvent("media-session-stop", { behavior: "pause-with-station-preserved" });
        pauseCurrentStationPlayback("Playback paused by system controls.");
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
