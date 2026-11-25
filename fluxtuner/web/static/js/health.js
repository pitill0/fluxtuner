/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createHealthController({ presentation, fetch, statusNode, healthStateNode, healthSummaryNode }) {
  function healthDetails(payload) {
    const version = payload.version ? ` · ${payload.version}` : "";
    const database = payload.database || payload.db || payload.storage || "";
    const databaseText = database ? ` · ${database}` : "";

    const details = `${version}${databaseText}`.trim();

    return details ? `${details} · ` : "";
  }

  function formatHealthSummary(payload) {
    const status = payload.status || payload.state || "ok";
    return { state: String(status).toUpperCase(), summary: `${healthDetails(payload)}checked now` };
  }

  function show(node, value, key, params = {}) {
    if (!node) return;
    presentation?.clear(node);
    if (presentation && key) presentation.present(node, key, value, "textContent", params);
    else node.textContent = value;
  }

  function setHealthSummary(state, summary) {
    if (healthStateNode) {
      show(healthStateNode, state);
    }

    if (healthSummaryNode) {
      show(healthSummaryNode, summary);
    }
  }

  async function checkHealth() {
    if (statusNode) {
      show(statusNode, "Checking server...", "health.check_server");
    }

    show(healthStateNode, "Checking", "health.checking");
    show(healthSummaryNode, "Refreshing server status...", "health.refresh");

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
      show(healthSummaryNode, summary.summary, "health.checked", {
        details: healthDetails(payload),
      });

      if (statusNode) {
        show(statusNode, JSON.stringify(payload, null, 2));
      }
    } catch (error) {
      show(healthStateNode, "Error", "health.error");
      show(healthSummaryNode, `Server check failed: ${error}`, "health.failed", { error: String(error) });

      if (statusNode) {
        show(statusNode, `Server check failed: ${error}`, "health.failed", { error: String(error) });
      }
    }
  }

  return {
    checkHealth,
    formatHealthSummary,
    setHealthSummary,
  };
}
