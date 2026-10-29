/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const directory = join(
  process.env.WORK,
  "fluxtuner/web/static/js",
);

async function load(name) {
  return import(pathToFileURL(join(directory, name)).href);
}

const { createAppState } = await load("app-state.js");
const { createSearchController } = await load("search.js");
const { createLibraryViewsController } = await load("library-views.js");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function response(name) {
  return {
    ok: true,
    json: async () => ({
      stations: [{ name }],
      count: 1,
    }),
  };
}

const originalFetch = globalThis.fetch;
const originalFormData = globalThis.FormData;

function harness() {
  const state = createAppState();
  state.setCurrentUser({ id: 1 });

  const resultsNode = { innerHTML: "" };
  const resultCountNode = { textContent: "" };
  const requests = [];

  let visible = true;
  const searchForm = {
    querySelector: () => ({
      value: "radio-browser",
      addEventListener() {},
    }),
  };

  globalThis.FormData = class {
    get(key) {
      return key === "q" ? "jazz" : "";
    }
  };

  globalThis.fetch = (url, options) => {
    const pending = deferred();
    requests.push({ kind: "search", url, options, pending });
    return pending.promise;
  };

  const setSearchView = () => {
    state.setCurrentSection("explore");
    state.setCurrentView("search");
    state.setCurrentPlaylistName("");
  };

  const search = createSearchController({
    searchForm,
    resultsNode,
    resultCountNode,
    setResultsHeader: () => {},
    renderStation: (station) => `<article>${station.name}</article>`,
    bindResultActions: () => {},
    setSearchView,
    getCurrentView: state.getCurrentView,
    getCurrentUser: state.getCurrentUser,
    isSearchVisible: () => visible,
    subscribeViewChange: state.subscribeViewChange,
  });

  const library = createLibraryViewsController({
    apiFetch: (url, options) => {
      const pending = deferred();
      requests.push({ kind: "library", url, options, pending });
      return pending.promise;
    },
    resultsNode,
    resultCountNode,
    setResultsHeader: () => {},
    renderResults: search.renderResults,
    renderPlaylists: (payload) => {
      resultsNode.innerHTML =
        `<article>Playlists ${payload.marker}</article>`;
    },
    renderSearchError: search.renderSearchError,
    setLibraryView: (view, name = "") => {
      state.setCurrentSection("explore");
      state.setCurrentView(view);
      state.setCurrentPlaylistName(name);
    },
    getCurrentView: state.getCurrentView,
    getCurrentUser: state.getCurrentUser,
    isLibraryVisible: () => visible,
  });

  return {
    state,
    search,
    library,
    requests,
    resultsNode,
    setVisible: (value) => { visible = value; },
  };
}

async function startSearch(h) {
  return h.search.searchStations({
    preventDefault() {},
  });
}

function latest(h) {
  return h.requests.at(-1);
}

try {
  {
    const h = harness();
    const searchPending = startSearch(h);
    const oldSearch = latest(h);

    const favoritesPending = h.library.loadFavorites();
    const favorites = latest(h);

    assert.equal(oldSearch.options.signal.aborted, true);
    assert.equal(h.state.getCurrentView(), "favorites");

    favorites.pending.resolve(response("Favorite Station"));
    await favoritesPending;

    oldSearch.pending.resolve(response("Old Search Station"));
    await searchPending;

    assert.match(h.resultsNode.innerHTML, /Favorite Station/);
    assert.doesNotMatch(h.resultsNode.innerHTML, /Old Search Station/);
    console.log("PASS: Search to Favorites");
  }

  {
    const h = harness();
    const libraryPending = h.library.loadHistory();
    const history = latest(h);

    const searchPending = startSearch(h);
    const search = latest(h);

    search.pending.resolve(response("Current Search Station"));
    await searchPending;

    history.pending.resolve(response("Old History Station"));
    await libraryPending;

    assert.equal(h.state.getCurrentView(), "search");
    assert.match(h.resultsNode.innerHTML, /Current Search Station/);
    assert.doesNotMatch(h.resultsNode.innerHTML, /Old History Station/);
    console.log("PASS: History to Search");
  }

  {
    const h = harness();
    const oldPending = h.library.loadPlaylists();
    const oldPlaylists = latest(h);

    const searchPending = startSearch(h);
    const search = latest(h);

    const newPending = h.library.loadPlaylists();
    const newPlaylists = latest(h);

    oldPlaylists.pending.resolve({
      ok: true,
      json: async () => ({ marker: "obsolete" }),
    });
    await oldPending;

    search.pending.resolve(response("Obsolete Search"));
    await searchPending;

    newPlaylists.pending.resolve({
      ok: true,
      json: async () => ({ marker: "latest" }),
    });
    await newPending;

    assert.match(h.resultsNode.innerHTML, /Playlists latest/);
    assert.doesNotMatch(h.resultsNode.innerHTML, /obsolete/i);
    console.log("PASS: Playlists to Search to Playlists");
  }

  {
    const h = harness();
    const oldPending = h.library.loadPlaylistStations("Jazz");
    const oldPlaylist = latest(h);

    const newPending = h.library.loadPlaylistStations("Rock");
    const newPlaylist = latest(h);

    newPlaylist.pending.resolve(response("Rock Station"));
    await newPending;

    oldPlaylist.pending.resolve(response("Jazz Station"));
    await oldPending;

    assert.equal(h.state.getCurrentPlaylistName(), "Rock");
    assert.match(h.resultsNode.innerHTML, /Rock Station/);
    assert.doesNotMatch(h.resultsNode.innerHTML, /Jazz Station/);
    console.log("PASS: playlist entity changes");
  }

  {
    const h = harness();
    const pending = startSearch(h);
    const request = latest(h);

    h.state.setCurrentUser(null);
    h.setVisible(false);
    h.resultsNode.innerHTML = "<p>Private content hidden</p>";

    request.pending.resolve(response("Private result"));
    await pending;

    assert.equal(
      h.resultsNode.innerHTML,
      "<p>Private content hidden</p>",
    );
    console.log("PASS: session loss invalidates Search");
  }

  console.log("BEHAVIOR_GATE=PASS");
} finally {
  globalThis.fetch = originalFetch;
  globalThis.FormData = originalFormData;
}
