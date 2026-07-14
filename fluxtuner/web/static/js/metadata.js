/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const DEFAULT_POLL_INTERVAL_MS = 5000;

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

export function createMetadataController({
  apiFetch,
  titleNode,
  stationNode,
  onMetadataChange = () => {},
  logPlayerEvent = () => {},
  windowRef = window,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}) {
  let streamUrl = "";
  let fallbackTitle = "";
  let playbackActive = false;
  let timeoutId = 0;
  let requestGeneration = 0;
  let requestInFlight = false;

  function clearTimer() {
    if (!timeoutId) return;
    windowRef.clearTimeout(timeoutId);
    timeoutId = 0;
  }

  function renderFallback({ notify = false } = {}) {
    if (notify) {
      onMetadataChange(null, fallbackTitle, streamUrl);
    }

    if (titleNode) {
      titleNode.textContent = fallbackTitle || "Nothing playing yet";
    }
    if (stationNode) {
      stationNode.textContent = "";
      stationNode.hidden = true;
    }
  }

  function renderMetadata(metadata) {
    const displayTitle = metadataDisplayTitle(metadata, fallbackTitle);
    onMetadataChange(metadata, fallbackTitle, streamUrl);

    if (titleNode) {
      titleNode.textContent = displayTitle;
    }

    if (stationNode) {
      const showStation = Boolean(fallbackTitle && displayTitle !== fallbackTitle);
      stationNode.textContent = showStation ? fallbackTitle : "";
      stationNode.hidden = !showStation;
    }
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
