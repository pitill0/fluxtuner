/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(process.env.WORK, "fluxtuner/web/static/js/library-views.js"),
  "utf8",
);

const { createLibraryViewsController } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
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

function harness() {
  const requests = [];
  const rendered = [];
  let view = "search";
  let user = { id: 1 };
  let visible = true;

  const resultsNode = { innerHTML: "" };
  const resultCountNode = { textContent: "" };

  const controller = createLibraryViewsController({
    apiFetch: (url) => {
      const pending = deferred();
      requests.push({ url, pending });
      return pending.promise;
    },
    resultsNode,
    resultCountNode,
    setResultsHeader: () => {},
    renderResults: (payload) => {
      rendered.push(["results", payload]);
    },
    renderPlaylists: (payload) => {
      rendered.push(["playlists", payload]);
    },
    renderSearchError: (error) => {
      rendered.push(["error", String(error)]);
    },
    setLibraryView: (next) => {
      view = next;
    },
    getCurrentView: () => view,
    getCurrentUser: () => user,
    isLibraryVisible: () => visible,
  });

  return {
    controller,
    requests,
    rendered,
    setView: (next) => { view = next; },
    setUser: (next) => { user = next; },
    setVisible: (next) => { visible = next; },
  };
}

function response(payload) {
  return {
    ok: true,
    json: async () => payload,
  };
}

async function flush() {
  await Promise.resolve();
  await Promise.resolve();
}

{
  const h = harness();
  const first = h.controller.loadFavorites();
  const second = h.controller.loadPlaylists();

  assert.equal(h.requests.length, 2);
  assert.equal(h.requests[0].url, "/api/favorites");
  assert.equal(h.requests[1].url, "/api/playlists");

  h.requests[1].pending.resolve(response({ name: "new" }));
  await second;

  h.requests[0].pending.resolve(response({ name: "old" }));
  await first;

  assert.deepEqual(h.rendered, [
    ["playlists", { name: "new" }],
  ]);
  console.log("PASS: stale Favorites cannot overwrite Playlists");
}

{
  const h = harness();
  const first = h.controller.loadFavorites();
  const second = h.controller.loadFavorites();

  h.requests[1].pending.resolve(response({ revision: 2 }));
  await second;

  h.requests[0].pending.resolve(response({ revision: 1 }));
  await first;

  assert.deepEqual(h.rendered, [
    ["results", { revision: 2 }],
  ]);
  console.log("PASS: older request for same view discarded");
}

{
  const h = harness();
  const pending = h.controller.loadHistory();

  h.setUser({ id: 2 });
  h.requests[0].pending.resolve(response({ private: true }));
  await pending;

  assert.deepEqual(h.rendered, []);
  console.log("PASS: changed session discards old results");
}

{
  const h = harness();
  const pending = h.controller.loadFavorites();

  h.setVisible(false);
  h.requests[0].pending.resolve(response({ hidden: true }));
  await pending;

  assert.deepEqual(h.rendered, []);
  console.log("PASS: hidden library discards pending results");
}

{
  const h = harness();
  const pending = h.controller.loadFavorites();
  const json = deferred();

  h.requests[0].pending.resolve({
    ok: true,
    json: () => json.promise,
  });
  await flush();

  h.setView("history");
  json.resolve({ late: true });
  await pending;

  assert.deepEqual(h.rendered, []);
  console.log("PASS: stale JSON completion discarded");
}

{
  const h = harness();
  const pending = h.controller.loadFavorites();

  h.setView("dashboard");
  h.requests[0].pending.reject(new Error("stale failure"));
  await pending;

  assert.deepEqual(h.rendered, []);
  console.log("PASS: stale failures do not replace newer content");
}

console.log("BEHAVIOR_GATE=PASS");
