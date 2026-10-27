/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const directory = join(
  process.env.WORK,
  "fluxtuner/web/static/js",
);

async function moduleUrl(name) {
  const source = await readFile(join(directory, name), "utf8");
  return `data:text/javascript;base64,${
    Buffer.from(source).toString("base64")
  }`;
}

const stateUrl = await moduleUrl("app-state.js");
const modelUrl = await moduleUrl("navigation-model.js");

const presentationSource = (
  await readFile(
    join(directory, "navigation-presentation.js"),
    "utf8",
  )
).replace(
  '"./navigation-model.js"',
  `"${modelUrl}"`,
);

const presentationUrl = `data:text/javascript;base64,${
  Buffer.from(presentationSource).toString("base64")
}`;

const { createAppState } = await import(stateUrl);
const { createNavigationPresentation } = await import(
  presentationUrl
);

const buttons = new Map();

for (const name of [
  "dashboard",
  "search",
  "favorites",
  "playlists",
  "subscriptions",
  "history",
  "account",
  "admin",
]) {
  buttons.set(`[data-nav-${name}]`, {
    attributes: new Map(),
    setAttribute(key, value) {
      this.attributes.set(key, value);
    },
    removeAttribute(key) {
      this.attributes.delete(key);
    },
    getAttribute(key) {
      return this.attributes.get(key) ?? null;
    },
  });
}

const appState = createAppState();
appState.setCurrentUser({ is_admin: false });

const presentation = createNavigationPresentation({
  appState,
  root: {
    querySelector(selector) {
      return buttons.get(selector) ?? null;
    },
  },
});

function selected() {
  return [...buttons.entries()]
    .filter(([, button]) => (
      button.getAttribute("aria-current") === "page"
    ))
    .map(([selector]) => selector);
}

function expectSelected(name) {
  assert.deepEqual(
    selected(),
    name ? [`[data-nav-${name}]`] : [],
  );
}

// Bind performs the initial render and subscribes to state changes.
const unbind = presentation.bind();
expectSelected("search");
console.log("PASS: initial authoritative destination");

// These assertions intentionally do not call render().
appState.setCurrentView("favorites");
expectSelected("favorites");

appState.setCurrentView("playlist");
expectSelected("playlists");

appState.setCurrentView("history");
expectSelected("history");

appState.setCurrentView("search");
expectSelected("search");

console.log("PASS: library transitions notify presentation");

appState.setCurrentSection("dashboard");
expectSelected("dashboard");

appState.setCurrentSection("account");
expectSelected("account");

appState.setCurrentSection("explore");
expectSelected("search");

console.log("PASS: section transitions notify presentation");

// The state can identify Admin while the user is not authorized,
// but the presentation must not expose it as active.
appState.setCurrentSection("admin");
expectSelected(null);

appState.setCurrentUser({ is_admin: true });
expectSelected("admin");

appState.setCurrentUser({ is_admin: false });
expectSelected(null);

appState.setCurrentSection("dashboard");
expectSelected("dashboard");

console.log("PASS: authorization and user-change updates");

appState.setCurrentUser(null);
expectSelected(null);

console.log("PASS: logout clears active navigation");

unbind();

appState.setCurrentUser({ is_admin: true });
appState.setCurrentSection("account");
expectSelected(null);

console.log("PASS: subscription cleanup");
console.log("BEHAVIOR_GATE=PASS");
