/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const PLAYER_DEBUG_EVENT_LIMIT = 80;
const PLAYER_DEBUG_STORAGE_KEY = "fluxtunerPlayerDebug";
const PLAYER_DEBUG_QUERY_KEY = "player_debug";

export function createPlayerDebugController({
  panel,
  summaryNode,
  enableInput,
  toggleButton,
  copyButton,
  clearButton,
  downloadButton,
  detailsNode,
  snapshotNode,
  logNode,
  exportNode,
  getSnapshot,
  isVisible,
}) {
  let enabled = false;
  let events = [];

  function payload() {
    const lines = [
      "FluxTuner player debug log",
      "",
      "Current snapshot:",
      JSON.stringify(getSnapshot(), null, 2),
      "",
      "Recent events:",
    ];

    for (const entry of events) {
      lines.push(`[${entry.timestamp}] ${entry.eventName}`);
      lines.push(JSON.stringify(entry.snapshot, null, 2));
    }

    return lines.join("\n");
  }

  function render() {
    if (!panel) return;

    if (enableInput) {
      enableInput.checked = enabled;
    }

    if (summaryNode) {
      const count = events.length;
      summaryNode.textContent = enabled
        ? count
          ? `${count} recent player event${count === 1 ? "" : "s"} captured.`
          : "Debug logging is enabled."
        : "Debug logging is disabled.";
    }

    if (!enabled) {
      if (snapshotNode) {
        snapshotNode.textContent = "Enable player debug to capture playback diagnostics.";
      }

      if (logNode) {
        logNode.textContent = "No player events captured while debug is disabled.";
      }

      return;
    }

    if (snapshotNode) {
      snapshotNode.textContent = JSON.stringify(getSnapshot(), null, 2);
    }

    if (logNode) {
      logNode.textContent = events.length
        ? events
            .map(
              (entry) =>
                `[${entry.timestamp}] ${entry.eventName}\n${JSON.stringify(entry.snapshot, null, 2)}`,
            )
            .join("\n\n")
        : "No player events yet.";
    }
  }

  function setSummary(message) {
    if (summaryNode) {
      summaryNode.textContent = message;
    }
  }

  function showExport(data) {
    if (!exportNode) return;

    exportNode.value = data;
    exportNode.hidden = false;
    exportNode.focus();
    exportNode.select();
  }

  function applyState(nextEnabled, persist = true) {
    enabled = Boolean(nextEnabled);

    try {
      if (persist) {
        if (enabled) {
          window.localStorage.setItem(PLAYER_DEBUG_STORAGE_KEY, "1");
        } else {
          window.localStorage.removeItem(PLAYER_DEBUG_STORAGE_KEY);
        }
      }
    } catch (_error) {
      // localStorage may be unavailable in private browsing or restricted contexts.
    }

    if (enableInput) {
      enableInput.checked = enabled;
    }

    if (!enabled && detailsNode) {
      detailsNode.open = false;
    }

    if (toggleButton) {
      toggleButton.textContent = detailsNode?.open && enabled ? "Hide" : "Show";
      toggleButton.disabled = !enabled;
    }

    if (copyButton) {
      copyButton.disabled = !enabled;
    }

    if (downloadButton) {
      downloadButton.disabled = !enabled;
    }

    if (clearButton) {
      clearButton.disabled = !enabled;
    }

    if (exportNode && !enabled) {
      exportNode.value = "";
      exportNode.hidden = true;
    }

    render();
  }

  function updateVisibility() {
    if (!panel) return;

    const showAdminDebug = Boolean(isVisible?.());
    panel.hidden = !showAdminDebug;

    if (showAdminDebug) {
      render();
    }
  }

  function initialize() {
    let initialEnabled = false;

    try {
      const params = new URLSearchParams(window.location.search);
      const requestedDebug = params.get(PLAYER_DEBUG_QUERY_KEY);

      if (requestedDebug === "1") {
        initialEnabled = true;
      } else if (requestedDebug === "0") {
        initialEnabled = false;
      } else {
        initialEnabled = window.localStorage.getItem(PLAYER_DEBUG_STORAGE_KEY) === "1";
      }

      applyState(initialEnabled, requestedDebug !== null);
    } catch (_error) {
      enabled = false;
      applyState(false, false);
    }

    if (enabled) {
      console.info("[FluxTuner player]", "debug enabled", {
        disableWith: `?${PLAYER_DEBUG_QUERY_KEY}=0`,
        adminToggle: "Admin > Player debug",
      });
    }
  }

  function copyLog() {
    if (!enabled) return;

    const data = payload();
    showExport(data);

    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }

      void navigator.clipboard.writeText(data).then(
        () => setSummary("Player debug log copied to clipboard and shown below."),
        () =>
          setSummary(
            "Clipboard unavailable. Select and copy the log below, or use Download log.",
          ),
      );
    } catch (_error) {
      setSummary("Clipboard unavailable. Select and copy the log below, or use Download log.");
    }
  }

  function downloadLog() {
    if (!enabled) return;

    const data = payload();
    showExport(data);

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `fluxtuner-player-debug-${timestamp}.txt`;
    const blob = new Blob([data], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);

    setSummary(`Player debug log download started: ${filename}`);
  }

  function clearLog() {
    events = [];

    if (exportNode) {
      exportNode.value = "";
      exportNode.hidden = true;
    }

    render();
  }

  function toggleDetails() {
    if (!detailsNode) return;

    detailsNode.open = !detailsNode.open;

    if (toggleButton) {
      toggleButton.textContent = detailsNode.open ? "Hide" : "Show";
    }

    render();
  }

  function logEvent(eventName, details = {}) {
    if (!enabled) return;

    const entry = {
      timestamp: new Date().toISOString(),
      eventName,
      snapshot: getSnapshot(details),
    };

    events.push(entry);
    if (events.length > PLAYER_DEBUG_EVENT_LIMIT) {
      events = events.slice(-PLAYER_DEBUG_EVENT_LIMIT);
    }

    console.debug("[FluxTuner player]", eventName, entry.snapshot);
    render();
  }

  return {
    applyState,
    updateVisibility,
    initialize,
    copyLog,
    downloadLog,
    clearLog,
    toggleDetails,
    logEvent,
    get enabled() {
      return enabled;
    },
  };
}
