/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/navigation-accordion.js",
  ),
  "utf8",
);

const { createNavigationAccordion } = await import(
  `data:text/javascript;base64,${Buffer.from(
    source,
  ).toString("base64")}`
);

const groups = new Map();

for (const key of ["library", "actions", "system"]) {
  const attrs = new Map();
  const listeners = new Map();

  const button = {
    setAttribute: (name, value) => attrs.set(name, value),
    getAttribute: (name) => attrs.get(name),
    addEventListener: (event, callback) => {
      listeners.set(event, callback);
    },
  };

  const content = {
    hidden: false,
    active: false,
    querySelector(selector) {
      return selector === '[aria-current="page"]' &&
        this.active ? {} : null;
    },
  };

  groups.set(key, { button, content, listeners });
}

const root = {
  querySelector(selector) {
    for (const [key, group] of groups) {
      if (selector === `[data-nav-group-toggle="${key}"]`) {
        return group.button;
      }
      if (selector === `[data-nav-group-content="${key}"]`) {
        return group.content;
      }
    }
    return null;
  },
};

const controller = createNavigationAccordion({ root });
controller.bind();

for (const group of groups.values()) {
  assert.equal(group.content.hidden, true);
  assert.equal(
    group.button.getAttribute("aria-expanded"),
    "false",
  );
}

const library = groups.get("library");
library.listeners.get("click")();

assert.equal(library.content.hidden, false);
assert.equal(
  library.button.getAttribute("aria-expanded"),
  "true",
);

library.listeners.get("click")();
assert.equal(library.content.hidden, true);

groups.get("system").content.active = true;
controller.syncActive();

assert.equal(
  groups.get("system").button.getAttribute("aria-expanded"),
  "true",
);

assert.equal(
  groups.get("library").content.hidden,
  true,
);

const inactive = createNavigationAccordion({ root: null });
inactive.bind();
inactive.syncActive();

console.log("PASS: groups initially collapsed");
console.log("PASS: manual toggle");
console.log("PASS: aria-expanded synchronization");
console.log("PASS: active group automatically opens");
console.log("PASS: missing root handled safely");
console.log("BEHAVIOR_GATE=PASS");
