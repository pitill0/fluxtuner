/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.env.WORK;

async function loadModule(name) {
  const source = await readFile(
    join(root, "fluxtuner/web/static/js", name),
    "utf8",
  );
  return import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
}

const { createUiShellController } = await loadModule("ui-shell.js");
const { createNavigationController } = await loadModule("navigation.js");
const { createSessionUiController } = await loadModule("session-ui.js");

const panel = (hidden = true) => ({
  hidden,
  dataset: {},
  textContent: "",
});

const searchPanel = panel(false);
const dashboardPanel = panel();
const adminPanel = panel();
const accountPanel = panel();
const accountUsernameNode = panel();
const authUsernameNode = panel();
const authUserPanel = panel();
const authPanel = panel(false);
const authMessageNode = panel();
const publicEntrySection = panel();
const publicStatsSection = panel();
const loginForm = panel();
const navAdminButton = panel();
const privateActionNodes = [{ disabled: true }, { disabled: true }];
const playerBar = {
  hidden: true,
  removeAttribute() { this.hidden = false; },
  setAttribute() { this.hidden = true; },
};

let user = { username: "listener", display_name: "Listener", is_admin: false };
let menuClosed = 0;
let authRequired = 0;
const scrollTargets = [];

const appState = {
  getCurrentUser: () => user,
  isAuthenticated: () => Boolean(user),
};

const shell = createUiShellController({
  accountPanel,
  adminPanel,
  appContentNodes: [panel()],
  appHeader: null,
  dashboardPanel,
  navToggleButton: null,
  playerBar,
  resultCountNode: null,
  resultsKickerNode: null,
  resultsNode: null,
  resultsTitleNode: null,
  searchPanel,
  setCurrentPlaylistName: () => {},
  setCurrentView: () => {},
});

const navigation = createNavigationController({
  accountPanel,
  accountRequestsController: {},
  adminPanel,
  appState,
  authPanel,
  checkHealth: async () => {},
  closeMobileMenu: () => { menuClosed++; },
  dashboardPanel,
  loadAdminUsersIfNeeded: async () => {},
  loadDashboard: async () => shell.showDashboardView(),
  renderAuthRequired: () => { authRequired++; },
  resetRadioBrowserView: shell.resetRadioBrowserView,
  scrollToSection: (node) => scrollTargets.push(node),
  searchPanel,
  showAccountView: shell.showAccountView,
  showAdminView: shell.showAdminView,
  showRadioBrowserView: shell.showRadioBrowserView,
});

const session = createSessionUiController({
  accountPanel,
  accountUsernameNode,
  accountRequestsController: { closeRegisterDialog: () => {} },
  adminController: { reset: () => {} },
  adminPanel,
  appState,
  authMessageNode,
  authPanel,
  authUserPanel,
  authUsernameNode,
  dashboardPanel,
  isSetupAvailable: () => false,
  loginForm,
  navAdminButton,
  playerDebugController: { updateVisibility: () => {} },
  privateActionNodes,
  publicEntrySection,
  publicStatsController: { loadPublicStats: () => {} },
  publicStatsSection,
  registerDialog: null,
  resultsNode: null,
  resultCountNode: null,
  searchPanel,
  setAppContentVisible: () => {},
  setPlayerVisible: shell.setPlayerVisible,
  showRadioBrowserView: shell.showRadioBrowserView,
});

function assertExclusive(expected) {
  const visible = [
    ["search", searchPanel],
    ["dashboard", dashboardPanel],
    ["admin", adminPanel],
    ["account", accountPanel],
  ].filter(([, node]) => !node.hidden).map(([name]) => name);
  assert.deepEqual(visible, [expected]);
}

session.updateAuthUi();
assert.equal(accountUsernameNode.textContent, "listener");
assert.equal(authUsernameNode.textContent, "Listener");
assert(privateActionNodes.every((node) => !node.disabled));
console.log("PASS: authenticated identity");

navigation.navigateToAccount();
assertExclusive("account");
assert.equal(scrollTargets.at(-1), accountPanel);
assert.equal(menuClosed, 1);
console.log("PASS: Account navigation and mobile menu closure");

session.updateAuthUi();
assertExclusive("account");
console.log("PASS: Account preserved during session refresh");

await navigation.navigateToDashboard();
assertExclusive("dashboard");
console.log("PASS: Dashboard navigation remains exclusive");

navigation.navigateToAccount();
shell.showAdminView();
assertExclusive("admin");
console.log("PASS: Admin view remains exclusive");

navigation.navigateToAccount();
navigation.navigateToSearch();
assertExclusive("search");
console.log("PASS: Search navigation remains exclusive");

navigation.navigateToAccount();
user = null;
session.updateAuthUi();
assert(accountPanel.hidden);
assert.equal(accountUsernameNode.textContent, "");
assert.equal(authUsernameNode.textContent, "");
assert(privateActionNodes.every((node) => node.disabled));
console.log("PASS: logout hides Account, clears identity and disables private actions");

navigation.navigateToAccount();
assert.equal(authRequired, 1);
assert.equal(scrollTargets.at(-1), authPanel);
assert(accountPanel.hidden);
console.log("PASS: unauthenticated Account navigation denied");

console.log("BEHAVIOR_GATE=PASS");
