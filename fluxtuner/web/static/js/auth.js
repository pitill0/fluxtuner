/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createAuthController({
  apiFetch,
  authMessageNode,
  loginForm,
  loadDashboard,
  publicStatsController,
  renderAuthRequired,
  resetRadioBrowserView,
  setCsrfToken,
  setCurrentUser,
  stopPlayback,
  updateAuthUi,
}) {
  async function loadAuthState() {
    try {
      const response = await fetch("/api/auth/me", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        setCurrentUser(null);
        setCsrfToken("");
        updateAuthUi();
        return;
      }

      const payload = await response.json();
      setCurrentUser(payload.user || null);
      setCsrfToken(payload.csrf_token || "");
      resetRadioBrowserView();
      updateAuthUi();
      await loadDashboard();
    } catch (_error) {
      setCurrentUser(null);
      updateAuthUi();
    }
  }

  async function login(event) {
    event.preventDefault();

    if (!loginForm || !authMessageNode) return;

    const formData = new FormData(loginForm);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");

    authMessageNode.textContent = "Signing in...";

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      loginForm.reset();

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("Too many login attempts. Try again later.");
        }

        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Invalid username or password.");
      }

      const payload = await response.json();
      setCurrentUser(payload.user || null);
      setCsrfToken(payload.csrf_token || "");
      resetRadioBrowserView();
      updateAuthUi();
      await loadDashboard();
    } catch (error) {
      setCurrentUser(null);
      setCsrfToken("");
      updateAuthUi();
      authMessageNode.hidden = false;
      authMessageNode.textContent = error instanceof Error ? error.message : String(error);
    }
  }

  async function logout() {
    try {
      await apiFetch("/api/auth/logout", {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      });
    } finally {
      stopPlayback();
      setCurrentUser(null);
      publicStatsController.reset();
      resetRadioBrowserView();
      updateAuthUi();
      renderAuthRequired();
    }
  }

  return {
    loadAuthState,
    login,
    logout,
  };
}
