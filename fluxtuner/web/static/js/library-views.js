/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

function setLoadingState({ resultsNode, resultCountNode, countText, emptyText }) {
  if (resultCountNode) {
    resultCountNode.textContent = countText;
  }

  if (resultsNode) {
    resultsNode.innerHTML = `<p class="empty">${emptyText}</p>`;
  }
}

export function createLibraryViewsController({
  apiFetch,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderResults,
  renderPlaylists,
  renderSearchError,
  setLibraryView,
}) {
  function ensureResultsContainer() {
    return Boolean(resultsNode && resultCountNode);
  }

  async function loadHistory() {
    if (!ensureResultsContainer()) return;

    setLibraryView("history", "");
    setResultsHeader("Playback", "History");
    setLoadingState({
      resultsNode,
      resultCountNode,
      countText: "Loading history...",
      emptyText: "Loading playback history...",
    });

    try {
      const response = await apiFetch("/api/history?limit=25", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      renderResults(payload);
    } catch (error) {
      renderSearchError(error);
    }
  }

  async function loadFavorites() {
    if (!ensureResultsContainer()) return;

    setLibraryView("favorites", "");
    setResultsHeader("Library", "Favorites");
    setLoadingState({
      resultsNode,
      resultCountNode,
      countText: "Loading favorites...",
      emptyText: "Loading favorites...",
    });

    try {
      const response = await apiFetch("/api/favorites", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      renderResults(payload);
    } catch (error) {
      renderSearchError(error);
    }
  }

  async function loadPlaylists() {
    if (!ensureResultsContainer()) return;

    setLibraryView("playlists", "");
    setResultsHeader("Library", "Playlists");
    setLoadingState({
      resultsNode,
      resultCountNode,
      countText: "Loading playlists...",
      emptyText: "Loading playlists...",
    });

    try {
      const response = await apiFetch("/api/playlists", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      renderPlaylists(payload);
    } catch (error) {
      renderSearchError(error);
    }
  }

  async function loadPlaylistStations(name) {
    if (!ensureResultsContainer()) return;

    setLibraryView("playlist", name);
    setResultsHeader("Playlist", name);
    setLoadingState({
      resultsNode,
      resultCountNode,
      countText: "Loading playlist...",
      emptyText: "Loading playlist stations...",
    });

    try {
      const response = await apiFetch(
        `/api/playlists/${encodeURIComponent(name)}/stations`,
        {
          headers: {
            Accept: "application/json",
          },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      renderResults(payload);
    } catch (error) {
      renderSearchError(error);
    }
  }

  return {
    loadFavorites,
    loadHistory,
    loadPlaylistStations,
    loadPlaylists,
  };
}
