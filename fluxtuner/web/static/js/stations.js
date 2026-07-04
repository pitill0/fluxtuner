/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };

    return replacements[char];
  });
}

export function safeExternalUrl(value) {
  const rawUrl = String(value || "").trim();
  if (!rawUrl) return "";

  if (!/^https?:\/\//i.test(rawUrl)) return "";

  try {
    const parsed = new URL(rawUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) return "";
    return parsed.href;
  } catch {
    return "";
  }
}

export function stationUrl(station) {
  return safeExternalUrl(station.url_resolved || station.url || "");
}

export function stationHomepage(station) {
  return safeExternalUrl(station.homepage || "");
}

export function stationTags(station) {
  const tags = String(station.tags || "").trim();
  if (!tags) return "";
  return tags.split(",").slice(0, 8).join(", ");
}

export function stationButtonPayload(station) {
  return escapeHtml(JSON.stringify(station));
}
