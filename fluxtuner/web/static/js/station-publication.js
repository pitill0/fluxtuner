/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

/** Update an owned favorite without optimistic publication state changes. */
export function createStationPublicationController({
  presentation, apiFetch, getCurrentUser, getSessionKey, getCurrentView, loadFavorites, setMessage,
}) {
  async function toggle(station, button) {
    const id = Number(station?.station_id);
    const owner = getCurrentUser();
    const session = getSessionKey();
    if (!owner || !Number.isSafeInteger(id) || id < 1 || button.disabled) return;

    const published = !Boolean(station.published);
    if (published && !station.publication_eligible) return;

    if (published) {
      const warning = "Make this station public?\n\nOther users may discover it through public station lists and activity rankings. Its name, associated public metadata and shareable stream URL may become accessible to others.\n\nYou can make it private again, but copies already saved by other people cannot be recalled.";
      const confirmed = window.confirm(
        presentation?.translate("station.confirm_public", warning) ?? warning
      );
      if (!confirmed) return;
    }

    button.disabled = true;
    try {
      const response = await apiFetch(`/api/stations/${id}/publication`, {
        method: "PUT",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ published }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (owner.id !== getCurrentUser()?.id || session !== getSessionKey()) return;
      if (getCurrentView() === "favorites") await loadFavorites();
      setMessage("idle", published ? "Station made public." : "Station made private.", undefined, published ? "publication.public" : "publication.private");
    } catch (_error) {
      if (owner.id === getCurrentUser()?.id && session === getSessionKey()) {
        setMessage("error", "Could not update station visibility. Please try again.", undefined, "publication.failed");
      }
    } finally {
      if (button.isConnected && owner.id === getCurrentUser()?.id &&
          session === getSessionKey()) button.disabled = false;
    }
  }

  return { toggle };
}
