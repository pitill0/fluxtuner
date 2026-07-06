/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const THEME_STORAGE_KEY = "fluxtuner.theme";

function systemThemePreference() {
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
    return "light";
  }

  return "dark";
}

function storedThemePreference() {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    return storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
  } catch {
    return null;
  }
}

function saveThemePreference(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures. The selected theme still applies for this page load.
  }
}

export function createThemeController({ documentRef = document, toggleButton, labelNode } = {}) {
  function applyTheme(theme) {
    const nextTheme = theme === "light" ? "light" : "dark";

    documentRef.documentElement.dataset.theme = nextTheme;
    documentRef.documentElement.style.colorScheme = nextTheme;

    if (labelNode) {
      labelNode.textContent = nextTheme === "light" ? "Dark" : "Light";
    }

    if (toggleButton) {
      const label = nextTheme === "light" ? "Switch to dark theme" : "Switch to light theme";
      toggleButton.setAttribute("aria-label", label);
      toggleButton.title = label;
    }
  }

  function toggleTheme() {
    const currentTheme =
      documentRef.documentElement.dataset.theme === "light" ? "light" : "dark";
    const nextTheme = currentTheme === "light" ? "dark" : "light";

    applyTheme(nextTheme);
    saveThemePreference(nextTheme);
  }

  function initializeTheme() {
    applyTheme(storedThemePreference() || systemThemePreference());
  }

  return {
    applyTheme,
    initializeTheme,
    toggleTheme,
  };
}
