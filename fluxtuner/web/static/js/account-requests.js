/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function focusFirstDialogControl(dialogNode) {
  if (!dialogNode) return;

  const firstInput = dialogNode.querySelector("input, button");
  if (firstInput) {
    firstInput.focus();
  }
}

export function createAccountRequestsController({
  authMessageNode,
  fetchImpl = fetch,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  registerDialog,
  registerForm,
  registerMessageNode,
}) {
  function setPasswordChangeMessage(message) {
    if (passwordChangeMessageNode) {
      passwordChangeMessageNode.textContent = message || "";
    }
  }

  function openPasswordChangeDialog() {
    if (!passwordChangeDialog) return;

    setPasswordChangeMessage("");
    passwordChangeDialog.hidden = false;
    focusFirstDialogControl(passwordChangeDialog);
  }

  function closePasswordChangeDialog() {
    if (!passwordChangeDialog) return;

    passwordChangeDialog.hidden = true;
    setPasswordChangeMessage("");

    if (passwordChangeForm) {
      passwordChangeForm.reset();
    }
  }

  async function requestPasswordChange(event) {
    event.preventDefault();

    if (!passwordChangeForm || !authMessageNode) return;

    const formData = new FormData(passwordChangeForm);
    const username = String(formData.get("username") || "").trim();
    const newPassword = String(formData.get("new_password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const note = String(formData.get("note") || "").trim();

    if (newPassword !== confirmPassword) {
      setPasswordChangeMessage("Passwords do not match.");
      return;
    }

    setPasswordChangeMessage("Requesting password change...");

    try {
      const response = await fetchImpl("/api/auth/password-change-requests", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          new_password: newPassword,
          note,
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Could not request password change.");
      }

      closePasswordChangeDialog();
      authMessageNode.hidden = false;
      authMessageNode.textContent = payload.message || "Password change request received.";
    } catch (error) {
      setPasswordChangeMessage(errorMessage(error));
    }
  }

  function setRegisterMessage(message) {
    if (registerMessageNode) {
      registerMessageNode.textContent = message || "";
    }
  }

  function openRegisterDialog() {
    if (!registerDialog) return;

    setRegisterMessage("");
    registerDialog.hidden = false;
    focusFirstDialogControl(registerDialog);
  }

  function closeRegisterDialog() {
    if (!registerDialog) return;

    registerDialog.hidden = true;
    setRegisterMessage("");

    if (registerForm) {
      registerForm.reset();
    }
  }

  async function registerAccount(event) {
    event.preventDefault();

    if (!registerForm || !authMessageNode) return;

    const formData = new FormData(registerForm);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");
    const displayName = String(formData.get("display_name") || "").trim();
    const note = String(formData.get("note") || "").trim();

    setRegisterMessage("Requesting account...");

    try {
      const response = await fetchImpl("/api/auth/register", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
          display_name: displayName,
          note,
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Could not request account.");
      }

      closeRegisterDialog();
      authMessageNode.hidden = false;
      authMessageNode.textContent = payload.message || "Account request received.";
    } catch (error) {
      setRegisterMessage(errorMessage(error));
    }
  }

  return {
    closePasswordChangeDialog,
    closeRegisterDialog,
    openPasswordChangeDialog,
    openRegisterDialog,
    registerAccount,
    requestPasswordChange,
  };
}
