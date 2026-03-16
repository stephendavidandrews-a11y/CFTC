/**
 * Comment system API calls.
 * Talks to the CFTC comment analysis backend at /api/v1.
 */

import { fetchJSON } from "./client";

const API = "/api/v1";

export const commentsApi = {
  // Rules / Dockets
  getRules: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`${API}/rules${qs ? '?' + qs : ''}`);
  },
  getRule: (docket) => fetchJSON(`${API}/rules/${encodeURIComponent(docket)}`),

  // Comments
  getComments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`${API}/comments?${qs}`);
  },
  getComment: (docId) => fetchJSON(`${API}/comments/${encodeURIComponent(docId)}`),
  getStats: (docket) => fetchJSON(`${API}/comments/stats/${encodeURIComponent(docket)}`),
  getNarrative: (docket) => fetchJSON(`${API}/comments/narrative/${encodeURIComponent(docket)}`),

  // AI Processing
  detectFormLetters: (docket) =>
    fetchJSON(`${API}/comments/detect-form-letters?docket_number=${encodeURIComponent(docket)}`, { method: 'POST' }),
  aiTier: (docket, batchSize = 50) =>
    fetchJSON(`${API}/comments/ai-tier?docket_number=${encodeURIComponent(docket)}&batch_size=${batchSize}`, { method: 'POST' }),
  aiSummarize: (docket, tier = null, batchSize = 50) => {
    let url = `${API}/comments/ai-summarize?docket_number=${encodeURIComponent(docket)}&batch_size=${batchSize}`;
    if (tier) url += `&tier=${tier}`;
    return fetchJSON(url, { method: 'POST' });
  },

  // Ingestion
  addDocket: (docketNumber) =>
    fetchJSON(`${API}/rules/add-docket`, {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  fetchComments: (docketNumber) =>
    fetchJSON(`${API}/comments/fetch`, {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  extractText: (docketNumber, batchSize = 50) => {
    let url = `${API}/comments/extract-text?batch_size=${batchSize}`;
    if (docketNumber) url += `&docket_number=${encodeURIComponent(docketNumber)}`;
    return fetchJSON(url, { method: 'POST' });
  },
  browseCftcReleases: (year = 0) =>
    fetchJSON(year > 0 ? `${API}/cftc-releases?year=${year}` : `${API}/cftc-releases`),

  // Organizations
  getTier1Orgs: () => fetchJSON(`${API}/tier1-orgs`),

  // Analysis
  getTierBreakdown: (docket) => fetchJSON(`${API}/comments/tier-breakdown/${encodeURIComponent(docket)}`),
  getStatutoryAnalysis: (docket) => fetchJSON(`${API}/comments/statutory-analysis/${encodeURIComponent(docket)}`),

  // Export (returns URLs, not fetches — use absolute paths since these are href, not fetchJSON)
  exportBriefing: (docket) => `/api/v1/export/briefing/${encodeURIComponent(docket)}`,
  exportPdfs: (docket) => `/api/v1/export/pdfs/${encodeURIComponent(docket)}`,

  // Extraction status
  extractionStatus: (docket) => {
    let url = `${API}/comments/extraction-status`;
    if (docket) url += `?docket_number=${encodeURIComponent(docket)}`;
    return fetchJSON(url);
  },
};
