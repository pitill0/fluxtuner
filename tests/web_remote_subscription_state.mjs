import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(
  new URL("../fluxtuner/web/static/js/remote-subscriptions.js",
    import.meta.url),
  "utf8",
);

const moduleUrl = `data:text/javascript;base64,${
  Buffer.from(source).toString("base64")
}`;

const { createRemoteSubscriptionController } =
  await import(moduleUrl);

function createDocument() {
  const document = {};

  document.createElement = () => {
    const node = {
      ownerDocument: document,
      textContent: "",
      value: "",
      hidden: false,
      disabled: false,
      open: false,
      children: [],
      listeners: {},

      addEventListener(type, callback) {
        this.listeners[type] = callback;
      },

      append(...children) {
        this.children.push(...children);
      },

      replaceChildren(...children) {
        this.children = [...children];
      },

      showModal() {
        this.open = true;
      },

      close() {
        this.open = false;
        this.listeners.close?.();
      },
    };

    return node;
  };

  return document;
}

function setup() {
  const document = createDocument();
  const node = () => document.createElement();

  const elements = {
    dialog: node(),
    openButton: node(),
    closeButton: node(),
    form: node(),
    urlInput: node(),
    nameInput: node(),
    listNode: node(),
    messageNode: node(),
    previewNode: node(),
    confirmButton: node(),
  };

  let subscriptions = [];
  let nextError = null;
  let currentUser = { id: 1 };
  let session = "session-one";

  const calls = [];

  const apiFetch = async (path, options = {}) => {
    calls.push({ path, options });
    const method = options.method || "GET";

    if (nextError) {
      const detail = nextError;
      nextError = null;
      return {
        ok: false,
        json: async () => ({ detail }),
      };
    }

    let payload = {};

    if (method === "GET") {
      payload = { subscriptions };
    } else if (
      method === "POST" &&
      path === "/api/stations/subscriptions"
    ) {
      subscriptions = [
        { source_id: 1, revision: 1 },
      ];
      payload = {
        status: "ok",
        source_id: 1,
        revision: 1,
        stations: 53,
      };
    } else if (path.endsWith("/preview")) {
      payload = {
        not_modified: true,
        revision: 1,
      };
    } else if (method === "DELETE") {
      subscriptions = [];
      payload = { status: "ok" };
    }

    return {
      ok: true,
      json: async () => payload,
    };
  };

  const controller = createRemoteSubscriptionController({
    elements,
    apiFetch,
    getCurrentUser: () => currentUser,
    getSessionKey: () => session,
    confirmDelete: () => true,
  });

  controller.bind();

  return {
    elements,
    controller,
    calls,
    failNext(message) {
      nextError = message;
    },
    changeSession() {
      currentUser = { id: 2 };
      session = "session-two";
      controller.syncSession();
    },
  };
}

function actionButtons(elements) {
  return elements.listNode.children.flatMap(
    (container) => container.children
      .filter((child) => child.className === "subscription-actions")
      .flatMap((actions) => actions.children)
      .filter((child) =>
        child.textContent === "Check updates" ||
        child.textContent === "Unsubscribe"
      ),
  );
}

// Opening an existing or empty list must not leave Working... visible.
{
  const { controller, elements } = setup();
  await controller.openDialog();

  assert.equal(elements.dialog.open, true);
  assert.equal(elements.messageNode.textContent, "");
  assert.equal(elements.confirmButton.disabled, false);
}

// A successful create must restore both action buttons.
{
  const { controller, elements, calls } = setup();

  await controller.openDialog();

  elements.urlInput.value = "https://example.org/test.m3u";
  elements.nameInput.value = "My radio collection";

  await elements.form.listeners.submit({
    preventDefault() {},
  });

  assert.equal(
    elements.messageNode.textContent,
    "Subscription added.",
  );

  assert.equal(elements.urlInput.value, "");
  assert.equal(elements.nameInput.value, "");

  const creation = calls.find(({ path, options }) =>
    path === "/api/stations/subscriptions" &&
    options.method === "POST"
  );
  assert.ok(creation, "Subscription creation request missing");
  assert.deepEqual(JSON.parse(creation.options.body), {
    url: "https://example.org/test.m3u",
    display_name: "My radio collection",
  });

  const buttons = actionButtons(elements);
  assert.equal(buttons.length, 2);
  assert.ok(buttons.every((button) => !button.disabled));

  await controller.preview(1);

  assert.equal(
    elements.messageNode.textContent,
    "Catalog is already up to date.",
  );
  assert.ok(actionButtons(elements).every(
    (button) => !button.disabled
  ));
}

// HTTP errors must be visible and leave the UI usable.
{
  const { controller, elements, failNext } = setup();

  await controller.openDialog();

  failNext("Could not retrieve the remote collection.");

  elements.urlInput.value = "https://example.org/failure.m3u";

  await elements.form.listeners.submit({
    preventDefault() {},
  });

  assert.equal(
    elements.messageNode.textContent,
    "Could not retrieve the remote collection.",
  );

  assert.equal(elements.confirmButton.disabled, false);

  // Retry must be possible after the error.
  await elements.form.listeners.submit({
    preventDefault() {},
  });

  assert.equal(
    elements.messageNode.textContent,
    "Subscription added.",
  );
  assert.ok(actionButtons(elements).every(
    (button) => !button.disabled
  ));
}

// Session changes must invalidate the previous dialog.
{
  const { controller, elements, changeSession } = setup();

  await controller.openDialog();
  changeSession();

  assert.equal(elements.dialog.open, false);
  assert.equal(elements.messageNode.textContent, "");
}

console.log("PASS: remote subscription UI state regressions");
