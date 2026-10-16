/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

function setAdminUserDangerFeedback(button, message) {
  const feedbackNode = button
    ?.closest(".admin-user-danger-zone")
    ?.querySelector("[data-admin-user-danger-feedback]");

  if (feedbackNode) {
    feedbackNode.textContent = message || "";
  }
}

function adminUserActionButton(action, username, label) {
  return `<button type="button" data-admin-user-action="${action}" data-admin-username="${username}">${label}</button>`;
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
  apiFetch,
  usersNode,
  messageNode,
  createUserForm,
  passwordForm,
  getCurrentUser,
  loadDashboard,
}) {
  let usersLoaded = false;

  function currentUser() {
    return getCurrentUser?.() || null;
  }

  function setMessage(message) {
    if (messageNode) {
      messageNode.textContent = message || "";
    }
  }

  function reset() {
    usersLoaded = false;

    if (messageNode) {
      messageNode.textContent = "";
    }

    if (usersNode) {
      usersNode.innerHTML = '<p class="empty">Admin users will appear here.</p>';
    }

  }

  function renderUsers(users) {
    if (!usersNode) return;

    if (!users.length) {
      usersNode.innerHTML = '<p class="empty">No web users found.</p>';
      return;
    }

    usersNode.innerHTML = `
      <div class="admin-users-table" role="table" aria-label="Web users">
        <div class="admin-users-row admin-users-head" role="row">
          <span role="columnheader">User</span>
          <span role="columnheader">Admin</span>
          <span role="columnheader">Active</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Actions</span>
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
              ? `<small class="admin-user-danger-note">You cannot delete your own user.</small>`
              : `<button type="button" data-admin-user-action="delete" data-admin-username="${username}">Delete user</button>`;
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
                  <span class="admin-cell-label" aria-hidden="true">Admin</span>
                  <span>${adminLabel}</span>
                </span>
                <span role="cell" data-cell-label="Active">
                  <span class="admin-cell-label" aria-hidden="true">Active</span>
                  <span>${activeLabel}</span>
                </span>
                <span role="cell" data-cell-label="Status">
                  <span class="admin-cell-label" aria-hidden="true">Status</span>
                  <span>${approvalStatus}</span>
                </span>
                <span class="admin-user-actions" role="cell" data-cell-label="Actions">
                  <div class="admin-user-actions-normal">
                    ${userActions}
                  </div>
                  <details class="admin-user-danger-zone">
                    <summary>${dangerTitle}</summary>
                    <div>
                      <strong>${dangerDescription}</strong>
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
  }

  async function loadUsers() {
    const user = currentUser();
    if (!user || !user.is_admin) return;

    setMessage("Loading users...");

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
      setMessage(`${payload.count ?? 0} web user(s).`);
    } catch (error) {
      setMessage(String(error));
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
      setMessage("Passwords do not match.");
      return;
    }

    setMessage("Creating user...");

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

      setMessage("User created.");
      await loadUsers();
    } catch (error) {
      setMessage(String(error));
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
      setMessage("Passwords do not match.");
      return;
    }

    setMessage("Updating password...");

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

      setMessage("Password updated. Active sessions for that user were revoked.");
      await loadUsers();
    } catch (error) {
      setMessage(String(error));
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
      const confirmation = window.prompt(
        `This permanently deletes ${username} and all related data. Type "${expectedConfirmation}" to continue.`,
      );

      if (confirmation !== expectedConfirmation) {
        const message = confirmation === null
          ? "User deletion cancelled."
          : `Confirmation did not match. Type exactly: ${expectedConfirmation}`;
        setMessage(message);
        setAdminUserDangerFeedback(button, message);
        return;
      }
    }

    setMessage(action === "delete" ? "Deleting user..." : "Updating user...");
    if (action === "delete") {
      setAdminUserDangerFeedback(button, "Deleting user...");
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

      setMessage(action === "delete" ? "User deleted." : "User updated.");
      if (action === "delete") {
        setAdminUserDangerFeedback(button, "User deleted.");
      }
      await loadUsers();
      await loadDashboard({ preserveView: true, silent: true });
    } catch (error) {
      setMessage(String(error));
      if (action === "delete") {
        setAdminUserDangerFeedback(button, String(error));
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
