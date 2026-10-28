import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const temp = fs.mkdtempSync(
  path.join(os.tmpdir(), "fluxtuner-catalog-notify-"),
);

try {
  const source = fs.readFileSync(
    "fluxtuner/web/static/js/remote-subscriptions.js",
    "utf8",
  );
  const modulePath = path.join(temp, "remote-subscriptions.mjs");
  fs.writeFileSync(modulePath, source);

  const { createRemoteSubscriptionController } = await import(
    pathToFileURL(modulePath).href
  );

  async function scenario(postSucceeds) {
    const handlers = new Map();
    const notifications = [];
    const user = { id: 1 };

    const element = () => ({
      disabled: false,
      hidden: false,
      textContent: "",
      value: "",
      addEventListener(type, callback) {
        handlers.set(this, { type, callback });
      },
    });

    const dialog = {
      open: false,
      showModal() { this.open = true; },
      close() { this.open = false; },
      addEventListener() {},
    };

    const form = element();
    const elements = {
      dialog,
      form,
      openButton: element(),
      confirmButton: element(),
      closeButton: element(),
      urlInput: element(),
      previewNode: element(),
      messageNode: element(),
      listNode: {
        ownerDocument: { createElement: element },
        replaceChildren() {},
        append() {},
      },
    };

    elements.urlInput.value = "https://example.org/list.m3u";

    const apiFetch = async (_url, options) => {
      if (options.method === "POST") {
        return {
          ok: postSucceeds,
          json: async () => postSucceeds
            ? { source_id: 7 }
            : { detail: "Creation failed." },
        };
      }
      throw new Error("List refresh failed.");
    };

    const controller = createRemoteSubscriptionController({
      elements,
      apiFetch,
      getCurrentUser: () => user,
      getSessionKey: () => "session-a",
      beforeOpen: () => {},
      onChanged: (event) => notifications.push(event),
    });

    controller.bind();

    const registration = handlers.get(form);
    assert.equal(registration?.type, "submit");
    const submit = registration.callback;
    assert.equal(typeof submit, "function");

    await submit({ preventDefault() {} });

    assert.deepEqual(
      notifications,
      postSucceeds ? [{ type: "added" }] : [],
      "Notification must reflect a successful mutation, not list refresh",
    );
  }

  await scenario(true);
  await scenario(false);

  console.log("PASS: catalog mutation notification contract");
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
