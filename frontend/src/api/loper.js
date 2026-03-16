/**
 * Loper Bright Vulnerability Analyzer — API client.
 */

import { fetchJSON } from "./client";

const L = "/pipeline/loper";

// ── Rules ──────────────────────────────────────────────────────────

export const listRules = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
  );
  return fetchJSON(`${L}/rules?${new URLSearchParams(clean)}`);
};

export const getRule = (frCitation) =>
  fetchJSON(`${L}/rules/${encodeURIComponent(frCitation)}`);

// ── Guidance ───────────────────────────────────────────────────────

export const listGuidance = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
  );
  return fetchJSON(`${L}/guidance?${new URLSearchParams(clean)}`);
};

export const getGuidance = (docId) =>
  fetchJSON(`${L}/guidance/${encodeURIComponent(docId)}`);

// ── Dashboard ──────────────────────────────────────────────────────

export const getDashboard = () => fetchJSON(`${L}/dashboard`);

// ── Analytics ──────────────────────────────────────────────────────

export const getAnalytics = (type) => fetchJSON(`${L}/analytics/${type}`);

// ── Reports ────────────────────────────────────────────────────────

export const generateReport = (frCitation) =>
  fetchJSON(`${L}/rules/${encodeURIComponent(frCitation)}/generate-report`, {
    method: "POST",
  });

export const getReportStatus = (frCitation) =>
  fetchJSON(`${L}/rules/${encodeURIComponent(frCitation)}/report-status`);
