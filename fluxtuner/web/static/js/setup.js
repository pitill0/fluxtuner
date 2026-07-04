/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createSetupController({
  appContent,
  authPanel,
  getCurrentUser,
  loadAuthState,
  resetRadioBrowserView,
  scrollToSection,
  searchPanel,
  setAppContentVisible,
  setCsrfToken,
  setCurrentUser,
  setPlayerVisible,
  setupForm,
  setupMessageNode,
  setupPanel,
  setupTokenField,
  updateAuthUi,
}) {
  let setupAvailable = false;
  let setupRequiresToken = false;

  function isSetupAvailable() {
    return setupAvailable;
  }

  function updateSetupUi() {
    const authenticated = Boolean(getCurrentUser());

    setPlayerVisible(!setupAvailable && authenticated);

    if (appContent) {
      appContent.hidden = !authenticated || setupAvailable;
    }

    if (setupPanel) {
      setupPanel.hidden = !setupAvailable;
    }

    if (authPanel) {
      authPanel.hidden = setupAvailable || authenticated;
    }

    setAppContentVisible(!setupAvailable && authenticated);

    if (setupTokenField) {
      setupTokenField.hidden = !setupRequiresToken;
    }

    if (setupMessageNode && setupAvailable) {
      setupMessageNode.textContent = setupRequiresToken
        ? "Enter the setup verification value configured on the server."
        : "Local first-run setup is available. Create the first administrator.";
    }
  }

  async function loadSetupState() {
    try {
      const response = await fetch("/api/setup/status", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        setupAvailable = false;
        setupRequiresToken = false;
        updateSetupUi();
        await loadAuthState();
        return;
      }

      const payload = await response.json();
      setupAvailable = Boolean(payload.available);
      setupRequiresToken = Boolean(payload.requires_setup_token);
      updateSetupUi();

      if (!setupAvailable) {
        await loadAuthState();
        return;
      }

      setCurrentUser(null);
      setCsrfToken("");
      updateAuthUi();
    } catch (_error) {
      setupAvailable = false;
      setupRequiresToken = false;
      updateSetupUi();
      await loadAuthState();
    }
  }

  async function createFirstAdmin(event) {
    event.preventDefault();

    if (!setupForm || !setupMessageNode) return;

    const formData = new FormData(setupForm);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const setupToken = String(formData.get("setup_token") || "");

    if (password !== confirmPassword) {
      setupMessageNode.textContent = "Passwords do not match.";
      return;
    }

    setupMessageNode.textContent = "Creating administrator...";

    try {
      const body = {
        username,
        password,
      };

      if (setupRequiresToken) {
        body.setup_token = setupToken;
      }

      const response = await fetch("/api/setup/create-admin", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      setupForm.reset();

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Too many setup attempts. Try again later.");
        }

        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not complete first-run setup.");
      }

      const payload = await response.json();
      setCurrentUser(payload.user || null);
      setCsrfToken(payload.csrf_token || "");
      setupAvailable = false;
      setupRequiresToken = false;
      resetRadioBrowserView();
      updateSetupUi();
      updateAuthUi();
      scrollToSection(searchPanel);
    } catch (error) {
      setCurrentUser(null);
      setCsrfToken("");
      updateAuthUi();
      setupMessageNode.textContent = String(error);
    }
  }

  return {
    createFirstAdmin,
    isSetupAvailable,
    loadSetupState,
    updateSetupUi,
  };
}
