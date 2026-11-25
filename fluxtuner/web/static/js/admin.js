/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { knownApiErrorKey } from "./api.js";
import { escapeHtml } from "./stations.js";

function adminUserActionButton(action, username, label) {
  return `<button type="button" data-admin-user-action="${action}" data-admin-username="${username}" data-render-i18n="admin.action.${action}">${label}</button>`;
}

function adminUserActions(user, username, isCurrentUser = false) {
  const approvalStatus = String(user.approval_status || "approved").toLowerCase();
  const isPending = approvalStatus === "pending";
  const isApproved = approvalStatus === "approved";
  const actions = [];

  if (isPending) {
    actions.push(adminUserActionButton("approve", username, "Approve"));
    actions.push(adminUserActionButton("reject", username, "Reject"));
  } else if (user.is_active && isApproved) {
    actions.push(adminUserActionButton("deactivate", username, "Deactivate"));
  } else {
    actions.push(adminUserActionButton("activate", username, "Activate"));
  }

  if (user.is_admin) {
    if (!isCurrentUser) {
      actions.push(adminUserActionButton("revoke-admin", username, "Revoke admin"));
    }
  } else {
    actions.push(adminUserActionButton("grant-admin", username, "Grant admin"));
  }

  return actions.join("");
}

export function createAdminController({
  presentation,
  apiFetch,
  usersNode,
  messageNode,
  createUserForm,
  passwordForm,
  getCurrentUser,
  loadDashboard,
}) {
  function presentMessage(node, message, key, params = {}) {
    if (!node) return;
    if (key && presentation) presentation.present(node, key, message, "textContent", params);
    else {
      presentation?.clear(node);
      node.textContent = message || "";
    }
  }

  let usersLoaded = false;

  function currentUser() {
    return getCurrentUser?.() || null;
  }

  function setMessage(message, key, params) {
    if (messageNode) {
      presentMessage(messageNode, message, key, params);
    }
  }

  function reset() {
    usersLoaded = false;

    if (messageNode) {
      presentMessage(messageNode, "");
    }

    if (usersNode) {
      usersNode.innerHTML = '<p class="empty" data-render-i18n="admin.users_empty">Admin users will appear here.</p>';
      presentation?.bindRendered(usersNode);
    }

  }

  function renderUsers(users) {
    if (!usersNode) return;

    if (!users.length) {
      usersNode.innerHTML = '<p class="empty" data-render-i18n="admin.no_users">No web users found.</p>';
      presentation?.bindRendered(usersNode);
      return;
    }

    usersNode.innerHTML = `
      <div class="admin-users-table" role="table" aria-label="Web users" data-render-aria="admin.table">
        <div class="admin-users-row admin-users-head" role="row">
          <span role="columnheader" data-render-i18n="admin.column.user">User</span>
          <span role="columnheader" data-render-i18n="admin.column.admin">Admin</span>
          <span role="columnheader" data-render-i18n="admin.column.active">Active</span>
          <span role="columnheader" data-render-i18n="admin.column.status">Status</span>
          <span role="columnheader" data-render-i18n="admin.column.actions">Actions</span>
        </div>
        ${users
          .map((user) => {
            const username = escapeHtml(user.username || "");
            const displayName = escapeHtml(user.display_name || user.username || "");
            const adminLabel = user.is_admin ? "yes" : "no";
            const activeLabel = user.is_active ? "yes" : "no";
            const approvalStatus = escapeHtml(user.approval_status || "approved");
            const isCurrentUser = currentUser()?.username === user.username;
            const userActions = adminUserActions(user, username, isCurrentUser);
            const deleteAction = isCurrentUser
              ? `<small class="admin-user-danger-note" data-render-i18n="admin.protected_note">You cannot delete your own user.</small>`
              : `<button type="button" data-admin-user-action="delete" data-admin-username="${username}" data-render-i18n="admin.action.delete">Delete user</button>`;
            const dangerTitle = isCurrentUser ? "Protected user" : "Danger zone";
            const dangerDescription = isCurrentUser
              ? "The current signed-in user cannot be deleted."
              : "Deleting a user is permanent and cannot be undone.";

            return `
              <div class="admin-users-row" role="row">
                <span role="cell" data-cell-label="User">
                  <strong>${displayName}</strong>
                  <small>${username}</small>
                </span>
                <span role="cell" data-cell-label="Admin">
                  <span class="admin-cell-label" aria-hidden="true" data-render-i18n="admin.column.admin">Admin</span>
                  <span data-render-i18n="admin.${adminLabel}">${adminLabel}</span>
                </span>
                <span role="cell" data-cell-label="Active">
                  <span class="admin-cell-label" aria-hidden="true" data-render-i18n="admin.column.active">Active</span>
                  <span data-render-i18n="admin.${activeLabel}">${activeLabel}</span>
                </span>
                <span role="cell" data-cell-label="Status">
                  <span class="admin-cell-label" aria-hidden="true" data-render-i18n="admin.column.status">Status</span>
                  <span${["pending", "approved", "rejected", "disabled"].includes(user.approval_status || "approved") ? ` data-render-i18n="${approvalStatus === "rejected" ? "status.admin.rejected" : `status.${approvalStatus}`}"` : ""}>${approvalStatus}</span>
                </span>
                <span class="admin-user-actions" role="cell" data-cell-label="Actions">
                  <div class="admin-user-actions-normal">
                    ${userActions}
                  </div>
                  <details class="admin-user-danger-zone">
                    <summary data-render-i18n="${isCurrentUser ? "admin.protected" : "admin.danger"}">${dangerTitle}</summary>
                    <div>
                      <strong data-render-i18n="${isCurrentUser ? "admin.protected_description" : "admin.danger_description"}">${dangerDescription}</strong>
                      ${deleteAction}
                      <small class="admin-user-danger-feedback" data-admin-user-danger-feedback></small>
                    </div>
                  </details>
                </span>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
    presentation?.bindRendered(usersNode);
  }

  async function loadUsers() {
    const user = currentUser();
    if (!user || !user.is_admin) return;

    setMessage("Loading users...", "admin.loading");

    try {
      const response = await apiFetch("/api/admin/users", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not load users.");
      }

      const payload = await response.json();
      usersLoaded = true;
      renderUsers(payload.users || []);
      setMessage(`${payload.count ?? 0} web user(s).`, "admin.users_count", { count: payload.count ?? 0 });
    } catch (error) {
      setMessage(String(error), knownApiErrorKey(error instanceof Error ? error.message : String(error)));
    }
  }

  async function loadUsersIfNeeded() {
    if (usersLoaded) return;

    usersLoaded = true;
    await loadUsers();
  }

  async function createUser(event) {
    event.preventDefault();

    if (!createUserForm) return;

    const formData = new FormData(createUserForm);
    const username = String(formData.get("username") || "").trim();
    const displayName = String(formData.get("display_name") || "").trim();
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const isAdmin = formData.get("is_admin") === "on";

    if (password !== confirmPassword) {
      setMessage("Passwords do not match.", "account.password_mismatch");
      return;
    }

    setMessage("Creating user...", "admin.creating");

    try {
      const response = await apiFetch("/api/admin/users", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          display_name: displayName,
          password,
          is_admin: isAdmin,
          is_active: true,
        }),
      });

      createUserForm.reset();

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not create user.");
      }

      setMessage("User created.", "admin.created");
      await loadUsers();
    } catch (error) {
      setMessage(String(error), knownApiErrorKey(error instanceof Error ? error.message : String(error)));
    }
  }

  async function setUserPassword(event) {
    event.preventDefault();

    if (!passwordForm) return;

    const formData = new FormData(passwordForm);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (password !== confirmPassword) {
      setMessage("Passwords do not match.", "account.password_mismatch");
      return;
    }

    setMessage("Updating password...", "admin.updating_password");

    try {
      const response = await apiFetch(
        `/api/admin/users/${encodeURIComponent(username)}/password`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ password }),
        },
      );

      passwordForm.reset();

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not update password.");
      }

      setMessage("Password updated. Active sessions for that user were revoked.", "admin.password_updated");
      await loadUsers();
    } catch (error) {
      setMessage(String(error), knownApiErrorKey(error instanceof Error ? error.message : String(error)));
    }
  }

  async function mutateUser(username, action, button = null) {
    const encodedUsername = encodeURIComponent(username);
    const routes = {
      activate: {
        method: "POST",
        url: `/api/admin/users/${encodedUsername}/activate`,
      },
      deactivate: {
        method: "POST",
        url: `/api/admin/users/${encodedUsername}/deactivate`,
      },
      approve: {
        method: "POST",
        url: `/api/admin/users/${encodedUsername}/approve`,
      },
      reject: {
        method: "POST",
        url: `/api/admin/users/${encodedUsername}/reject`,
      },
      "grant-admin": {
        method: "POST",
        url: `/api/admin/users/${encodedUsername}/admin`,
      },
      "revoke-admin": {
        method: "DELETE",
        url: `/api/admin/users/${encodedUsername}/admin`,
      },
      delete: {
        method: "DELETE",
        url: `/api/admin/users/${encodedUsername}`,
      },
    };

    const route = routes[action];
    if (!route) return;

    if (action === "delete") {
      const expectedConfirmation = `DELETE ${username}`;
      const promptText = `This permanently deletes ${username} and all related data. Type "${expectedConfirmation}" to continue.`;
      const confirmation = window.prompt(presentation?.translate("admin.confirm_delete", promptText, {
        username, confirmation: expectedConfirmation,
      }) ?? promptText);

      if (confirmation !== expectedConfirmation) {
        const message = confirmation === null
          ? "User deletion cancelled."
          : `Confirmation did not match. Type exactly: ${expectedConfirmation}`;
        const key = confirmation === null ? "admin.cancelled" : "admin.confirm_mismatch";
        const params = { confirmation: expectedConfirmation };
        setMessage(message, key, params);
        presentMessage(button?.closest(".admin-user-danger-zone")?.querySelector("[data-admin-user-danger-feedback]"), message, key, params);
        return;
      }
    }

    if (action === "delete") setMessage("Deleting user...", "admin.deleting");
    else setMessage("Updating user...", "admin.updating");
    if (action === "delete") {
      presentMessage(button?.closest(".admin-user-danger-zone")?.querySelector("[data-admin-user-danger-feedback]"), "Deleting user...", "admin.deleting");
    }

    try {
      const response = await apiFetch(route.url, {
        method: route.method,
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Could not update user.");
      }

      if (action === "delete") setMessage("User deleted.", "admin.deleted");
    else setMessage("User updated.", "admin.updated");
      if (action === "delete") {
        presentMessage(button?.closest(".admin-user-danger-zone")?.querySelector("[data-admin-user-danger-feedback]"), "User deleted.", "admin.deleted");
      }
      await loadUsers();
      await loadDashboard({ preserveView: true, silent: true });
    } catch (error) {
      setMessage(String(error), knownApiErrorKey(error instanceof Error ? error.message : String(error)));
      if (action === "delete") {
        presentMessage(button?.closest(".admin-user-danger-zone")?.querySelector("[data-admin-user-danger-feedback]"), String(error), knownApiErrorKey(error instanceof Error ? error.message : String(error)));
      }
    }
  }

  return {
    createUser,
    loadUsers,
    loadUsersIfNeeded,
    mutateUser,
    reset,
    setUserPassword,
  };
}
