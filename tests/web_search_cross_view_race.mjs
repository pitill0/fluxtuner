/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const modulePath = join(
  process.env.WORK,
  "fluxtuner/web/static/js/search.js",
);
const { createSearchController } = await import(
  pathToFileURL(modulePath).href,
);

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

const originalFetch = globalThis.fetch;
const originalFormData = globalThis.FormData;

function harness() {
  let view = "search";
  let visible = true;
  let user = { id: 1 };
  const listeners = new Set();
  const requests = [];
  const resultsNode = { innerHTML: "" };
  const resultCountNode = { textContent: "" };

  const searchForm = {
    querySelector: () => ({
      value: "radio-browser",
      addEventListener() {},
    }),
  };

  globalThis.FormData = class {
    get(name) {
      return name === "q" ? "jazz" : "";
    }
  };

  globalThis.fetch = (url, options) => {
    const pending = deferred();
    requests.push({ url, options, pending });
    return pending.promise;
  };

  const controller = createSearchController({
    searchForm,
    resultsNode,
    resultCountNode,
    setResultsHeader: () => {},
    renderStation: (station) => `<article>${station.name}</article>`,
    bindResultActions: () => {},
    setSearchView: () => { changeView("search"); },
    getCurrentView: () => view,
    getCurrentUser: () => user,
    isSearchVisible: () => visible,
    subscribeViewChange: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  });

  function changeView(value) {
    view = value;
    for (const listener of listeners) listener(value);
  }

  return {
    controller,
    requests,
    resultsNode,
    resultCountNode,
    changeView,
    setUser(value) { user = value; },
    setVisible(value) { visible = value; },
  };
}

const response = (name) => ({
  ok: true,
  json: async () => ({
    stations: [{ name }],
    count: 1,
  }),
});

async function runSearch(h) {
  return h.controller.searchStations({
    preventDefault() {},
  });
}

try {
  {
    const h = harness();
    const old = runSearch(h);
    assert.equal(h.requests.length, 1);

    h.changeView("favorites");
    assert.equal(h.requests[0].options.signal.aborted, true);

    h.resultsNode.innerHTML = "<p>Favorites result</p>";
    h.requests[0].pending.resolve(response("Stale Search"));
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>Favorites result</p>");
    console.log("PASS: Search cannot overwrite Favorites");
  }

  {
    const h = harness();
    const old = runSearch(h);

    h.changeView("playlists");
    h.changeView("search");
    h.resultsNode.innerHTML = "<p>New Search view</p>";

    h.requests[0].pending.resolve(response("Old Search"));
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>New Search view</p>");
    console.log("PASS: Search-Favorites-Search style race discarded");
  }

  {
    const h = harness();
    const old = runSearch(h);

    h.setUser({ id: 2 });
    h.resultsNode.innerHTML = "<p>New session</p>";
    h.requests[0].pending.resolve(response("Old user"));
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>New session</p>");
    console.log("PASS: changed session rejects response");
  }

  {
    const h = harness();
    const old = runSearch(h);

    h.setVisible(false);
    h.resultsNode.innerHTML = "<p>Other panel</p>";
    h.requests[0].pending.resolve(response("Hidden search"));
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>Other panel</p>");
    console.log("PASS: hidden Search rejects response");
  }

  {
    const h = harness();
    const old = runSearch(h);
    const json = deferred();

    h.requests[0].pending.resolve({
      ok: true,
      json: () => json.promise,
    });

    await Promise.resolve();
    await Promise.resolve();

    h.changeView("history");
    h.resultsNode.innerHTML = "<p>History view</p>";

    json.resolve({
      stations: [{ name: "Old JSON" }],
      count: 1,
    });
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>History view</p>");
    console.log("PASS: late JSON discarded");
  }

  {
    const h = harness();
    const old = runSearch(h);

    h.changeView("playlist");
    h.resultsNode.innerHTML = "<p>Playlist stations</p>";

    h.requests[0].pending.reject(new Error("Old failure"));
    await old;

    assert.equal(h.resultsNode.innerHTML, "<p>Playlist stations</p>");
    console.log("PASS: stale Search error discarded");
  }

  {
    const h = harness();
    const first = runSearch(h);
    const second = runSearch(h);

    h.requests[1].pending.resolve(response("Newer Search"));
    await second;

    h.requests[0].pending.resolve(response("Older Search"));
    await first;

    assert.match(h.resultsNode.innerHTML, /Newer Search/);
    assert.doesNotMatch(h.resultsNode.innerHTML, /Older Search/);
    console.log("PASS: latest Search request wins");
  }

  console.log("BEHAVIOR_GATE=PASS");
} finally {
  globalThis.fetch = originalFetch;
  globalThis.FormData = originalFormData;
}
