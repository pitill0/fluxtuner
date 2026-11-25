/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "./stations.js";

function renderDashboardMetric(label, value, key) {
  return `
    <article class="dashboard-metric">
      <span data-render-i18n="${key}">${escapeHtml(label)}</span>
      <strong${typeof value === "number" ? ` data-render-number="${value}"` : ""}>${escapeHtml(value)}</strong>
    </article>
  `;
}

export function createDashboardController({
  presentation,
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
  getCurrentUser,
  isDashboardVisible,
}) {
  let generation = 0;
  function setDashboardMessage(message, key) {
    if (messageNode) {
      presentation?.clear(messageNode);
      if (presentation && key) presentation.present(messageNode, key, message);
      else messageNode.textContent = message || "";
    }
  }

  function renderDashboardStations(node, stations, emptyMessage, key) {
    if (!node) return;

    if (!stations.length) {
      node.innerHTML = `<p class="empty" data-render-i18n="${key}">${escapeHtml(emptyMessage)}</p>`;
      presentation?.bindRendered(node);
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
        renderDashboardMetric("Favorites", Number(userMetrics.favorites_count || 0), "nav.favorites"),
        renderDashboardMetric("Playlists", Number(userMetrics.playlists_count || 0), "nav.playlists"),
        renderDashboardMetric(
          "Playlist stations",
          Number(userMetrics.playlist_stations_count || 0), "dashboard.playlist_stations",
        ),
        renderDashboardMetric("History", Number(userMetrics.history_count || 0), "nav.history"),
      ].join("");
      presentation?.bindRendered(userMetricsNode);
    }

    renderDashboardStations(
      recentHistoryNode,
      userMetrics.recent_history || [],
      "No recent playback yet.", "dashboard.no_recent",
    );
    renderDashboardStations(
      favoriteHighlightsNode,
      userMetrics.favorite_highlights || [],
      "No favorites yet.", "dashboard.no_favorites",
    );

    if (adminPanelNode) {
      adminPanelNode.hidden = !adminMetrics;
    }

    if (adminActionButton) {
      adminActionButton.hidden = !adminMetrics;
    }

    if (adminMetricsNode && adminMetrics) {
      adminMetricsNode.innerHTML = [
        renderDashboardMetric("Users", Number(adminMetrics.users_count || 0), "dashboard.users"),
        renderDashboardMetric("New today", Number(adminMetrics.users_created_today || 0), "dashboard.new_today"),
        renderDashboardMetric("New 7 days", Number(adminMetrics.users_created_7_days || 0), "dashboard.new_7"),
        renderDashboardMetric("New 30 days", Number(adminMetrics.users_created_30_days || 0), "dashboard.new_30"),
        renderDashboardMetric("Pending approval", Number(adminMetrics.pending_users_count || 0), "dashboard.pending"),
        renderDashboardMetric("Server", String(adminMetrics.server?.status || "unknown"), "dashboard.server"),
      ].join("");
      presentation?.bindRendered(adminMetricsNode);
    }
  }

  async function loadDashboard(options = {}) {
    if (!isAuthenticated() || !panelNode) return;

    const preserveView = Boolean(options.preserveView);
    const silent = Boolean(options.silent);
    const requestGeneration = ++generation;
    const requestUser = getCurrentUser();
    const stillCurrent = () =>
      requestGeneration === generation &&
      isAuthenticated() &&
      getCurrentUser() === requestUser &&
      (preserveView || isDashboardVisible());

    if (!preserveView) {
      setCurrentView("dashboard");
      setCurrentPlaylistName("");
      showDashboardView();
    }

    if (!silent) {
      setDashboardMessage("Loading dashboard...", "dashboard.loading");
    }

    try {
      const response = await apiFetch("/api/dashboard", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!stillCurrent()) return;

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        if (!stillCurrent()) return;
        throw new Error(payload.detail || "Could not load dashboard.");
      }

      const payload = await response.json();
      if (!stillCurrent()) return;
      renderDashboard(payload);
      if (!silent) {
        setDashboardMessage("Dashboard updated.", "dashboard.updated");
      }
    } catch (error) {
      if (stillCurrent()) {
        const message = String(error);
        setDashboardMessage(message, message === "Error: Could not load dashboard." ? "dashboard.load_error" : undefined);
      }
    }
  }

  return {
    loadDashboard,
    renderDashboard,
    setDashboardMessage,
  };
}
