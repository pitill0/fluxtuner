/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createPlayerController({
  audioNode,
  playerBar,
  titleNode,
  statusNode,
  toggleButton,
  stopButton,
  openLink,
  stationUrl,
  logPlayerEvent,
  mediaSessionController,
  recordHistory,
  resetRecordedHistory,
  windowRef = window,
  documentRef = document,
}) {
  let currentStation = null;
  let startingPlayback = false;
  let softPausingPlayback = false;
  let stoppingPlayback = false;
  let initialized = false;

  function audioDebugSnapshot() {
    if (!audioNode) return null;

    return {
      paused: audioNode.paused,
      ended: audioNode.ended,
      readyState: audioNode.readyState,
      networkState: audioNode.networkState,
      currentSrc: audioNode["currentSrc"] || "",
      src: audioNode.getAttribute("src") || "",
      errorCode: audioNode.error?.code || null,
      errorMessage: audioNode.error?.message || "",
    };
  }

  function mediaSessionDebugSnapshot() {
    if (!("mediaSession" in navigator)) return null;

    try {
      return {
        playbackState: navigator.mediaSession.playbackState || "",
        hasMetadata: Boolean(navigator.mediaSession.metadata),
      };
    } catch (_error) {
      return { unavailable: true };
    }
  }

  function debugSnapshot(details = {}) {
    return {
      state: playerBar?.dataset.state || "",
      station: currentStation
        ? {
            name: currentStation.name || currentStation.custom_name || "",
            url: stationUrl(currentStation),
          }
        : null,
      flags: {
        startingPlayback,
        softPausingPlayback,
        stoppingPlayback,
      },
      audio: audioDebugSnapshot(),
      mediaSession: mediaSessionDebugSnapshot(),
      visibilityState: documentRef.visibilityState || "",
      details,
    };
  }

  function getCurrentStation() {
    return currentStation;
  }

  function setPlayerState(state, message) {
    logPlayerEvent("player-state", { state, message });
    if (playerBar) {
      playerBar.dataset.state = state;
    }

    if (statusNode) {
      statusNode.textContent = message;
    }

    mediaSessionController.updateMediaSessionState(state);
  }

  function updatePlayerControls() {
    if (!audioNode || !toggleButton || !stopButton) return;

    const hasStream = Boolean(currentStation && stationUrl(currentStation));
    toggleButton.disabled = !hasStream;
    stopButton.disabled = !hasStream;

    if (audioNode.paused || playerBar?.dataset.state === "loading") {
      toggleButton.textContent = "Resume";
    } else {
      toggleButton.textContent = "Pause";
    }

    if (openLink) {
      openLink.hidden = !hasStream;

      if (hasStream) {
        openLink.href = stationUrl(currentStation);
      } else {
        openLink.removeAttribute("href");
      }
    }
  }

  function clearAudioSource() {
    if (!audioNode) return;

    audioNode.pause();
    audioNode.removeAttribute("src");
    audioNode.load();
  }

  function waitForAudioPlaybackStart(timeoutMs = 4500) {
    if (!audioNode) return Promise.reject(new Error("Audio element is unavailable."));

    return new Promise((resolve, reject) => {
      let timeoutId = 0;

      const cleanup = () => {
        windowRef.clearTimeout(timeoutId);
        audioNode.removeEventListener("playing", handleStarted);
        audioNode.removeEventListener("canplay", handleStarted);
        audioNode.removeEventListener("error", handleError);
      };

      const handleStarted = () => {
        cleanup();
        resolve();
      };

      const handleError = () => {
        cleanup();
        reject(new Error("stream failed to start after reload"));
      };

      timeoutId = windowRef.setTimeout(() => {
        cleanup();
        reject(new Error("stream did not start after reload"));
      }, timeoutMs);

      audioNode.addEventListener("playing", handleStarted, { once: true });
      audioNode.addEventListener("canplay", handleStarted, { once: true });
      audioNode.addEventListener("error", handleError, { once: true });
    });
  }

  async function attemptCurrentStationPlayback(streamUrl) {
    if (!audioNode) return;

    logPlayerEvent("playback-attempt", { streamUrl });
    clearAudioSource();
    audioNode.src = streamUrl;
    audioNode.load();

    const playbackStarted = waitForAudioPlaybackStart();
    await audioNode.play();
    await playbackStarted;
    logPlayerEvent("playback-attempt-started", { streamUrl });
  }

  async function startCurrentStationPlayback(message = "Loading stream...") {
    if (!audioNode || !currentStation) return;

    logPlayerEvent("playback-start-request", { message });

    const streamUrl = stationUrl(currentStation);
    if (!streamUrl) {
      setPlayerState("error", "This station has no playable stream URL.");
      updatePlayerControls();
      return;
    }

    startingPlayback = true;
    mediaSessionController.setMediaSessionMetadata(currentStation);
    setPlayerState("loading", message);
    updatePlayerControls();

    try {
      try {
        await attemptCurrentStationPlayback(streamUrl);
      } catch (firstError) {
        logPlayerEvent("playback-retry", { error: String(firstError) });
        await attemptCurrentStationPlayback(streamUrl);
      }

      setPlayerState("playing", "Playing in browser.");
      await recordHistory(currentStation);
    } catch (error) {
      logPlayerEvent("playback-start-failed", { error: String(error) });
      audioNode.pause();
      setPlayerState(
        "error",
        `Browser playback failed. Try opening the stream directly. ${error}`,
      );
    } finally {
      startingPlayback = false;
      updatePlayerControls();
    }
  }

  function pauseCurrentStationPlayback(message = "Paused.") {
    if (!audioNode || !currentStation) return;

    logPlayerEvent("playback-pause-request", { message });
    softPausingPlayback = true;
    audioNode.pause();
    mediaSessionController.setMediaSessionMetadata(currentStation);
    setPlayerState("paused", message);
    updatePlayerControls();
    windowRef.setTimeout(() => {
      softPausingPlayback = false;
    }, 0);
  }

  async function playStation(station) {
    if (!audioNode || !titleNode || !openLink) return;

    const streamUrl = stationUrl(station);
    if (!streamUrl) {
      setPlayerState("error", "This station has no playable stream URL.");
      return;
    }

    currentStation = station;
    resetRecordedHistory();
    titleNode.textContent = station.name || "Unknown station";
    openLink.href = streamUrl;
    openLink.hidden = false;

    await startCurrentStationPlayback("Loading stream...");
  }

  function stopPlayback() {
    if (!audioNode || !titleNode || !openLink) return;

    logPlayerEvent("playback-stop-request");
    stoppingPlayback = true;
    clearAudioSource();

    currentStation = null;
    resetRecordedHistory();
    titleNode.textContent = "Nothing playing yet";
    openLink.hidden = true;
    openLink.removeAttribute("href");

    mediaSessionController.clearMediaSessionMetadata();
    setPlayerState("idle", "Idle");
    updatePlayerControls();
    windowRef.setTimeout(() => {
      stoppingPlayback = false;
    }, 0);
  }

  async function togglePlayback() {
    if (!audioNode || !currentStation) return;

    logPlayerEvent("playback-toggle");

    if (audioNode.paused || playerBar?.dataset.state === "loading") {
      await startCurrentStationPlayback("Resuming stream...");
    } else {
      pauseCurrentStationPlayback("Paused.");
    }
  }

  function bindAudioEvents() {
    if (!audioNode) return;

    audioNode.addEventListener("play", () => {
      logPlayerEvent("audio-play");
      if (currentStation && !startingPlayback && !softPausingPlayback && !stoppingPlayback) {
        startCurrentStationPlayback("Restarting live stream...");
      }
    });

    audioNode.addEventListener("playing", () => {
      logPlayerEvent("audio-playing");
      if (currentStation) {
        setPlayerState("playing", "Playing in browser.");
        recordHistory(currentStation);
      }

      updatePlayerControls();
    });

    audioNode.addEventListener("pause", () => {
      logPlayerEvent("audio-pause");
      if (currentStation && !startingPlayback && !stoppingPlayback) {
        mediaSessionController.setMediaSessionMetadata(currentStation);
        setPlayerState("paused", "Paused.");
      }
      updatePlayerControls();
    });

    audioNode.addEventListener("waiting", () => {
      logPlayerEvent("audio-waiting");
      if (currentStation) {
        setPlayerState("loading", "Buffering stream...");
      }
    });

    audioNode.addEventListener("error", () => {
      logPlayerEvent("audio-error");
      if (currentStation) {
        setPlayerState("error", "Browser playback failed. Try Open stream.");
      }
      updatePlayerControls();
    });

    ["abort", "canplay", "emptied", "ended", "loadstart", "stalled", "suspend"].forEach(
      (eventName) => {
        audioNode.addEventListener(eventName, () => {
          logPlayerEvent(`audio-${eventName}`);
        });
      },
    );
  }

  function bindLifecycleEvents() {
    if (typeof documentRef !== "undefined") {
      documentRef.addEventListener("visibilitychange", () => {
        logPlayerEvent("document-visibilitychange");
      });
    }

    windowRef.addEventListener("pagehide", () => {
      logPlayerEvent("window-pagehide");
    });

    windowRef.addEventListener("pageshow", () => {
      logPlayerEvent("window-pageshow");
    });

    windowRef.addEventListener("online", () => {
      logPlayerEvent("window-online");
    });

    windowRef.addEventListener("offline", () => {
      logPlayerEvent("window-offline");
    });
  }

  function initialize() {
    if (initialized) return;
    initialized = true;

    if (toggleButton) {
      toggleButton.addEventListener("click", togglePlayback);
    }

    if (stopButton) {
      stopButton.addEventListener("click", stopPlayback);
    }

    bindAudioEvents();
    bindLifecycleEvents();
    updatePlayerControls();
  }

  return {
    debugSnapshot,
    getCurrentStation,
    initialize,
    pauseCurrentStationPlayback,
    playStation,
    setPlayerState,
    startCurrentStationPlayback,
    stopPlayback,
    togglePlayback,
    updatePlayerControls,
  };
}
