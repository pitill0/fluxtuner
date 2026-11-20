/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

const STORAGE_KEY = "fluxtuner.discovery.selection.v1";
const MAX_AGE_MS = 15 * 60 * 1000;

export function discoverySessionStorage() {
  try { return window.sessionStorage; } catch (_error) { return null; }
}

export function createDiscoveryPendingController({ storage, now = Date.now, apiFetch }) {
  let redeeming = false;

  function clear() {
    try { storage?.removeItem(STORAGE_KEY); } catch (_error) { /* Storage may be unavailable. */ }
  }

  function read() {
    let pending;
    try { pending = JSON.parse(storage?.getItem(STORAGE_KEY) || "null"); }
    catch (_error) { clear(); return null; }
    if (!pending || typeof pending.selection !== "string" ||
        !/^v1\.[0-9]{10}\.[A-Za-z0-9_-]{43}$/.test(pending.selection) ||
        !Number.isFinite(pending.savedAt) || pending.savedAt > now() ||
        now() - pending.savedAt >= MAX_AGE_MS) {
      clear();
      return null;
    }
    return pending.selection;
  }

  function select(reference) {
    if (typeof reference !== "string" ||
        !/^v1\.[0-9]{10}\.[A-Za-z0-9_-]{43}$/.test(reference)) return false;
    if (!storage) return false;
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify({ selection: reference, savedAt: now() }));
      return storage.getItem(STORAGE_KEY) !== null;
    } catch (_error) { return false; }
  }

  async function redeem() {
    if (redeeming) return null;
    const selection = read();
    if (!selection) return null;
    redeeming = true;
    try {
      const response = await apiFetch("/api/public/featured/redeem", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ selection }),
      });
      if (response.status === 401) return null;
      if (!response.ok) {
        clear();
        return { ok: false, expired: response.status === 404, limited: response.status === 429 };
      }
      const result = await response.json();
      clear();
      return { ok: true, added: Boolean(result.added) };
    } catch (_error) {
      // A transient network failure can be retried, subject to the local TTL.
      return { ok: false, network: true };
    } finally { redeeming = false; }
  }

  return { clear, read, select, redeem };
}
