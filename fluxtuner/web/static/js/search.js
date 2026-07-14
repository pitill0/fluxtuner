/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

function renderSearchDebug(debug) {
  if (!debug) return "";

  const cacheState = debug.cache_bypassed ? "bypassed" : debug.cache_hit ? "hit" : "miss";
  const ranking = debug.ranking || {};
  const tiers = ranking.tiers || {};
  const selectedRanking = Array.isArray(ranking.selected) ? ranking.selected : [];
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
    ["ranking applied", ranking.applied ? "yes" : "no"],
    ["exact name", tiers.exact_name],
    ["name prefix", tiers.name_prefix],
    ["name contains", tiers.name_contains],
    ["tag contains", tiers.tag_contains],
    ["other rank", tiers.other],
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
      ${
        selectedRanking.length
          ? `<ol>${selectedRanking
              .map(
                (item) =>
                  `<li>${escapeHtml(String(item.name || "Unknown station"))}: tier ${escapeHtml(
                    String(item.tier ?? ""),
                  )} (${escapeHtml(String(item.reason || "other"))})</li>`,
              )
              .join("")}</ol>`
          : ""
      }
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
  let activeSearchController = null;
  let searchRequestId = 0;

  function renderResults(payload) {
    if (!resultsNode || !resultCountNode) return;

    const stations = payload.stations || [];
    const status = payload.status || "ok";
    const debugPanel = renderSearchDebug(payload.debug);

    if (status === "unavailable") {
      resultCountNode.textContent = "Search unavailable.";
      resultsNode.innerHTML = `${debugPanel}<p class="error">Radio Browser is temporarily unavailable. Please try again.</p>`;
      return;
    }

    resultCountNode.textContent = `${payload.count ?? stations.length} result${
      stations.length === 1 ? "" : "s"
    }`;

    const partialNotice =
      status === "partial"
        ? '<p class="empty">Some search sources were unavailable. Showing available results.</p>'
        : "";

    if (!stations.length) {
      const emptyMessage =
        status === "partial"
          ? "No stations found in the available search sources."
          : "No stations found.";
      resultsNode.innerHTML = `${debugPanel}${partialNotice}<p class="empty">${emptyMessage}</p>`;
      return;
    }

    resultsNode.innerHTML = `${debugPanel}${partialNotice}${stations
      .map(renderStation)
      .join("")}`;
    bindResultActions();
  }

  function renderSearchError(error) {
    if (!resultsNode || !resultCountNode) return;

    resultCountNode.textContent = "Search failed.";
    const message = error?.message || String(error);
    resultsNode.innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
  }

  async function searchStations(event) {
    event.preventDefault();

    if (!searchForm || !resultsNode || !resultCountNode) return;

    activeSearchController?.abort();
    const requestId = ++searchRequestId;
    const controller = new AbortController();
    activeSearchController = controller;

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
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (requestId !== searchRequestId) return;
      renderResults(payload);
    } catch (error) {
      if (error?.name === "AbortError" || requestId !== searchRequestId) return;
      renderSearchError(error);
    } finally {
      if (requestId === searchRequestId) {
        activeSearchController = null;
      }
    }
  }

  return {
    renderResults,
    renderSearchError,
    searchStations,
  };
}
