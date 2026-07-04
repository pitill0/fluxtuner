/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const CSRF_HEADER_NAME = "X-FluxTuner-CSRF";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function createApiFetch({ getCsrfToken, onUnauthorized } = {}) {
  return async function apiFetch(url, options = {}) {
    const requestOptions = { ...options };
    const method = String(requestOptions.method || "GET").toUpperCase();
    const csrfToken = typeof getCsrfToken === "function" ? getCsrfToken() : "";

    if (!SAFE_METHODS.has(method) && csrfToken) {
      requestOptions.headers = {
        ...(requestOptions.headers || {}),
        [CSRF_HEADER_NAME]: csrfToken,
      };
    }

    const response = await fetch(url, requestOptions);

    if (response.status === 401 && typeof onUnauthorized === "function") {
      onUnauthorized();
    }

    return response;
  };
}
