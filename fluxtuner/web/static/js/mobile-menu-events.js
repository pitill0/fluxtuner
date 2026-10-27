/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

/*
 * Classify a click without changing application navigation.
 *
 * The mobile navigation region is the sibling immediately
 * following the header in the UX-02 application shell.
 */

const NAVIGATION_ACTION = [
  "[data-nav-dashboard]",
  "[data-nav-search]",
  "[data-nav-favorites]",
  "[data-nav-playlists]",
  "[data-nav-history]",
  "[data-nav-account]",
  "[data-nav-admin]",
  "[data-nav-subscriptions]",
  "[data-nav-custom-station]",
  "[data-nav-station-import]",
].join(", ");

export function mobileMenuClickDisposition({
  target,
  header,
  nodeConstructor,
}) {
  if (!header || !target || !(target instanceof nodeConstructor)) {
    return "outside";
  }

  if (header.contains(target)) {
    return "header";
  }

  const region = header.nextElementSibling;
  if (
    !region ||
    !region.hasAttribute("data-app-sidebar-region") ||
    !region.contains(target)
  ) {
    return "outside";
  }

  if (target.closest(NAVIGATION_ACTION)) {
    return "navigation";
  }

  return "inside";
}
