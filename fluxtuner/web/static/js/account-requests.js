/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { knownApiErrorKey } from "./api.js";

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
  presentation,
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
  function presentMessage(node, message, key, params = {}) {
    if (!node) return;
    if (key && presentation) presentation.present(node, key, message, "textContent", params);
    else {
      presentation?.clear(node);
      node.textContent = message || "";
    }
  }

  function setPasswordChangeMessage(message, key) {
    if (passwordChangeMessageNode) {
      presentMessage(passwordChangeMessageNode, message, key);
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

  function setRecoveryCodesRegenerateMessage(message, key) {
    if (recoveryCodesRegenerateMessageNode) {
      presentMessage(recoveryCodesRegenerateMessageNode, message, key);
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

    setRecoveryCodesRegenerateMessage("Generating recovery codes...", "account.generating_codes");

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
      const message = errorMessage(error);
      setRecoveryCodesRegenerateMessage(message, knownApiErrorKey(message));
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
      setPasswordChangeMessage("Passwords do not match.", "account.password_mismatch");
      return;
    }

    setPasswordChangeMessage("Recovering account...", "account.recovering");

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
      presentMessage(authMessageNode, "Password updated. Sign in with your new password.", "account.password_recovered");

      showRecoveryCodes(payload.recovery_codes);
    } catch (error) {
      const message = errorMessage(error);
      setPasswordChangeMessage(message, knownApiErrorKey(message));
    }
  }

  function setRegisterMessage(message, key) {
    if (registerMessageNode) {
      presentMessage(registerMessageNode, message, key);
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

    setRegisterMessage("Requesting account...", "account.requesting");

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
      if (payload.message) presentMessage(authMessageNode, payload.message);
      else presentMessage(authMessageNode, "Account request received.", "account.request_received");
    } catch (error) {
      const message = errorMessage(error);
      setRegisterMessage(message, knownApiErrorKey(message));
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
