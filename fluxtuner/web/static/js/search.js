/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

function renderSearchDebug(debug) {
  if (!debug) return "";

  const cacheState = debug.cache_bypassed ? "bypassed" : debug.cache_hit ? "hit" : "miss";
  const items = [
    ["cache", cacheState],
    ["name fetched", debug.name_results],
    ["tag fetched", debug.tag_results],
    ["name returned", debug.name_returned_results],
    ["tag returned", debug.tag_returned_results],
    ["raw", debug.raw_results],
    ["deduped", debug.deduped_results],
    ["country filtered", debug.country_filtered_results],
    ["bitrate filtered", debug.bitrate_filtered_results],
    ["returned", debug.returned_results],
    ["api limit", debug.api_limit],
  ];

  return `
    <details class="search-debug-panel">
      <summary>Search debug</summary>
      <dl>
        ${items
          .map(
            ([label, value]) => `
              <div>
                <dt>${escapeHtml(String(label))}</dt>
                <dd>${escapeHtml(String(value ?? 0))}</dd>
              </div>
            `,
          )
          .join("")}
      </dl>
    </details>
  `;
}

export function createSearchController({
  searchForm,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderStation,
  bindResultActions,
  setSearchView,
}) {
  function renderResults(payload) {
    if (!resultsNode || !resultCountNode) return;

    const stations = payload.stations || [];
    const debugPanel = renderSearchDebug(payload.debug);
    resultCountNode.textContent = `${payload.count ?? stations.length} result${
      stations.length === 1 ? "" : "s"
    }`;

    if (!stations.length) {
      resultsNode.innerHTML = `${debugPanel}<p class="empty">No stations found.</p>`;
      return;
    }

    resultsNode.innerHTML = `${debugPanel}${stations.map(renderStation).join("")}`;
    bindResultActions();
  }

  function renderSearchError(error) {
    if (!resultsNode || !resultCountNode) return;

    resultCountNode.textContent = "Search failed.";
    resultsNode.innerHTML = `<p class="error">${escapeHtml(error)}</p>`;
  }

  async function searchStations(event) {
    event.preventDefault();

    if (!searchForm || !resultsNode || !resultCountNode) return;

    const formData = new FormData(searchForm);
    const params = new URLSearchParams();

    params.set("q", String(formData.get("q") || "").trim());
    params.set("country", String(formData.get("country") || "").trim());
    const minBitrate = String(formData.get("min_bitrate") || "0").trim();
    params.set("min_bitrate", minBitrate || "0");
    params.set("limit", String(formData.get("limit") || "25"));
    if (formData.get("debug") === "1") {
      params.set("debug", "1");
    }

    const hasMinBitrateFilter = Number(params.get("min_bitrate") || "0") > 0;
    if (!params.get("q") && !params.get("country") && !hasMinBitrateFilter) {
      renderSearchError("Search text, country, or minimum bitrate is required.");
      return;
    }

    setSearchView();
    setResultsHeader("Radio Browser", "Search stations");
    resultCountNode.textContent = "Searching...";
    resultsNode.innerHTML = '<p class="empty">Searching Radio Browser...</p>';

    try {
      const response = await fetch(`/api/search?${params.toString()}`, {
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

  return {
    renderResults,
    renderSearchError,
    searchStations,
  };
}
