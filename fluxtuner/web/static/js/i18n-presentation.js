/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

// Bind only explicit presentation writes. Never infer translation keys from
// displayed text, and never retain detached DOM nodes or replay controllers.
export function createDynamicPresentation() {
  const bindings = new WeakMap();
  let i18n;

  function read(node, attribute) {
    return attribute === "textContent" ? node.textContent : node.getAttribute(attribute);
  }

  function write(node, attribute, value) {
    if (attribute === "textContent") node.textContent = value;
    else node.setAttribute(attribute, value);
  }

  function valueFor(binding) {
    if (binding.parts) return binding.parts.map(part => typeof part === "string" ? part : valueFor(part)).join(binding.separator);
    const params = { ...binding.params };
    if (i18n) {
      for (const [name, format] of Object.entries(binding.formats ?? {})) {
        if (format === "number" && Number.isFinite(params[name])) {
          params[name] = new Intl.NumberFormat(i18n.locale).format(params[name]);
        } else if (format === "datetime") {
          const date = new Date(params[name]);
          if (Number.isFinite(date.getTime())) params[name] = date.toLocaleString(i18n.locale);
        }
      }
    }
    const translated = i18n?.t(binding.key, params);
    return translated === undefined || translated === binding.key ? binding.fallback : translated;
  }

  function present(node, key, fallback, attribute = "textContent", params = {}, formats = {}) {
    if (!node) return;
    let properties = bindings.get(node);
    if (!properties) {
      properties = new Map();
      bindings.set(node, properties);
    }
    const binding = { key, fallback, params: { ...params }, formats: { ...formats }, last: undefined };
    binding.last = valueFor(binding);
    write(node, attribute, binding.last);
    properties.set(attribute, binding);
  }

  function presentParts(node, parts, separator = "") {
    if (!node) return;
    let properties = bindings.get(node);
    if (!properties) {
      properties = new Map();
      bindings.set(node, properties);
    }
    const binding = { parts: parts.map(part => typeof part === "string" ? part : {
      ...part, params: { ...part.params }, formats: { ...part.formats },
    }), separator };
    binding.last = valueFor(binding);
    write(node, "textContent", binding.last);
    properties.set("textContent", binding);
  }

  // Explicitly relinquish a translation when writing external/raw data.
  function clear(node, attribute = "textContent") {
    if (!node) return;
    let properties = bindings.get(node);
    if (!properties) {
      properties = new Map();
      bindings.set(node, properties);
    }
    properties.set(attribute, null);
  }

  function owns(node, attribute) {
    return bindings.get(node)?.has(attribute) ?? false;
  }

  function refresh(root, engine) {
    i18n = engine;
    for (const node of root.querySelectorAll("*")) {
      for (const [attribute, binding] of bindings.get(node) ?? []) {
        if (!binding || read(node, attribute) !== binding.last) {
          // A controller replaced the value. Do not restore stale text, even
          // if the new value later happens to match an earlier translation.
          bindings.get(node).set(attribute, null);
          continue;
        }
        const next = valueFor(binding);
        if (next !== binding.last) write(node, attribute, next);
        binding.last = next;
      }
    }
  }

  // Temporary feedback owns a specific binding, not the displayed text.
  // A subsequent controller write invalidates the restoration token.
  function temporary(node, key, fallback, params = {}) {
    const previousText = read(node, "textContent");
    const candidate = bindings.get(node)?.get("textContent");
    const previous = candidate?.last === previousText ? candidate : null;
    present(node, key, fallback, "textContent", params);
    const token = bindings.get(node).get("textContent");
    return () => {
      if (bindings.get(node)?.get("textContent") !== token || read(node, "textContent") !== token.last) return;
      if (previous?.parts) presentParts(node, previous.parts, previous.separator);
      else if (previous) present(node, previous.key, previous.fallback, "textContent", previous.params, previous.formats);
      else {
        clear(node);
        write(node, "textContent", previousText);
      }
    };
  }

  function translate(key, fallback, params = {}) {
    return valueFor({ key, fallback, params });
  }

  // Markers are emitted only by trusted renderers, never by external data.
  function bindRendered(root) {
    if (!root) return;
    for (const node of root.querySelectorAll("[data-render-i18n]")) {
      const key = node.dataset.renderI18n;
      const count = node.dataset.renderCount;
      const formatted = node.dataset.renderFormattedCount !== undefined;
      const params = count === undefined ? {} : { count: Number(count) };
      if (formatted) params.number = Number(count);
      present(node, key, node.textContent, "textContent", params,
        formatted ? { number: "number" } : {});
    }
    for (const node of root.querySelectorAll("[data-render-number]")) {
      present(node, "format.number", node.textContent, "textContent",
        { number: Number(node.dataset.renderNumber) }, { number: "number" });
    }
    for (const node of root.querySelectorAll("[data-render-aria]")) {
      present(node, node.dataset.renderAria, node.getAttribute("aria-label"), "aria-label");
    }
  }

  return { present, presentParts, clear, owns, refresh, translate, temporary, bindRendered };
}
