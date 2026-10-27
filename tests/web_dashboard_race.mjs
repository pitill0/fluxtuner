/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

let source = await readFile(
  join(process.env.WORK, "fluxtuner/web/static/js/dashboard.js"),
  "utf8",
);

// Replace only the absolute browser import in this isolated
// Node test. Production code is loaded unchanged otherwise.
source = source.replace(
  'import { escapeHtml } from "/static/js/stations.js";',
  'const escapeHtml = (value) => String(value);',
);

const { createDashboardController } = await import(
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
  let user = { id: 1 };
  let visible = true;
  let view = "search";

  const messageNode = { textContent: "" };
  const userMetricsNode = { innerHTML: "" };
  const panelNode = {};
  const controller = createDashboardController({
    apiFetch: () => {
      const pending = deferred();
      requests.push(pending);
      return pending.promise;
    },
    panelNode,
    messageNode,
    userMetricsNode,
    recentHistoryNode: null,
    favoriteHighlightsNode: null,
    adminPanelNode: null,
    adminMetricsNode: null,
    adminActionButton: null,
    renderStation: () => "",
    bindResultActions: () => {},
    showDashboardView: () => { visible = true; },
    isAuthenticated: () => Boolean(user),
    setCurrentView: (value) => { view = value; },
    setCurrentPlaylistName: () => {},
    getCurrentUser: () => user,
    isDashboardVisible: () => visible,
  });

  return {
    controller,
    requests,
    messageNode,
    userMetricsNode,
    setUser: (value) => { user = value; },
    setVisible: (value) => { visible = value; },
    getView: () => view,
  };
}

const reply = (count) => ({
  ok: true,
  json: async () => ({ user: { favorites_count: count } }),
});

{
  const h = harness();
  const old = h.controller.loadDashboard();
  const newer = h.controller.loadDashboard();

  h.requests[1].resolve(reply(20));
  await newer;
  h.requests[0].resolve(reply(10));
  await old;

  assert.match(h.userMetricsNode.innerHTML, />20</);
  assert.doesNotMatch(h.userMetricsNode.innerHTML, />10</);
  console.log("PASS: latest dashboard request wins");
}

{
  const h = harness();
  const pending = h.controller.loadDashboard();

  h.setVisible(false);
  h.requests[0].resolve(reply(30));
  await pending;

  assert.equal(h.userMetricsNode.innerHTML, "");
  console.log("PASS: hidden dashboard discards normal result");
}

{
  const h = harness();
  const pending = h.controller.loadDashboard();

  h.setUser({ id: 2 });
  h.requests[0].resolve(reply(40));
  await pending;

  assert.equal(h.userMetricsNode.innerHTML, "");
  console.log("PASS: session change discards response");
}

{
  const h = harness();
  const pending = h.controller.loadDashboard({
    preserveView: true,
    silent: true,
  });

  h.setVisible(false);
  h.requests[0].resolve(reply(50));
  await pending;

  assert.match(h.userMetricsNode.innerHTML, />50</);
  assert.equal(h.getView(), "search");
  assert.equal(h.messageNode.textContent, "");
  console.log("PASS: silent preserveView refresh remains valid");
}

{
  const h = harness();
  const pending = h.controller.loadDashboard({
    preserveView: true,
    silent: true,
  });

  h.setUser(null);
  h.requests[0].resolve(reply(60));
  await pending;

  assert.equal(h.userMetricsNode.innerHTML, "");
  console.log("PASS: silent refresh respects logout");
}

{
  const h = harness();
  const pending = h.controller.loadDashboard();
  const json = deferred();

  h.requests[0].resolve({
    ok: true,
    json: () => json.promise,
  });
  await Promise.resolve();
  await Promise.resolve();

  h.setVisible(false);
  json.resolve({ user: { favorites_count: 70 } });
  await pending;

  assert.equal(h.userMetricsNode.innerHTML, "");
  console.log("PASS: late JSON cannot overwrite abandoned view");
}

console.log("BEHAVIOR_GATE=PASS");
