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

export function createThemeController({ documentRef = document, toggleButton, labelNode, presentation } = {}) {
  function applyTheme(theme) {
    const nextTheme = theme === "light" ? "light" : "dark";

    documentRef.documentElement.dataset.theme = nextTheme;
    documentRef.documentElement.style.colorScheme = nextTheme;

    if (labelNode) {
      const label = nextTheme === "light" ? "Dark" : "Light";
      const key = nextTheme === "light" ? "theme.dark" : "theme.light";
      if (presentation) presentation.present(labelNode, key, label);
      else labelNode.textContent = label;
    }

    if (toggleButton) {
      const label = nextTheme === "light" ? "Switch to dark theme" : "Switch to light theme";
      const key = nextTheme === "light" ? "theme.switch_dark" : "theme.switch_light";
      if (presentation) {
        presentation.present(toggleButton, key, label, "aria-label");
        presentation.present(toggleButton, key, label, "title");
      } else {
        toggleButton.setAttribute("aria-label", label);
        toggleButton.title = label;
      }
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
