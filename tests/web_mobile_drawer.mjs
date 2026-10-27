/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/mobile-drawer.js",
  ),
  "utf8",
);

const { createMobileDrawer } = await import(
  `data:text/javascript;base64,${Buffer.from(
    source,
  ).toString("base64")}`
);

let isMobile = true;
let activeElement = null;
const observerCallbacks = new Map();

const groups = new Map();
const listeners = new Map();
const windowListeners = new Map();

class MockMutationObserver {
  constructor(callback) {
    this.callback = callback;
    this.target = null;
  }

  observe(target) {
    this.target = target;
    observerCallbacks.set(target, this.callback);
  }

  disconnect() {
    if (this.target) observerCallbacks.delete(this.target);
  }
}

globalThis.MutationObserver = MockMutationObserver;

function mockButton(key) {
  const attributes = new Map([["aria-expanded", "false"]]);
  return {
    dataset: { navGroupToggle: key },
    attributes,
    setAttribute: (name, value) => attributes.set(name, value),
    getAttribute: (name) => attributes.get(name),
    focus() {
      activeElement = this;
    },
  };
}

for (const key of ["library", "actions", "system"]) {
  groups.set(key, {
    group: { dataset: {} },
    button: mockButton(key),
    content: { hidden: true },
  });
}

const menu = {
  dataset: {},
  addEventListener(name, callback) {
    listeners.set(`menu:${name}`, callback);
  },
  contains(node) {
    return node === backButton;
  },
};

const backButton = {
  hidden: true,
  addEventListener(name, callback) {
    listeners.set(`back:${name}`, callback);
  },
  focus() {
    activeElement = this;
  },
};

const title = { textContent: "" };
const documentListeners = new Map();

const documentNode = {
  get activeElement() {
    return activeElement;
  },
  addEventListener(name, callback) {
    documentListeners.set(name, callback);
  },
  removeEventListener(name, callback) {
    if (documentListeners.get(name) === callback) {
      documentListeners.delete(name);
    }
  },
  querySelector() {
    return null;
  },
};

const root = {
  ownerDocument: documentNode,
  querySelector(selector) {
    if (selector === "[data-app-menu]") return menu;
    if (selector === "[data-mobile-drawer-back]") return backButton;
    if (selector === "[data-mobile-drawer-title]") return title;

    for (const [key, nodes] of groups) {
      if (selector === `[data-nav-group="${key}"]`) {
        return nodes.group;
      }
      if (selector === `[data-nav-group-toggle="${key}"]`) {
        return nodes.button;
      }
      if (selector === `[data-nav-group-content="${key}"]`) {
        return nodes.content;
      }
    }

    return null;
  },
};

const header = { dataset: { mobileMenuOpen: "true" } };

const toggleButton = {
  focus() {
    activeElement = this;
  },
};

const controller = createMobileDrawer({
  root,
  header,
  toggleButton,
  windowNode: {
    matchMedia: () => ({ matches: isMobile }),
    addEventListener: (name, callback) => {
      windowListeners.set(name, callback);
    },
    removeEventListener: (name) => {
      windowListeners.delete(name);
    },
  },
});

const unbind = controller.bind();
// Non-modal navigation must not register a Tab focus trap.
assert.equal(documentListeners.has("keydown"), false);

assert.equal(menu.dataset.mobileLevel, "root");
assert.equal(backButton.hidden, true);
assert.equal(title.textContent, "Navigation");

controller.enter("actions");
assert.equal(menu.dataset.mobileLevel, "group");
assert.equal(backButton.hidden, false);
assert.equal(title.textContent, "Library actions");
assert.equal(groups.get("actions").content.hidden, false);
assert.equal(activeElement, backButton);

listeners.get("back:click")({
  stopPropagation() {},
});

assert.equal(menu.dataset.mobileLevel, "root");
assert.equal(activeElement, groups.get("actions").button);

controller.enter("system");
assert.equal(groups.get("system").content.hidden, false);

// Closing the menu while focus is inside it returns to hamburger.
header.dataset.mobileMenuOpen = "false";
assert.equal(typeof observerCallbacks.get(header), "function");
observerCallbacks.get(header)();

assert.equal(menu.dataset.mobileLevel, "root");
assert.equal(activeElement, toggleButton);

// Resizing to desktop restores the pre-drawer accordion state.
header.dataset.mobileMenuOpen = "true";
controller.enter("library");

isMobile = false;
windowListeners.get("resize")();

assert.equal(menu.dataset.mobileLevel, "root");
for (const nodes of groups.values()) {
  assert.equal(nodes.content.hidden, true);
  assert.equal(nodes.button.getAttribute("aria-expanded"), "false");
}

unbind();

assert.equal(documentListeners.has("keydown"), false);

console.log("PASS: keyboard listener lifecycle");
console.log("PASS: root presentation");
console.log("PASS: secondary level");
console.log("PASS: Back focus returns to originating group");
console.log("PASS: close returns focus to hamburger");
console.log("PASS: breakpoint restores accordion state");
console.log("BEHAVIOR_GATE=PASS");
