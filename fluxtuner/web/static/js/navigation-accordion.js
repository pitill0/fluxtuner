/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

/*
 * Accordion presentation for existing navigation controls.
 *
 * Destination selection remains owned by the application.
 * Group expansion does not navigate or modify session state.
 */

export function createNavigationAccordion({ root }) {
  const keys = ["library", "actions", "system"];
  const groups = new Map();

  function setExpanded(key, expanded) {
    const group = groups.get(key);
    if (!group) return;

    group.button.setAttribute(
      "aria-expanded",
      String(expanded),
    );
    group.content.hidden = !expanded;
  }

  function activeGroup() {
    for (const [key, group] of groups) {
      if (group.content.querySelector(
        '[aria-current="page"]',
      )) {
        return key;
      }
    }
    return null;
  }

  function syncActive() {
    const key = activeGroup();
    if (key) setExpanded(key, true);
  }

  function bind() {
    if (!root) return () => {};

    for (const key of keys) {
      const button = root.querySelector(
        `[data-nav-group-toggle="${key}"]`,
      );
      const content = root.querySelector(
        `[data-nav-group-content="${key}"]`,
      );

      if (!button || !content) continue;

      groups.set(key, { button, content });
      setExpanded(key, false);

      button.addEventListener("click", () => {
        const expanded = button.getAttribute(
          "aria-expanded",
        ) === "true";

        setExpanded(key, !expanded);
      });
    }

    syncActive();

    const nav = root.querySelector(".app-nav");
    if (!nav || typeof MutationObserver === "undefined") {
      return () => {};
    }

    const observer = new MutationObserver(syncActive);

    observer.observe(nav, {
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-current"],
    });

    return () => observer.disconnect();
  }

  return {
    bind,
    setExpanded,
    syncActive,
  };
}
