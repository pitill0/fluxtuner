/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

/**
 * Profile-scoped library views using the existing results surface.
 * Does not own navigation, playback, or authentication state.
 */
export function createUnifiedLibraryController({
  apiFetch,
  getCurrentUser,
  getCurrentView,
  isLibraryVisible,
  setLibraryView,
  setResultsHeader,
  resultsNode,
  resultCountNode,
  renderResults,
  renderSearchError,
  onOpenCatalog,
  onManageCatalogs,
}) {
  let generation = 0;

  function invalidate() {
    generation += 1;
  }

  function begin(view, kicker, title, loadingText) {
    const generationAtStart = ++generation;
    const user = getCurrentUser();

    setLibraryView(view);
    setResultsHeader(kicker, title);
    resultCountNode.textContent = loadingText;
    resultsNode.replaceChildren();

    const loading = resultsNode.ownerDocument.createElement("p");
    loading.className = "empty";
    loading.textContent = loadingText;
    resultsNode.append(loading);

    return () =>
      generation === generationAtStart &&
      getCurrentUser() === user &&
      Boolean(user) &&
      getCurrentView() === view &&
      isLibraryVisible();
  }

  async function fetchJson(path) {
    const response = await apiFetch(path, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async function loadMyStations() {
    const current = begin(
      "stations", "Library", "My stations", "Loading my stations...",
    );

    try {
      const payload = await fetchJson("/api/stations/custom");
      if (current()) renderResults(payload);
    } catch (error) {
      if (current()) renderSearchError(error);
    }
  }

  function renderCatalogs(payload) {
    const catalogs = payload.subscriptions || [];

    resultCountNode.textContent =
      `${catalogs.length} catalog${catalogs.length === 1 ? "" : "s"}`;

    const cards = catalogs.map((catalog) => {
      const id = Number(catalog.source_id);
      if (!Number.isSafeInteger(id) || id <= 0) return "";

      return `
        <article class="station-card">
          <header>
            <h3>Catalog #${id}</h3>
            <div class="station-meta">
              <span>Revision ${Number(catalog.revision) || 1}</span>
            </div>
          </header>
          <div class="station-actions">
            <button type="button" data-open-catalog="${id}">
              Browse stations
            </button>
          </div>
        </article>
      `;
    }).join("");

    resultsNode.innerHTML = `
      <div class="station-actions">
        <button type="button" data-manage-catalogs>
          Manage subscriptions
        </button>
      </div>
      ${cards || '<p class="empty">No remote catalogs subscribed.</p>'}
    `;

    resultsNode.querySelector("[data-manage-catalogs]")
      ?.addEventListener("click", () => onManageCatalogs());

    resultsNode.querySelectorAll("[data-open-catalog]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          const id = Number(button.getAttribute("data-open-catalog"));
          if (Number.isSafeInteger(id) && id > 0) {
            onOpenCatalog(id);
          }
        });
      });
  }

  async function loadCatalogs() {
    const current = begin(
      "catalogs", "Library", "Remote catalogs", "Loading catalogs...",
    );

    try {
      const payload = await fetchJson("/api/stations/subscriptions");
      if (current()) renderCatalogs(payload);
    } catch (error) {
      if (current()) renderSearchError(error);
    }
  }

  async function loadCatalogStations(sourceId) {
    const id = Number(sourceId);
    if (!Number.isSafeInteger(id) || id <= 0) {
      throw new Error("Invalid catalog identifier.");
    }

    const current = begin(
      "catalog",
      "Remote catalog",
      `Catalog #${id}`,
      "Loading catalog stations...",
    );

    try {
      const payload = await fetchJson(
        `/api/stations/subscriptions/${id}/stations`,
      );
      if (current()) renderResults(payload);
    } catch (error) {
      if (current()) renderSearchError(error);
    }
  }

  return {
    invalidate,
    loadMyStations,
    loadCatalogs,
    loadCatalogStations,
  };
}
