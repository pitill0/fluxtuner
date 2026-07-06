/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createHealthController({ fetch, statusNode, healthStateNode, healthSummaryNode }) {
  function formatHealthSummary(payload) {
    const status = payload.status || payload.state || "ok";
    const version = payload.version ? ` · ${payload.version}` : "";
    const database = payload.database || payload.db || payload.storage || "";
    const databaseText = database ? ` · ${database}` : "";

    const details = `${version}${databaseText}`.trim();

    return {
      state: String(status).toUpperCase(),
      summary: details ? `${details} · checked now` : "checked now",
    };
  }

  function setHealthSummary(state, summary) {
    if (healthStateNode) {
      healthStateNode.textContent = state;
    }

    if (healthSummaryNode) {
      healthSummaryNode.textContent = summary;
    }
  }

  async function checkHealth() {
    if (statusNode) {
      statusNode.textContent = "Checking server...";
    }

    setHealthSummary("Checking", "Refreshing server status...");

    try {
      const response = await fetch("/api/health", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      const summary = formatHealthSummary(payload);

      setHealthSummary(summary.state, summary.summary);

      if (statusNode) {
        statusNode.textContent = JSON.stringify(payload, null, 2);
      }
    } catch (error) {
      setHealthSummary("Error", `Server check failed: ${error}`);

      if (statusNode) {
        statusNode.textContent = `Server check failed: ${error}`;
      }
    }
  }

  return {
    checkHealth,
    formatHealthSummary,
    setHealthSummary,
  };
}
