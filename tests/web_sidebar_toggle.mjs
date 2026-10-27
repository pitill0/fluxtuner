/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/sidebar-toggle.js",
  ),
  "utf8",
);

const { createSidebarToggle } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

const shell = { dataset: {} };
const attributes = new Map();
const listeners = new Map();
const windowListeners = new Map();

const button = {
  setAttribute: (name, value) => attributes.set(name, value),
  getAttribute: (name) => attributes.get(name),
  addEventListener: (name, callback) => listeners.set(name, callback),
};

const controller = createSidebarToggle({
  shell,
  button,
  windowNode: {
    addEventListener: (name, callback) => {
      windowListeners.set(name, callback);
    },
  },
});

controller.bind();

assert.equal(shell.dataset.sidebarCollapsed, "false");
assert.equal(button.getAttribute("aria-expanded"), "true");
assert.equal(button.getAttribute("aria-label"), "Collapse sidebar");

listeners.get("click")();

assert.equal(shell.dataset.sidebarCollapsed, "true");
assert.equal(button.getAttribute("aria-expanded"), "false");
assert.equal(button.getAttribute("aria-label"), "Expand sidebar");
assert.equal(button.getAttribute("title"), "Expand sidebar");

windowListeners.get("resize")();

assert.equal(shell.dataset.sidebarCollapsed, "true");

listeners.get("click")();

assert.equal(shell.dataset.sidebarCollapsed, "false");
assert.equal(button.getAttribute("aria-expanded"), "true");
assert.equal(button.getAttribute("aria-label"), "Collapse sidebar");

const inactive = createSidebarToggle({
  shell: null,
  button: null,
  windowNode: null,
});

inactive.bind();
inactive.toggle();

console.log("PASS: initial expanded state");
console.log("PASS: collapse and expand");
console.log("PASS: accessible labels");
console.log("PASS: resize preserves state");
console.log("PASS: missing elements handled safely");
console.log("BEHAVIOR_GATE=PASS");
