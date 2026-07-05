/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const PLAYBACK_START_TIMEOUT_MS = 12000;
const BUFFERING_NOTICE_TIMEOUT_MS = 8000;

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
  let playbackRunId = 0;
  let bufferingNoticeTimeoutId = 0;

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
      playbackRunId,
      audio: audioDebugSnapshot(),
      mediaSession: mediaSessionDebugSnapshot(),
      visibilityState: documentRef.visibilityState || "",
      details,
    };
  }

  function getCurrentStation() {
    return currentStation;
  }

  function currentStreamUrl() {
    return currentStation ? stationUrl(currentStation) : "";
  }

  function nextPlaybackRun() {
    playbackRunId += 1;
    return playbackRunId;
  }

  function isCurrentPlaybackRun(runId) {
    return runId === playbackRunId;
  }

  function clearBufferingNotice() {
    if (!bufferingNoticeTimeoutId) return;

    windowRef.clearTimeout(bufferingNoticeTimeoutId);
    bufferingNoticeTimeoutId = 0;
  }

  function scheduleBufferingNotice(runId, message = "Still buffering stream...") {
    clearBufferingNotice();
    bufferingNoticeTimeoutId = windowRef.setTimeout(() => {
      bufferingNoticeTimeoutId = 0;
      if (!currentStation || !isCurrentPlaybackRun(runId) || playerBar?.dataset.state !== "loading") {
        return;
      }

      setPlayerState("loading", message);
      updatePlayerControls();
    }, BUFFERING_NOTICE_TIMEOUT_MS);
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
    const state = playerBar?.dataset.state || "idle";
    const isLoading = state === "loading" || startingPlayback;

    toggleButton.disabled = !hasStream || isLoading;
    stopButton.disabled = !hasStream;

    if (isLoading) {
      toggleButton.textContent = "Loading...";
    } else if (state === "error") {
      toggleButton.textContent = "Retry";
    } else if (audioNode.paused) {
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

  function waitForAudioPlaybackStart(runId, timeoutMs = PLAYBACK_START_TIMEOUT_MS) {
    if (!audioNode) return Promise.reject(new Error("Audio element is unavailable."));

    return new Promise((resolve, reject) => {
      let timeoutId = 0;

      const cleanup = () => {
        windowRef.clearTimeout(timeoutId);
        audioNode.removeEventListener("playing", handleStarted);
        audioNode.removeEventListener("timeupdate", handleStarted);
        audioNode.removeEventListener("error", handleError);
        audioNode.removeEventListener("stalled", handleStalled);
      };

      const resolveIfCurrent = () => {
        if (!isCurrentPlaybackRun(runId)) {
          cleanup();
          reject(new Error("playback request was replaced"));
          return false;
        }

        cleanup();
        resolve();
        return true;
      };

      const handleStarted = () => {
        resolveIfCurrent();
      };

      const handleError = () => {
        cleanup();
        reject(new Error("stream failed to start after reload"));
      };

      const handleStalled = () => {
        if (isCurrentPlaybackRun(runId)) {
          scheduleBufferingNotice(runId, "Still waiting for stream data...");
        }
      };

      timeoutId = windowRef.setTimeout(() => {
        cleanup();
        reject(new Error("stream did not start in time"));
      }, timeoutMs);

      audioNode.addEventListener("playing", handleStarted, { once: true });
      audioNode.addEventListener("timeupdate", handleStarted, { once: true });
      audioNode.addEventListener("error", handleError, { once: true });
      audioNode.addEventListener("stalled", handleStalled, { once: true });
    });
  }

  async function attemptCurrentStationPlayback(streamUrl, runId) {
    if (!audioNode) return;

    logPlayerEvent("playback-attempt", { streamUrl, runId });
    clearAudioSource();

    if (!isCurrentPlaybackRun(runId)) {
      throw new Error("playback request was replaced");
    }

    audioNode.src = streamUrl;
    audioNode.load();
    scheduleBufferingNotice(runId, "Still loading stream...");

    const playbackStarted = waitForAudioPlaybackStart(runId);
    await audioNode.play();
    await playbackStarted;

    if (!isCurrentPlaybackRun(runId)) {
      throw new Error("playback request was replaced");
    }

    clearBufferingNotice();
    logPlayerEvent("playback-attempt-started", { streamUrl, runId });
  }

  async function startCurrentStationPlayback(message = "Loading stream...") {
    if (!audioNode || !currentStation) return;

    const runId = nextPlaybackRun();
    logPlayerEvent("playback-start-request", { message, runId });

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
        await attemptCurrentStationPlayback(streamUrl, runId);
      } catch (firstError) {
        if (!isCurrentPlaybackRun(runId)) return;
        logPlayerEvent("playback-retry", { error: String(firstError), runId });
        setPlayerState("loading", "Retrying stream...");
        updatePlayerControls();
        await attemptCurrentStationPlayback(streamUrl, runId);
      }

      if (!isCurrentPlaybackRun(runId)) return;
      setPlayerState("playing", "Playing in browser.");
      await recordHistory(currentStation);
    } catch (error) {
      if (!isCurrentPlaybackRun(runId)) return;
      logPlayerEvent("playback-start-failed", { error: String(error), runId });
      clearBufferingNotice();
      audioNode.pause();
      setPlayerState(
        "error",
        `Could not start this stream. Try Retry, Stop, or Open externally. ${error}`,
      );
    } finally {
      if (isCurrentPlaybackRun(runId)) {
        startingPlayback = false;
        clearBufferingNotice();
        updatePlayerControls();
      }
    }
  }

  function pauseCurrentStationPlayback(message = "Paused.") {
    if (!audioNode || !currentStation) return;

    logPlayerEvent("playback-pause-request", { message });
    clearBufferingNotice();
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
    const runId = nextPlaybackRun();
    stoppingPlayback = true;
    clearBufferingNotice();
    clearAudioSource();

    currentStation = null;
    resetRecordedHistory();
    titleNode.textContent = "Nothing playing yet";
    openLink.hidden = true;
    openLink.removeAttribute("href");

    mediaSessionController.clearMediaSessionMetadata();
    setPlayerState("idle", "Idle");
    updatePlayerControls();
    logPlayerEvent("playback-stopped", { runId });

    windowRef.setTimeout(() => {
      stoppingPlayback = false;
    }, 0);
  }

  async function togglePlayback() {
    if (!audioNode || !currentStation) return;

    logPlayerEvent("playback-toggle");

    if (playerBar?.dataset.state === "loading" || startingPlayback) {
      return;
    }

    if (audioNode.paused || playerBar?.dataset.state === "error") {
      await startCurrentStationPlayback(
        playerBar?.dataset.state === "error" ? "Retrying stream..." : "Resuming stream...",
      );
    } else {
      pauseCurrentStationPlayback("Paused.");
    }
  }

  function bindAudioEvents() {
    if (!audioNode) return;

    audioNode.addEventListener("play", () => {
      logPlayerEvent("audio-play");
      if (currentStation && !startingPlayback && !softPausingPlayback && !stoppingPlayback) {
        void startCurrentStationPlayback("Restarting live stream...");
      }
    });

    audioNode.addEventListener("playing", () => {
      logPlayerEvent("audio-playing");
      clearBufferingNotice();
      if (currentStation) {
        setPlayerState("playing", "Playing in browser.");
        recordHistory(currentStation);
      }

      updatePlayerControls();
    });

    audioNode.addEventListener("pause", () => {
      logPlayerEvent("audio-pause");
      if (currentStation && !startingPlayback && !stoppingPlayback) {
        clearBufferingNotice();
        mediaSessionController.setMediaSessionMetadata(currentStation);
        setPlayerState("paused", "Paused.");
      }
      updatePlayerControls();
    });

    audioNode.addEventListener("waiting", () => {
      logPlayerEvent("audio-waiting");
      if (currentStation && !stoppingPlayback) {
        setPlayerState("loading", "Buffering stream...");
        scheduleBufferingNotice(playbackRunId);
      }
      updatePlayerControls();
    });

    audioNode.addEventListener("error", () => {
      logPlayerEvent("audio-error");
      clearBufferingNotice();
      if (currentStation && !startingPlayback && !stoppingPlayback) {
        setPlayerState("error", "Stream playback failed. Try Retry, Stop, or Open externally.");
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
        updatePlayerControls();
      });
    }

    windowRef.addEventListener("pagehide", () => {
      logPlayerEvent("window-pagehide");
    });

    windowRef.addEventListener("pageshow", () => {
      logPlayerEvent("window-pageshow");
      updatePlayerControls();
    });

    windowRef.addEventListener("online", () => {
      logPlayerEvent("window-online");
    });

    windowRef.addEventListener("offline", () => {
      logPlayerEvent("window-offline");
      if (currentStation) {
        setPlayerState("error", "Browser is offline. Playback may resume when network returns.");
        updatePlayerControls();
      }
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
