/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export const SUPPORTED_LOCALES = Object.freeze(["en", "es", "ca", "fr", "de", "zh-CN", "zh-TW", "ko", "ja", "gl", "eu", "it", "pl", "ru"]);
export const LANGUAGE_STORAGE_KEY = "fluxtuner.language";

export function resolveLocale(preferences = []) {
  for (const preference of preferences) {
    if (typeof preference !== "string") continue;
    try {
      const { language, script, region } = new Intl.Locale(preference);
      if (language === "zh") {
        if (script === "Hans") return "zh-CN";
        if (script === "Hant") return "zh-TW";
        return ["TW", "HK", "MO"].includes(region) ? "zh-TW" : "zh-CN";
      }
      if (SUPPORTED_LOCALES.includes(language)) return language;
    } catch {
      // Invalid locale: consider the next preference.
    }
  }
  return "en";
}

export async function loadCatalog(locale, fetchRef = globalThis.fetch) {
  if (!SUPPORTED_LOCALES.includes(locale)) throw new RangeError("Unsupported locale");
  const url = new URL(`../locales/${locale}.json`, import.meta.url);
  const response = await fetchRef(url, { credentials: "same-origin", priority: "high" });
  if (!response.ok) throw new Error("Could not load locale catalog");
  return response.json();
}

function validMessage(value) {
  return typeof value === "string" || (value !== null && typeof value === "object"
    && !Array.isArray(value) && Object.hasOwn(value, "other")
    && Object.values(value).every((entry) => typeof entry === "string"));
}

function interpolate(message, params) {
  return message.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (match, name) =>
    Object.hasOwn(params, name) ? String(params[name]) : match);
}

export function createI18n({ loader = loadCatalog, storage, preferences = [] } = {}) {
  let locale = "en";
  let english = null;
  let current = null;
  let request = 0;
  let initialRequest;
  const catalogs = new Map();

  async function catalog(language) {
    if (!catalogs.has(language)) {
      const pending = Promise.resolve().then(() => loader(language)).then((data) => {
        if (!data || typeof data !== "object" || Array.isArray(data)
          || !Object.values(data).every(validMessage)) {
          throw new TypeError("Invalid locale catalog");
        }
        return data;
      });
      catalogs.set(language, pending);
      pending.catch(() => { if (catalogs.get(language) === pending) catalogs.delete(language); });
    }
    return catalogs.get(language);
  }

  async function setLocale(language, { persist = true } = {}) {
    if (!SUPPORTED_LOCALES.includes(language)) throw new RangeError("Unsupported locale");
    const ticket = ++request;
    const baseRequest = catalog("en");
    const selectedRequest = language === "en" ? baseRequest : catalog(language);
    const [baseResult, selectedResult] = await Promise.allSettled([baseRequest, selectedRequest]);
    const base = baseResult.status === "fulfilled" ? baseResult.value : null;
    const next = selectedResult.status === "fulfilled" ? selectedResult.value : base;
    const effective = selectedResult.status === "fulfilled" ? language : "en";
    if (ticket !== request) return false;
    if (!next) throw new Error("No locale catalog available");
    english = base;
    current = next;
    locale = effective;
    if (persist && next && effective === language) {
      try { storage?.setItem(LANGUAGE_STORAGE_KEY, language); } catch { /* optional storage */ }
    }
    return true;
  }

  function initialize() {
    if (initialRequest) return initialRequest;
    let saved;
    try { saved = storage?.getItem(LANGUAGE_STORAGE_KEY); } catch { /* optional storage */ }
    const selected = SUPPORTED_LOCALES.includes(saved) ? saved : resolveLocale(preferences);
    const pending = setLocale(selected, { persist: false });
    initialRequest = pending;
    pending.catch(() => { if (initialRequest === pending) initialRequest = undefined; });
    return pending;
  }

  function t(key, params = {}) {
    for (const [data, language] of [[current, locale], [english, "en"]]) {
      if (!data || !Object.hasOwn(data, key)) continue;
      let message = data[key];
      if (typeof message !== "string") {
        if (typeof params.count !== "number" || !Number.isFinite(params.count)) continue;
        const category = new Intl.PluralRules(language).select(params.count);
        message = Object.hasOwn(message, category) ? message[category] : message.other;
      }
      const display = { ...params };
      if (typeof display.count === "number" && Number.isFinite(display.count)) {
        display.count = new Intl.NumberFormat(locale).format(display.count);
      }
      return interpolate(message, display);
    }
    return key;
  }

  return { initialize, setLocale, t,
    englishText(key) { return english && Object.hasOwn(english, key) ? english[key] : undefined; },
    get locale() { return locale; } };
}

// A small independent entry point can warm the same engine before app.js.
const browserEngines = new WeakMap();
export function browserI18n(browser) {
  if (!browserEngines.has(browser)) {
    let storage;
    try { storage = browser.localStorage; } catch { /* optional storage */ }
    const preferences = browser.navigator.languages || [browser.navigator.language];
    browserEngines.set(browser, createI18n({ storage, preferences }));
  }
  return browserEngines.get(browser);
}
