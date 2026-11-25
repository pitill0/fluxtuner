/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { browserI18n } from "./i18n.js";

const ATTRIBUTES = ["aria-label", "title", "placeholder", "alt", "content"];
const normalize = (value) => value?.trim().replace(/\s+/g, " ");

// Share template bindings between early bootstrap and the application, so
// translation can start before the controller graph is ready without recapturing
// already translated or controller-owned content.
const templates = new WeakMap();
export function createTemplateTranslator(root, i18n, presentation) {
  const existing = templates.get(root);
  if (existing?.i18n === i18n) {
    if (presentation) existing.presentation = presentation;
    return existing.apply;
  }
  const state = { i18n, presentation };
  const bindings = [];
  function bind(marker, read, write, attribute = "textContent") {
    for (const node of root.querySelectorAll(`[${marker}]`)) {
      const key = node.getAttribute(marker);
      const original = read(node);
      let previous;
      bindings.push(() => {
        if (state.presentation?.owns(node, attribute)) return;
        const expected = previous ?? i18n.englishText(key) ?? original;
        if (typeof expected !== "string" || normalize(read(node)) !== normalize(expected)) return;
        const next = i18n.t(key);
        if (next === key) return;
        if (read(node) !== next) write(node, next);
        previous = next;
      });
    }
  }
  bind("data-i18n", (node) => node.textContent, (node, value) => {
    if (!node.children.length) node.textContent = value;
  });
  for (const attr of ATTRIBUTES) {
    bind(`data-i18n-${attr}`, (node) => node.getAttribute(attr),
      (node, value) => node.setAttribute(attr, value), attr);
  }
  state.apply = () => {
    for (const apply of bindings) apply();
    root.documentElement.lang = i18n.locale;
  };
  templates.set(root, state);
  return state.apply;
}

export function createLanguageController({ root, selector, i18n, presentation }) {
  const translate = createTemplateTranslator(root, i18n, presentation);
  function render() {
    translate();
    presentation?.refresh(root, i18n);
    selector.value = i18n.locale;
  }
  async function change(language) {
    try {
      if (await i18n.setLocale(language)) render();
    } catch {
      selector.value = i18n.locale;
    }
  }
  async function initialize() {
    try {
      if (await i18n.initialize()) render();
    } catch {
      // The original English template is usable without catalog requests.
      selector.value = i18n.locale;
    }
  }
  selector.addEventListener("change", () => { void change(selector.value); });
  return { initialize, change, render };
}

// Initialize the language UI once, independently of application bootstrap.
export function initializeLanguageUi(root = document, browser = window, presentation) {
  const control = root.querySelector("[data-language-control]");
  const selector = root.querySelector("[data-language-select]");
  if (!control || control.hidden || !selector) return;
  const i18n = browserI18n(browser);
  relocateLanguageControl(root, browser, control);
  const controller = createLanguageController({ root, selector, i18n, presentation });
  const ready = controller.initialize();
  return { i18n, controller, ready };
}

// Move the same control, rather than creating a second selector or listener.
function relocateLanguageControl(root, browser, control) {
  if (!browser.matchMedia || !browser.MutationObserver) return;
  const user = root.querySelector("[data-auth-user]");
  const menu = root.querySelector("[data-language-mobile-slot]");
  if (!user || !menu || !control.parentNode) return;
  const home = control.parentNode;
  const next = control.nextSibling;
  const narrow = browser.matchMedia("(max-width: 58rem)");
  function update() {
    if (narrow.matches && !user.hidden) {
      if (control.parentNode !== menu) menu.append(control);
    } else if (control.parentNode !== home) {
      home.insertBefore(control, next);
    }
  }
  narrow.addEventListener("change", update);
  new browser.MutationObserver(update).observe(user, { attributes: true, attributeFilter: ["hidden"] });
  update();
}
