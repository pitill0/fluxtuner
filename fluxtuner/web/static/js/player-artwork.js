/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

// The player receives artwork separately from the persistent station payload.
// Never accept an arbitrary image URL or copy signed references into history.
export function createPlayerArtworkController({ imageNode, fallbackNode }) {
  function clear() {
    if (fallbackNode) fallbackNode.textContent = "♫";
    if (imageNode) {
      imageNode.hidden = true;
      imageNode.removeAttribute("src");
    }
  }

  if (imageNode) {
    imageNode.addEventListener("error", () => { imageNode.hidden = true; });
    imageNode.addEventListener("load", () => { imageNode.hidden = false; });
  }

  function show(stationTitle, reference) {
    const initial = String(stationTitle || "").trim().charAt(0).toUpperCase() || "♫";
    if (fallbackNode) fallbackNode.textContent = initial;
    if (!imageNode) return;

    const token = typeof reference === "string" ? reference : "";
    if (token.length > 4096 || !/^v1\.[0-9]+\.[A-Za-z0-9_-]+\.[a-f0-9]{64}$/.test(token)) {
      imageNode.hidden = true;
      imageNode.removeAttribute("src");
      return;
    }

    imageNode.hidden = false;
    imageNode.setAttribute("src", `/api/artwork/${encodeURIComponent(token)}`);
    if (imageNode.complete && imageNode.naturalWidth === 0) imageNode.hidden = true;
  }

  clear();
  return { clear, show };
}
