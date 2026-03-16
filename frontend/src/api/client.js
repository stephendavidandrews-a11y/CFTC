/**
 * API client wrapper for the CFTC Pipeline backend.
 *
 * Uses the proxy configured in package.json for development,
 * or REACT_APP_API_URL in production.
 */

const BASE = process.env.REACT_APP_API_URL || "";

export async function fetchJSON(url, options = {}) {
  const response = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`API ${response.status}: ${body || response.statusText}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

export async function uploadFile(url, formData) {
  const response = await fetch(`${BASE}${url}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Upload ${response.status}: ${body || response.statusText}`);
  }

  return response.json();
}
