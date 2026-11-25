/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createFavoriteController({
  apiFetch,
  stationUrl,
  setPlayerState,
  isAuthenticated,
  getCurrentView,
  loadFavorites,
}) {
  let recordedHistoryUrl = "";

  function resetRecordedHistory() {
    recordedHistoryUrl = "";
  }

  async function recordHistory(station) {
    const url = stationUrl(station);
    if (!isAuthenticated() || !url || recordedHistoryUrl === url) return;

    recordedHistoryUrl = url;

    try {
      const response = await apiFetch("/api/history", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(station),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (_error) {
      // Playback history is best-effort. Keep production consoles quiet if it fails.
    }
  }

  async function addFavorite(station) {
    const url = stationUrl(station);
    if (!url) {
      setPlayerState("error", "This station has no URL to save as favorite.", undefined, "favorite.no_save_url");
      return;
    }

    try {
      const response = await apiFetch("/api/favorites", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(station),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.added ? "Saved to favorites." : "Station is already in favorites.",
        undefined, payload.added ? "favorite.saved" : "favorite.exists",
      );
    } catch (error) {
      setPlayerState("error", `Could not save favorite. ${error}`, undefined, "favorite.save_failed", { error: String(error) });
    }
  }

  async function removeFavorite(station) {
    const url = stationUrl(station);
    if (!url) {
      setPlayerState("error", "This station has no URL to remove.", undefined, "favorite.no_remove_url");
      return;
    }

    try {
      const response = await apiFetch(`/api/favorites?url=${encodeURIComponent(url)}`, {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.removed ? "Removed from favorites." : "Station was not in favorites.",
        undefined, payload.removed ? "favorite.removed" : "favorite.absent",
      );

      if (getCurrentView() === "favorites") {
        await loadFavorites();
      }
    } catch (error) {
      setPlayerState("error", `Could not remove favorite. ${error}`, undefined, "favorite.remove_failed", { error: String(error) });
    }
  }

  return {
    addFavorite,
    recordHistory,
    removeFavorite,
    resetRecordedHistory,
  };
}
