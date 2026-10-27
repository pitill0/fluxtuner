/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

/*
 * Desktop-only presentation state.
 *
 * This does not affect the active destination, session,
 * existing mobile menu, or player runtime.
 */

export function createSidebarToggle({
  shell,
  button,
  windowNode,
}) {
  let collapsed = false;

  function render() {
    if (!shell || !button) return;

    shell.dataset.sidebarCollapsed = String(collapsed);
    button.setAttribute("aria-expanded", String(!collapsed));

    const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);

    const icon = button.querySelector?.("[data-sidebar-toggle-icon]");
    if (icon) icon.textContent = collapsed ? "›" : "‹";

    const labelNode = button.querySelector?.("[data-sidebar-toggle-label]");
    if (labelNode) labelNode.textContent = "Menu";
  }

  function toggle() {
    collapsed = !collapsed;
    render();
  }

  function bind() {
    if (!shell || !button) return;

    render();

    button.addEventListener("click", toggle);

    // A layout preference, not an application destination.
    // Resizing does not change navigation or playback.
    windowNode?.addEventListener("resize", render);
  }

  return { bind, render, toggle };
}
