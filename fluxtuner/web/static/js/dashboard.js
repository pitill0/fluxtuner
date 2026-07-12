/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

function renderDashboardMetric(label, value) {
  return `
    <article class="dashboard-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

export function createDashboardController({
  apiFetch,
  panelNode,
  messageNode,
  userMetricsNode,
  recentHistoryNode,
  favoriteHighlightsNode,
  adminPanelNode,
  adminMetricsNode,
  adminActionButton,
  renderStation,
  bindResultActions,
  showDashboardView,
  isAuthenticated,
  setCurrentView,
  setCurrentPlaylistName,
}) {
  function setDashboardMessage(message) {
    if (messageNode) {
      messageNode.textContent = message || "";
    }
  }

  function renderDashboardStations(node, stations, emptyMessage) {
    if (!node) return;

    if (!stations.length) {
      node.innerHTML = `<p class="empty">${escapeHtml(emptyMessage)}</p>`;
      return;
    }

    node.innerHTML = stations.map(renderStation).join("");
    bindResultActions();
  }

  function renderDashboard(payload) {
    const userMetrics = payload.user || {};
    const adminMetrics = payload.admin || null;

    if (userMetricsNode) {
      userMetricsNode.innerHTML = [
        renderDashboardMetric("Favorites", Number(userMetrics.favorites_count || 0)),
        renderDashboardMetric("Playlists", Number(userMetrics.playlists_count || 0)),
        renderDashboardMetric(
          "Playlist stations",
          Number(userMetrics.playlist_stations_count || 0),
        ),
        renderDashboardMetric("History", Number(userMetrics.history_count || 0)),
      ].join("");
    }

    renderDashboardStations(
      recentHistoryNode,
      userMetrics.recent_history || [],
      "No recent playback yet.",
    );
    renderDashboardStations(
      favoriteHighlightsNode,
      userMetrics.favorite_highlights || [],
      "No favorites yet.",
    );

    if (adminPanelNode) {
      adminPanelNode.hidden = !adminMetrics;
    }

    if (adminActionButton) {
      adminActionButton.hidden = !adminMetrics;
    }

    if (adminMetricsNode && adminMetrics) {
      adminMetricsNode.innerHTML = [
        renderDashboardMetric("Users", Number(adminMetrics.users_count || 0)),
        renderDashboardMetric("New today", Number(adminMetrics.users_created_today || 0)),
        renderDashboardMetric("New 7 days", Number(adminMetrics.users_created_7_days || 0)),
        renderDashboardMetric("New 30 days", Number(adminMetrics.users_created_30_days || 0)),
        renderDashboardMetric("Pending approval", Number(adminMetrics.pending_users_count || 0)),
        renderDashboardMetric(
          "Password changes",
          Number(adminMetrics.pending_password_change_requests_count || 0),
        ),
        renderDashboardMetric("Server", String(adminMetrics.server?.status || "unknown")),
      ].join("");
    }
  }

  async function loadDashboard(options = {}) {
    if (!isAuthenticated() || !panelNode) return;

    const preserveView = Boolean(options.preserveView);
    const silent = Boolean(options.silent);

    if (!preserveView) {
      setCurrentView("dashboard");
      setCurrentPlaylistName("");
      showDashboardView();
    }

    if (!silent) {
      setDashboardMessage("Loading dashboard...");
    }

    try {
      const response = await apiFetch("/api/dashboard", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not load dashboard.");
      }

      const payload = await response.json();
      renderDashboard(payload);
      if (!silent) {
        setDashboardMessage("Dashboard updated.");
      }
    } catch (error) {
      setDashboardMessage(String(error));
    }
  }

  return {
    loadDashboard,
    renderDashboard,
    setDashboardMessage,
  };
}
