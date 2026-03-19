/**
 * API client wrapper for the CFTC Pipeline backend.
 *
 * Uses the proxy configured in package.json for development,
 * or REACT_APP_API_URL in production.
 */

const BASE = process.env.REACT_APP_API_URL || "";

export class ApiError extends Error {
  constructor(status, detail, statusText) {
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join("; ")
      : typeof detail === "string"
        ? detail
        : statusText || "Request failed";
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

export async function fetchJSON(url, options = {}) {
  const { headers: customHeaders, ...restOptions } = options;
  const response = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", "X-Write-Source": "human", ...customHeaders },
    ...restOptions,
  });

  if (!response.ok) {
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
}

export async function uploadFile(url, formData) {
  const response = await fetch(`${BASE}${url}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    let detail = body || response.statusText;
    try { const parsed = JSON.parse(body); detail = parsed.detail ?? parsed; } catch {}
    throw new ApiError(response.status, detail, response.statusText);
  }

  return response.json();
}
