/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createUiShellController({
  accountPanel,
  adminPanel,
  appContentNodes,
  appHeader,
  dashboardPanel,
  navToggleButton,
  playerBar,
  resultCountNode,
  resultsKickerNode,
  resultsNode,
  resultsTitleNode,
  searchPanel,
  setCurrentPlaylistName,
  setCurrentView,
}) {
  function setResultsHeader(kicker, title) {
    if (resultsKickerNode) {
      resultsKickerNode.textContent = kicker;
    }

    if (resultsTitleNode) {
      resultsTitleNode.textContent = title;
    }
  }

  function setAppContentVisible(visible) {
    appContentNodes.forEach((node) => {
      node.hidden = !visible;
    });
  }

  function scrollToSection(node) {
    if (!node) return;

    const headerHeight = appHeader?.getBoundingClientRect().height ?? 0;
    const headerTop = appHeader
      ? Number.parseFloat(window.getComputedStyle(appHeader).top) || 0
      : 0;
    const gap = 16;
    const targetTop =
      window.scrollY +
      node.getBoundingClientRect().top -
      headerHeight -
      headerTop -
      gap;

    window.scrollTo({
      top: Math.max(0, targetTop),
      behavior: "smooth",
    });
  }

  function setMobileMenuOpen(open) {
    if (!appHeader || !navToggleButton) return;

    const nextState = open ? "true" : "false";
    appHeader.dataset.mobileMenuOpen = nextState;
    navToggleButton.setAttribute("aria-expanded", nextState);
  }

  function closeMobileMenu() {
    setMobileMenuOpen(false);
  }

  function setPlayerVisible(isVisible) {
    if (!playerBar) return;

    if (isVisible) {
      playerBar.removeAttribute("hidden");
    } else {
      playerBar.setAttribute("hidden", "");
    }
  }

  function showRadioBrowserView() {
    if (accountPanel) {
      accountPanel.hidden = true;
    }

    if (searchPanel) {
      searchPanel.hidden = false;
    }

    if (dashboardPanel) {
      dashboardPanel.hidden = true;
    }

    if (adminPanel) {
      adminPanel.hidden = true;
    }
  }

  function showDashboardView() {
    if (accountPanel) {
      accountPanel.hidden = true;
    }

    if (searchPanel) {
      searchPanel.hidden = true;
    }

    if (dashboardPanel) {
      dashboardPanel.hidden = false;
    }

    if (adminPanel) {
      adminPanel.hidden = true;
    }
  }

  function showAdminView() {
    if (accountPanel) {
      accountPanel.hidden = true;
    }

    if (searchPanel) {
      searchPanel.hidden = true;
    }

    if (dashboardPanel) {
      dashboardPanel.hidden = true;
    }

    if (adminPanel) {
      adminPanel.hidden = false;
    }
  }

  function showAccountView() {
    if (searchPanel) searchPanel.hidden = true;
    if (dashboardPanel) dashboardPanel.hidden = true;
    if (adminPanel) adminPanel.hidden = true;
    if (accountPanel) accountPanel.hidden = false;
  }

  function resetRadioBrowserView() {
    showRadioBrowserView();
    setCurrentView("search");
    setCurrentPlaylistName("");
    setResultsHeader("Radio Browser", "Search stations");

    if (resultCountNode) {
      resultCountNode.textContent = "";
    }

    if (resultsNode) {
      resultsNode.innerHTML = '<p class="empty">Search Radio Browser to find internet radio stations.</p>';
    }
  }

  return {
    closeMobileMenu,
    resetRadioBrowserView,
    scrollToSection,
    setAppContentVisible,
    setMobileMenuOpen,
    setPlayerVisible,
    setResultsHeader,
    showAccountView,
    showAdminView,
    showDashboardView,
    showRadioBrowserView,
  };
}
