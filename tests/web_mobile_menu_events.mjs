/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/mobile-menu-events.js",
  ),
  "utf8",
);

const { mobileMenuClickDisposition } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

class MockNode {
  constructor(name, parent = null) {
    this.name = name;
    this.parent = parent;
    this.nextElementSibling = null;
  }

  contains(node) {
    for (let current = node; current; current = current.parent) {
      if (current === this) return true;
    }
    return false;
  }

  hasAttribute(name) {
    return this.name === "region" &&
      name === "data-app-sidebar-region";
  }

  closest(selector) {
    return this.name === "favorites" &&
      selector.includes("[data-nav-favorites]") ? this : null;
  }
}

const header = new MockNode("header");
const region = new MockNode("region");
header.nextElementSibling = region;

function classify(target) {
  return mobileMenuClickDisposition({
    target,
    header,
    nodeConstructor: MockNode,
  });
}

assert.equal(
  classify(new MockNode("hamburger", header)),
  "header",
);
assert.equal(
  classify(new MockNode("group-toggle", region)),
  "inside",
);
assert.equal(
  classify(new MockNode("favorites", region)),
  "navigation",
);
assert.equal(
  classify(new MockNode("dashboard")),
  "outside",
);
assert.equal(
  classify(null),
  "outside",
);

// Missing region must not be treated as inside the menu.
header.nextElementSibling = null;
assert.equal(
  classify(new MockNode("favorites", region)),
  "outside",
);

console.log("PASS: header clicks retained");
console.log("PASS: accordion clicks retained");
console.log("PASS: destination clicks recognized");
console.log("PASS: outside clicks recognized");
console.log("PASS: missing region handled");
console.log("BEHAVIOR_GATE=PASS");
