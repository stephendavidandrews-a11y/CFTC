/**
 * API client wrapper for the CFTC Pipeline backend.
 *
 * Uses the proxy configured in package.json for development,
 * or REACT_APP_API_URL in production.
 */

const BASE = process.env.REACT_APP_API_URL || "";

/** Generate a short unique request ID for tracing. */
function generateRequestId() {
  return "fe-" + Math.random().toString(36).substring(2, 10) + "-" + Date.now().toString(36);
};

export class ApiError extends Error {
  constructor(status, detail, statusText) {
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join("; ")
      : typeof detail === "string"
        ? detail
        : (detail && detail.message) || statusText || "Request failed";
    super(msg);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  get isValidation() { return this.status === 422; }
  get isNotFound()   { return this.status === 404; }
  get isConflict()   { return this.status === 409; }

  get fieldErrors() {
    if (!Array.isArray(this.detail)) return {};
    const out = {};
    for (const d of this.detail) {
      const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "unknown";
      out[field] = d.msg;
    }
    return out;
  }
}

const DEFAULT_TIMEOUT_MS = 30000;
const MAX_RETRIES = 1;
const RETRY_DELAY_MS = 1000;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

export async function fetchJSON(url, options = {}) {
  const { headers: customHeaders, timeout = DEFAULT_TIMEOUT_MS, ...restOptions } = options;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(`${BASE}${url}`, {
        headers: { "Content-Type": "application/json", "X-Write-Source": "human", "X-Request-ID": generateRequestId(), ...customHeaders },
        signal: controller.signal,
        ...restOptions,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        if (RETRYABLE_STATUSES.has(response.status) && attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
          continue;
        }
        const body = await response.text().catch(() => "");
        let detail = body || response.statusText;
        try { const parsed = JSON.parse(body); detail = parsed.detail ?? parsed; } catch {}
        throw new ApiError(response.status, detail, response.statusText);
      }

      if (response.status === 204) return null;
      const data = await response.json();
      const etag = response.headers.get("etag");
      if (etag && data && typeof data === "object" && !Array.isArray(data)) {
        data._etag = etag;
      }
      return data;

    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof ApiError) throw err;
      if (err.name === "AbortError") {
        throw new ApiError(0, "Request timed out", "Timeout");
      }
      if (attempt < MAX_RETRIES) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        continue;
      }
      throw new ApiError(0, err.message || "Network error", "NetworkError");
    }
  }
}

export async function uploadFile(url, formData, { timeout = 300000 } = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  let response;
  try {
    response = await fetch(`${BASE}${url}`, {
      method: "POST",
      headers: { "X-Request-ID": generateRequestId() },
      body: formData,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new ApiError(0, "Upload timed out", "Timeout");
    }
    throw new ApiError(0, err.message || "Upload failed", "NetworkError");
  }
  clearTimeout(timeoutId);

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    let detail = body || response.statusText;
    try { const parsed = JSON.parse(body); detail = parsed.detail ?? parsed; } catch {}
    throw new ApiError(response.status, detail, response.statusText);
  }

  return response.json();
}
