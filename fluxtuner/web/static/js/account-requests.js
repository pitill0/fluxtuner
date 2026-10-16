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
  apiFetch,
  authMessageNode,
  fetchImpl = fetch,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  recoveryCodesRegenerateDialog,
  recoveryCodesRegenerateForm,
  recoveryCodesRegenerateMessageNode,
  recoveryCodesDialog,
  recoveryCodesListNode,
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

  function setRecoveryCodesRegenerateMessage(message) {
    if (recoveryCodesRegenerateMessageNode) {
      recoveryCodesRegenerateMessageNode.textContent = message || "";
    }
  }

  function openRecoveryCodeRegenerationDialog() {
    if (!recoveryCodesRegenerateDialog) return;

    setRecoveryCodesRegenerateMessage("");
    recoveryCodesRegenerateDialog.hidden = false;
    focusFirstDialogControl(recoveryCodesRegenerateDialog);
  }

  function closeRecoveryCodeRegenerationDialog() {
    if (!recoveryCodesRegenerateDialog) return;

    recoveryCodesRegenerateDialog.hidden = true;
    setRecoveryCodesRegenerateMessage("");

    if (recoveryCodesRegenerateForm) {
      recoveryCodesRegenerateForm.reset();
    }
  }

  function closeRecoveryCodesDialog() {
    if (!recoveryCodesDialog) return;

    recoveryCodesDialog.hidden = true;
    if (recoveryCodesListNode) {
      recoveryCodesListNode.replaceChildren();
    }
  }

  function showRecoveryCodes(codes) {
    if (!recoveryCodesDialog || !recoveryCodesListNode) return;
    if (!Array.isArray(codes) || !codes.length) return;

    recoveryCodesListNode.replaceChildren();

    codes.forEach((code) => {
      const item = document.createElement("li");
      const codeNode = document.createElement("code");
      codeNode.textContent = String(code);
      item.append(codeNode);
      recoveryCodesListNode.append(item);
    });

    recoveryCodesDialog.hidden = false;
    recoveryCodesDialog
      .querySelector("[data-recovery-codes-close]")
      ?.focus();
  }

  async function regenerateRecoveryCodes(event) {
    event.preventDefault();

    if (!recoveryCodesRegenerateForm || !apiFetch) return;

    const formData = new FormData(recoveryCodesRegenerateForm);
    const currentPassword = String(formData.get("current_password") || "");

    setRecoveryCodesRegenerateMessage("Generating recovery codes...");

    try {
      const response = await apiFetch("/api/auth/recovery-codes/regenerate", {
        method: "POST",
        handleUnauthorized: false,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Could not generate recovery codes.");
      }

      closeRecoveryCodeRegenerationDialog();
      showRecoveryCodes(payload.recovery_codes);
    } catch (error) {
      setRecoveryCodesRegenerateMessage(errorMessage(error));
    }
  }

  async function recoverPassword(event) {
    event.preventDefault();

    if (!passwordChangeForm || !authMessageNode) return;

    const formData = new FormData(passwordChangeForm);
    const username = String(formData.get("username") || "").trim();
    const recoveryCode = String(formData.get("recovery_code") || "").trim();
    const newPassword = String(formData.get("new_password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (newPassword !== confirmPassword) {
      setPasswordChangeMessage("Passwords do not match.");
      return;
    }

    setPasswordChangeMessage("Recovering account...");

    try {
      const response = await fetchImpl("/api/auth/recover-password", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          recovery_code: recoveryCode,
          new_password: newPassword,
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "Could not recover account.");
      }

      closePasswordChangeDialog();
      authMessageNode.hidden = false;
      authMessageNode.textContent =
        "Password updated. Sign in with your new password.";

      showRecoveryCodes(payload.recovery_codes);
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
    closeRecoveryCodeRegenerationDialog,
    closeRecoveryCodesDialog,
    closeRegisterDialog,
    openPasswordChangeDialog,
    openRecoveryCodeRegenerationDialog,
    openRegisterDialog,
    recoverPassword,
    regenerateRecoveryCodes,
    registerAccount,
    showRecoveryCodes,
  };
}
