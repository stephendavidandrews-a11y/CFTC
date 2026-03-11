/**
 * Comment system API calls.
 * Talks to the CFTC comment analysis backend at /api/v1.
 */

import { fetchJSON } from "./client";

export const commentsApi = {
  // Rules / Dockets
  getRules: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`/rules${qs ? '?' + qs : ''}`);
  },
  getRule: (docket) => fetchJSON(`/rules/${encodeURIComponent(docket)}`),

  // Comments
  getComments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`/comments?${qs}`);
  },
  getComment: (docId) => fetchJSON(`/comments/${encodeURIComponent(docId)}`),
  getStats: (docket) => fetchJSON(`/comments/stats/${encodeURIComponent(docket)}`),
  getNarrative: (docket) => fetchJSON(`/comments/narrative/${encodeURIComponent(docket)}`),

  // AI Processing
  detectFormLetters: (docket) =>
    fetchJSON(`/comments/detect-form-letters?docket_number=${encodeURIComponent(docket)}`, { method: 'POST' }),
  aiTier: (docket, batchSize = 50) =>
    fetchJSON(`/comments/ai-tier?docket_number=${encodeURIComponent(docket)}&batch_size=${batchSize}`, { method: 'POST' }),
  aiSummarize: (docket, tier = null, batchSize = 50) => {
    let url = `/comments/ai-summarize?docket_number=${encodeURIComponent(docket)}&batch_size=${batchSize}`;
    if (tier) url += `&tier=${tier}`;
    return fetchJSON(url, { method: 'POST' });
  },

  // Ingestion
  addDocket: (docketNumber) =>
    fetchJSON(`/rules/add-docket`, {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  fetchComments: (docketNumber) =>
    fetchJSON(`/comments/fetch`, {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  extractText: (docketNumber, batchSize = 50) => {
    let url = `/comments/extract-text?batch_size=${batchSize}`;
    if (docketNumber) url += `&docket_number=${encodeURIComponent(docketNumber)}`;
    return fetchJSON(url, { method: 'POST' });
  },
  browseCftcReleases: (year = 0) =>
    fetchJSON(year > 0 ? `/cftc-releases?year=${year}` : `/cftc-releases`),

  // Organizations
  getTier1Orgs: () => fetchJSON(`/tier1-orgs`),

  // Analysis
  getTierBreakdown: (docket) => fetchJSON(`/comments/tier-breakdown/${encodeURIComponent(docket)}`),
  getStatutoryAnalysis: (docket) => fetchJSON(`/comments/statutory-analysis/${encodeURIComponent(docket)}`),

  // Export (returns URLs, not fetches — use absolute paths since these are href, not fetchJSON)
  exportBriefing: (docket) => `/api/v1/export/briefing/${encodeURIComponent(docket)}`,
  exportPdfs: (docket) => `/api/v1/export/pdfs/${encodeURIComponent(docket)}`,

  // Extraction status
  extractionStatus: (docket) => {
    let url = `/comments/extraction-status`;
    if (docket) url += `?docket_number=${encodeURIComponent(docket)}`;
    return fetchJSON(url);
  },
};
