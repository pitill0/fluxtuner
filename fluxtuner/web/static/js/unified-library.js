/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

/**
 * Profile-scoped library views using the existing results surface.
 * Does not own navigation, playback, or authentication state.
 */
export function createUnifiedLibraryController({
  presentation,
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

  function begin(view, kicker, title, loadingText, kickerKey, titleKey, loadingKey, titleParams = {}) {
    const generationAtStart = ++generation;
    const user = getCurrentUser();

    setLibraryView(view);
    setResultsHeader(kicker, title, kickerKey, titleKey, titleParams);
    resultCountNode.textContent = loadingText;
    presentation?.present(resultCountNode, loadingKey, loadingText);
    resultsNode.replaceChildren();

    const loading = resultsNode.ownerDocument.createElement("p");
    loading.className = "empty";
    loading.textContent = loadingText;
    presentation?.present(loading, loadingKey, loadingText);
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
      "shell.library", "nav.stations", "unified.loading_stations",
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
    presentation?.present(resultCountNode, "unified.count", resultCountNode.textContent, "textContent", { count: catalogs.length });

    const cards = catalogs.map((catalog) => {
      const id = Number(catalog.source_id);
      if (!Number.isSafeInteger(id) || id <= 0) return "";

      const name = String(catalog.label || `Catalog #${id}`);
      const escapedName = name.replaceAll("&", "&amp;").replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
      return `
        <article class="station-card">
          <header>
            <h3${catalog.label ? "" : ` data-catalog-fallback="${id}"`}>${escapedName}</h3>
            <div class="station-meta">
              <span data-catalog-meta="${id}" data-revision="${Number(catalog.revision) || 1}">Catalog #${id} · Revision ${Number(catalog.revision) || 1}</span>
            </div>
          </header>
          <div class="station-actions">
            <button type="button" data-open-catalog="${id}" data-render-i18n="unified.browse">
              Browse stations
            </button>
          </div>
        </article>
      `;
    }).join("");

    resultsNode.innerHTML = `
      <div class="station-actions">
        <button type="button" data-manage-catalogs data-render-i18n="unified.manage">
          Manage subscriptions
        </button>
      </div>
      ${cards || '<p class="empty" data-render-i18n="subscriptions.empty">No remote catalogs subscribed.</p>'}
    `;

    presentation?.bindRendered(resultsNode);
    if (presentation) {
      for (const node of resultsNode.querySelectorAll("[data-catalog-meta]")) {
        presentation.present(node, "subscriptions.revision", node.textContent, "textContent", { id: Number(node.dataset.catalogMeta), revision: Number(node.dataset.revision) });
      }
      for (const node of resultsNode.querySelectorAll("[data-catalog-fallback]")) {
        presentation.present(node, "subscriptions.catalog", node.textContent, "textContent", { id: Number(node.dataset.catalogFallback) });
      }
    }
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
      "shell.library", "nav.catalogs", "unified.loading_catalogs",
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
      "shell.remote", "subscriptions.catalog", "unified.loading_catalog", { id },
    );

    try {
      const payload = await fetchJson(
        `/api/stations/subscriptions/${id}/stations`,
      );
      if (current()) {
        setResultsHeader(
          "Remote catalog",
          `${String(payload.label || `Catalog #${id}`)} · Catalog #${id}`,
          "shell.remote", payload.label ? "unified.named_catalog" : "subscriptions.catalog", { name: String(payload.label || ""), id },
        );
        renderResults(payload);
      }
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
