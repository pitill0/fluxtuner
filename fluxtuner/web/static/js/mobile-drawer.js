/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

/*
 * Mobile-only two-level presentation.
 * Reuses the existing navigation controls and destinations.
 */

const GROUP_TITLES = Object.freeze({
  library: "My library",
  actions: "Library actions",
  system: "Account & system",
});

export function createMobileDrawer({
  root,
  header,
  toggleButton,
  windowNode,
}) {
  let selected = null;
  let previouslyOpen = false;
  const saved = new Map();

  function mobile() {
    return windowNode?.matchMedia?.("(max-width: 58rem)")?.matches ?? false;
  }

  function elements() {
    return {
      menu: root?.querySelector("[data-app-menu]"),
      back: root?.querySelector("[data-mobile-drawer-back]"),
      title: root?.querySelector("[data-mobile-drawer-title]"),
    };
  }

  function groupNodes(key) {
    return {
      group: root?.querySelector(`[data-nav-group="${key}"]`),
      button: root?.querySelector(`[data-nav-group-toggle="${key}"]`),
      content: root?.querySelector(`[data-nav-group-content="${key}"]`),
    };
  }

  function paint() {
    const { menu, back, title } = elements();
    if (!menu || !back || !title) return;

    menu.dataset.mobileLevel = selected ? "group" : "root";
    back.hidden = !selected;
    title.textContent = selected ? GROUP_TITLES[selected] : "Navigation";

    for (const key of Object.keys(GROUP_TITLES)) {
      const { group } = groupNodes(key);
      if (group) {
        group.dataset.mobileSelected = String(selected === key);
      }
    }
  }

  function enter(key) {
    if (!mobile() || !GROUP_TITLES[key]) return;

    if (!saved.size) {
      for (const name of Object.keys(GROUP_TITLES)) {
        const { button, content } = groupNodes(name);
        if (button && content) {
          saved.set(name, {
            hidden: content.hidden,
            expanded: button.getAttribute("aria-expanded"),
          });
        }
      }
    }

    selected = key;

    for (const name of Object.keys(GROUP_TITLES)) {
      const { button, content } = groupNodes(name);
      if (!button || !content) continue;

      const open = name === key;
      content.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    }

    paint();
    const { back } = elements();
    back?.focus?.();
  }

  function back({ restoreFocus = false } = {}) {
    const previous = selected;
    selected = null;

    for (const [key, state] of saved) {
      const { button, content } = groupNodes(key);
      if (!button || !content) continue;

      content.hidden = state.hidden;
      button.setAttribute("aria-expanded", state.expanded ?? "false");
    }

    saved.clear();
    paint();

    if (restoreFocus && previous && mobile()) {
      groupNodes(previous).button?.focus?.();
    }
  }

  function closeSync() {
    if (!mobile()) return;

    const open = header?.dataset.mobileMenuOpen === "true";

    if (previouslyOpen && !open) {
      const { menu } = elements();
      const containedFocus = menu?.contains?.(
        root?.ownerDocument?.activeElement,
      );

      back();

      if (containedFocus) toggleButton?.focus?.();
    }

    previouslyOpen = open;
  }

  function bind() {
    if (!root || !header) return () => {};

    const { menu, back: backButton } = elements();
    if (!menu || !backButton) return () => {};

    menu.addEventListener("click", (event) => {
      if (!mobile()) return;

      const target = event.target;
      const groupButton = target?.closest?.("[data-nav-group-toggle]");
      if (!groupButton) return;

      const key = groupButton.dataset.navGroupToggle;
      if (!GROUP_TITLES[key]) return;

      // Capture prevents the desktop accordion listener
      // from changing the level after this interaction.
      event.preventDefault();
      event.stopImmediatePropagation();
      enter(key);
    }, true);

    backButton.addEventListener("click", (event) => {
      event.stopPropagation();
      back({ restoreFocus: true });
    });

    const observer = new MutationObserver(closeSync);
    observer.observe(header, {
      attributes: true,
      attributeFilter: ["data-mobile-menu-open"],
    });

    // Losing the private application closes the navigation
    // without returning focus to an unavailable control.
    const appContent = root.querySelector("[data-app-content]");
    const sessionObserver = new MutationObserver(() => {
      if (!appContent?.hidden) return;

      header.dataset.mobileMenuOpen = "false";
      toggleButton?.setAttribute("aria-expanded", "false");

      back();
      previouslyOpen = false;

    });

    if (appContent) {
      sessionObserver.observe(appContent, {
        attributes: true,
        attributeFilter: ["hidden"],
      });
    }


    const onResize = () => {
      if (!mobile()) {
        back();
        previouslyOpen = false;
      }
    };

    windowNode?.addEventListener?.("resize", onResize);

    paint();
    closeSync();

    return () => {
      observer.disconnect();
      sessionObserver.disconnect();
      windowNode?.removeEventListener?.("resize", onResize);
    };
  }

  return { bind, enter, back, paint };
}
