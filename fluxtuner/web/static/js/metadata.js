/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const DEFAULT_POLL_INTERVAL_MS = 15000;

function cleanText(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function metadataDisplayTitle(metadata, fallbackTitle) {
  const artist = cleanText(metadata?.artist);
  const title = cleanText(metadata?.title);
  const raw = cleanText(metadata?.raw);
  const fallback = cleanText(fallbackTitle) || "Unknown station";

  if (artist && title) return `${artist} — ${title}`;
  return title || raw || fallback;
}

export async function copyTextToClipboard(
  text,
  { navigatorRef = navigator, documentRef = document } = {},
) {
  const value = cleanText(text);
  if (!value) {
    throw new Error("No track information is available to copy.");
  }

  try {
    if (navigatorRef?.clipboard?.writeText) {
      await navigatorRef.clipboard.writeText(value);
      return;
    }
  } catch {
    // Private HTTP deployments may expose the API but reject writes.
  }

  const textarea = documentRef?.createElement?.("textarea");
  if (!textarea || !documentRef?.body || !documentRef.execCommand) {
    throw new Error("Clipboard access is unavailable.");
  }

  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  documentRef.body.append(textarea);
  textarea.select();

  try {
    if (!documentRef.execCommand("copy")) {
      throw new Error("Clipboard copy command was rejected.");
    }
  } finally {
    textarea.remove();
  }
}

export function trackOverflowDistance(scrollWidth, clientWidth) {
  return Math.max(0, Number(scrollWidth) - Number(clientWidth));
}

export function createMetadataController({
  apiFetch,
  titleNode,
  copyButton,
  stationNode,
  statusNode,
  onMetadataChange = () => {},
  logPlayerEvent = () => {},
  windowRef = window,
  navigatorRef = navigator,
  documentRef = document,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}) {
  let streamUrl = "";
  let fallbackTitle = "";
  let playbackActive = false;
  let timeoutId = 0;
  let requestGeneration = 0;
  let requestInFlight = false;
  let currentTrackText = "";
  let feedbackTimeoutId = 0;
  let overflowFrameId = 0;

  const requestFrame =
    windowRef.requestAnimationFrame?.bind(windowRef) ||
    ((callback) => windowRef.setTimeout(callback, 0));
  const cancelFrame =
    windowRef.cancelAnimationFrame?.bind(windowRef) ||
    ((frameId) => windowRef.clearTimeout(frameId));

  function clearFeedbackTimer() {
    if (!feedbackTimeoutId) return;
    windowRef.clearTimeout(feedbackTimeoutId);
    feedbackTimeoutId = 0;
  }

  function showCopyFeedback(message) {
    if (!statusNode) return;

    clearFeedbackTimer();
    const previousMessage = statusNode.textContent;
    statusNode.textContent = message;
    feedbackTimeoutId = windowRef.setTimeout(() => {
      feedbackTimeoutId = 0;
      if (statusNode.textContent === message) {
        statusNode.textContent = previousMessage;
      }
    }, 1800);
  }

  function refreshTrackOverflow() {
    overflowFrameId = 0;
    if (!copyButton || !titleNode) return;

    copyButton.dataset.overflow = "false";
    copyButton.style.removeProperty("--player-track-distance");
    copyButton.style.removeProperty("--player-track-duration");

    const distance = trackOverflowDistance(titleNode.scrollWidth, copyButton.clientWidth);
    if (distance <= 1 || copyButton.disabled) return;

    copyButton.style.setProperty("--player-track-distance", `-${distance}px`);
    copyButton.style.setProperty(
      "--player-track-duration",
      `${Math.max(8, Math.round(distance / 22) + 5)}s`,
    );
    copyButton.dataset.overflow = "true";
  }

  function scheduleTrackOverflowRefresh() {
    if (overflowFrameId) {
      cancelFrame(overflowFrameId);
    }
    overflowFrameId = requestFrame(refreshTrackOverflow);
  }

  function setCopyTrack(text) {
    currentTrackText = cleanText(text);
    if (!copyButton) return;

    copyButton.disabled = !currentTrackText;
    const label = currentTrackText
      ? `Copy current track: ${currentTrackText}`
      : "Current track information unavailable";
    copyButton.setAttribute("aria-label", label);
    copyButton.setAttribute("title", label);
    scheduleTrackOverflowRefresh();
  }

  async function copyCurrentTrack() {
    if (!currentTrackText) return;

    try {
      await copyTextToClipboard(currentTrackText, { navigatorRef, documentRef });
      showCopyFeedback("Track copied to clipboard.");
      logPlayerEvent("metadata-track-copied");
    } catch (error) {
      showCopyFeedback("Could not copy track information.");
      logPlayerEvent("metadata-track-copy-failed", {
        error: String(error),
      });
    }
  }

  copyButton?.addEventListener("click", () => {
    void copyCurrentTrack();
  });
  windowRef.addEventListener?.("resize", scheduleTrackOverflowRefresh);

  if (copyButton && typeof windowRef.ResizeObserver === "function") {
    const observer = new windowRef.ResizeObserver(scheduleTrackOverflowRefresh);
    observer.observe(copyButton);
  }

  function clearTimer() {
    if (!timeoutId) return;
    windowRef.clearTimeout(timeoutId);
    timeoutId = 0;
  }

  function renderFallback({ notify = false } = {}) {
    if (notify) {
      onMetadataChange(null, fallbackTitle, streamUrl);
    }

    if (stationNode) {
      stationNode.textContent = fallbackTitle;
      stationNode.hidden = !fallbackTitle;
    }
    if (titleNode) {
      titleNode.textContent = fallbackTitle ? "Waiting for track info…" : "Nothing playing yet";
    }
    setCopyTrack("");
  }

  function renderMetadata(metadata) {
    const displayTitle = metadataDisplayTitle(metadata, fallbackTitle);
    onMetadataChange(metadata, fallbackTitle, streamUrl);

    if (stationNode) {
      stationNode.textContent = fallbackTitle;
      stationNode.hidden = !fallbackTitle;
    }
    if (titleNode) {
      titleNode.textContent = displayTitle;
    }
    setCopyTrack(displayTitle);
  }

  function scheduleNext(generation) {
    if (!playbackActive || !streamUrl || generation !== requestGeneration) return;
    clearTimer();

    timeoutId = windowRef.setTimeout(() => {
      timeoutId = 0;
      void poll(generation);
    }, pollIntervalMs);
  }

  async function poll(generation) {
    if (
      !playbackActive ||
      !streamUrl ||
      generation !== requestGeneration ||
      requestInFlight
    ) {
      return;
    }

    requestInFlight = true;
    const requestedUrl = streamUrl;

    try {
      const response = await apiFetch(
        `/api/metadata?url=${encodeURIComponent(requestedUrl)}`,
        { cache: "no-store" },
      );

      if (
        generation !== requestGeneration ||
        !playbackActive ||
        requestedUrl !== streamUrl
      ) {
        return;
      }

      if (!response.ok) {
        logPlayerEvent("metadata-response-error", {
          status: response.status,
        });
        return;
      }

      const payload = await response.json();
      if (
        generation !== requestGeneration ||
        !playbackActive ||
        requestedUrl !== streamUrl
      ) {
        return;
      }

      if (payload?.status === "fresh" && payload.metadata) {
        renderMetadata(payload.metadata);
        logPlayerEvent("metadata-updated", {
          status: payload.status,
        });
      } else {
        logPlayerEvent("metadata-cache-state", {
          status: payload?.status || "unknown",
        });
      }
    } catch (error) {
      if (generation === requestGeneration && playbackActive) {
        logPlayerEvent("metadata-request-failed", {
          error: String(error),
        });
      }
    } finally {
      requestInFlight = false;
      scheduleNext(requestGeneration);
    }
  }

  function setStation(url, title) {
    const normalizedUrl = cleanText(url);
    const normalizedTitle = cleanText(title) || normalizedUrl || "Unknown station";
    const changed = normalizedUrl !== streamUrl;

    streamUrl = normalizedUrl;
    fallbackTitle = normalizedTitle;

    if (changed) {
      requestGeneration += 1;
      clearTimer();
    }

    renderFallback({ notify: changed });
  }

  function updatePlaybackState(state, station = {}) {
    const nextUrl = cleanText(station.url);
    const nextTitle = cleanText(station.title);

    if (nextUrl && (nextUrl !== streamUrl || nextTitle !== fallbackTitle)) {
      setStation(nextUrl, nextTitle);
    }

    if (state !== "playing" || !streamUrl) {
      playbackActive = false;
      requestGeneration += 1;
      clearTimer();
      return;
    }

    playbackActive = true;
    requestGeneration += 1;
    clearTimer();

    if (requestInFlight) {
      scheduleNext(requestGeneration);
    } else {
      void poll(requestGeneration);
    }
  }

  function clear() {
    playbackActive = false;
    requestGeneration += 1;
    clearTimer();
    streamUrl = "";
    fallbackTitle = "";
    renderFallback({ notify: true });
  }

  return {
    clear,
    setStation,
    updatePlaybackState,
  };
}
