import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "fluxtuner-ux03-"));

try {
  const moduleSource = fs.readFileSync(
    path.join(root, "fluxtuner/web/static/js/unified-library.js"),
    "utf8",
  );

  fs.writeFileSync(
    path.join(temp, "unified-library.mjs"),
    moduleSource,
  );

  const { createUnifiedLibraryController } = await import(
    pathToFileURL(path.join(temp, "unified-library.mjs")).href
  );

  let view = "";
  let user = { id: 1 };
  let resolveRequest;
  let rendered = null;

  function node() {
    return {
      textContent: "",
      innerHTML: "",
      children: [],
      ownerDocument: {
        createElement() {
          return { className: "", textContent: "" };
        },
      },
      replaceChildren() {
        this.children = [];
      },
      append(item) {
        this.children.push(item);
      },
    };
  }

  const controller = createUnifiedLibraryController({
    apiFetch: () => new Promise((resolve) => {
      resolveRequest = resolve;
    }),
    getCurrentUser: () => user,
    getCurrentView: () => view,
    isLibraryVisible: () => true,
    setLibraryView: (next) => { view = next; },
    setResultsHeader: () => {},
    resultsNode: node(),
    resultCountNode: node(),
    renderResults: (payload) => { rendered = payload; },
    renderSearchError: (error) => { throw error; },
    onOpenCatalog: () => {},
    onManageCatalogs: () => {},
  });

  const pending = controller.loadMyStations();
  assert.equal(view, "stations");

  user = { id: 2 };
  resolveRequest({
    ok: true,
    json: async () => ({ count: 1, stations: [{ name: "Old" }] }),
  });
  await pending;
  assert.equal(rendered, null, "Stale user response must be ignored");

  const next = controller.loadMyStations();
  resolveRequest({
    ok: true,
    json: async () => ({ count: 1, stations: [{ name: "Current" }] }),
  });
  await next;
  assert.equal(rendered.stations[0].name, "Current");

  const obsolete = controller.loadMyStations();
  controller.invalidate();
  resolveRequest({
    ok: true,
    json: async () => ({ count: 1, stations: [{ name: "Obsolete" }] }),
  });
  await obsolete;
  assert.equal(rendered.stations[0].name, "Current");

  console.log("PASS: unified library loading and stale response guards");
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
