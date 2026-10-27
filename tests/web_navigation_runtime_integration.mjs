/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

async function load(name) {
  const source = await readFile(
    join(process.env.WORK, "fluxtuner/web/static/js", name),
    "utf8",
  );
  return import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
}

const { createAppState } = await load("app-state.js");
const { createUiShellController } = await load("ui-shell.js");
const { createNavigationController } = await load("navigation.js");
const { createSessionUiController } = await load("session-ui.js");

const state = createAppState();
const panel = (hidden = true) => ({ hidden, dataset: {} });

const accountPanel = panel();
const adminPanel = panel();
const dashboardPanel = panel();
const searchPanel = panel(false);
const appContent = panel();
const authPanel = panel(false);

const appHeader = {
  dataset: { mobileMenuOpen: "false" },
};
const navToggleButton = {
  setAttribute() {},
};

const resultsNode = { innerHTML: "" };
const resultCountNode = { textContent: "" };
const resultsKickerNode = { textContent: "" };
const resultsTitleNode = { textContent: "" };
const scrollTargets = [];

const shell = createUiShellController({
  accountPanel,
  adminPanel,
  appContentNodes: [appContent],
  appHeader,
  dashboardPanel,
  navToggleButton,
  playerBar: null,
  resultCountNode,
  resultsKickerNode,
  resultsNode,
  resultsTitleNode,
  searchPanel,
  setCurrentPlaylistName: state.setCurrentPlaylistName,
  setCurrentView: state.setCurrentView,
  setCurrentSection: state.setCurrentSection,
});

function expectView(destination, visiblePanel) {
  assert.equal(state.getCurrentDestination(), destination);

  for (const [name, node] of Object.entries({
    account: accountPanel,
    admin: adminPanel,
    dashboard: dashboardPanel,
    explore: searchPanel,
  })) {
    assert.equal(
      node.hidden,
      name !== visiblePanel,
      `panel mismatch: ${name}`,
    );
  }
}

state.setCurrentUser({ username: "listener", is_admin: false });

const navigation = createNavigationController({
  accountPanel,
  adminPanel,
  appState: state,
  authPanel,
  closeMobileMenu: shell.closeMobileMenu,
  dashboardPanel,
  loadDashboard: async () => {
    state.setCurrentView("dashboard");
    shell.showDashboardView();
  },
  checkHealth: async () => {},
  loadAdminUsersIfNeeded: async () => {},
  renderAuthRequired: () => {},
  resetRadioBrowserView: shell.resetRadioBrowserView,
  scrollToSection: (target) => scrollTargets.push(target),
  searchPanel,
  showAccountView: shell.showAccountView,
  showAdminView: shell.showAdminView,
  showRadioBrowserView: shell.showRadioBrowserView,
});

navigation.navigateToAccount();
expectView("account", "account");
assert.equal(scrollTargets.at(-1), accountPanel);

await navigation.navigateToDashboard();
expectView("dashboard", "dashboard");

navigation.navigateToSearch();
expectView("explore", "explore");

console.log("PASS: Account, Dashboard and Search stay synchronized");

state.setCurrentUser({ username: "admin", is_admin: true });

await navigation.navigateToAdmin();
expectView("admin", "admin");

console.log("PASS: authorized Admin navigation");

state.setCurrentUser({ username: "listener", is_admin: false });

const emptyController = {
  syncSession() {},
  reset() {},
};

const session = createSessionUiController({
  subscriptionController: emptyController,
  stationImportController: emptyController,
  customStationController: emptyController,
  accountRequestsController: {
    closeRegisterDialog() {},
  },
  adminController: emptyController,
  appState: state,
  authMessageNode: panel(),
  authPanel,
  authUserPanel: panel(),
  authUsernameNode: { textContent: "" },
  accountPanel,
  accountUsernameNode: { textContent: "" },
  dashboardPanel,
  isSetupAvailable: () => false,
  loginForm: panel(),
  navAdminButton: panel(),
  playerDebugController: {
    updateVisibility() {},
  },
  privateActionNodes: [],
  publicEntrySection: panel(),
  publicStatsController: {
    loadPublicStats() {},
  },
  publicStatsSection: panel(),
  registerDialog: panel(),
  resultsNode,
  resultCountNode,
  searchPanel,
  setAppContentVisible: shell.setAppContentVisible,
  setPlayerVisible: shell.setPlayerVisible,
  showRadioBrowserView: shell.showRadioBrowserView,
  adminPanel,
});

session.updateAuthUi();

expectView("explore", "explore");
assert.equal(appContent.hidden, false);

console.log("PASS: revoked Admin permission restores Explore");

navigation.navigateToAccount();
expectView("account", "account");

state.setCurrentUser(null);
session.updateAuthUi();

assert.equal(appContent.hidden, true);
assert.equal(accountPanel.hidden, true);
assert.equal(adminPanel.hidden, true);
assert.equal(dashboardPanel.hidden, true);
assert.equal(state.isAuthenticated(), false);

console.log("PASS: logout hides private application panels");

console.log("BEHAVIOR_GATE=PASS");
