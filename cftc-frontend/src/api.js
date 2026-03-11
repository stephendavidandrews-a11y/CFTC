const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

async function fetchJSON(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

export const api = {
  // Rules
  getRules: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`/rules${qs ? '?' + qs : ''}`);
  },
  getRule: (docket) => fetchJSON(`/rules/${encodeURIComponent(docket)}`),

  // Comments
  getComments: (params = {}) => {
    // Map frontend params to backend params
    const mapped = { ...params };
    if (mapped.skip !== undefined) {
      mapped.page = Math.floor(mapped.skip / (mapped.limit || 25)) + 1;
      mapped.page_size = mapped.limit || 25;
      delete mapped.skip;
      delete mapped.limit;
    }
    const qs = new URLSearchParams(mapped).toString();
    return fetchJSON(`/comments?${qs}`);
  },
  getComment: (docId) => fetchJSON(`/comments/${encodeURIComponent(docId)}`),
  getStats: (docket) => fetchJSON(`/comments/stats/${encodeURIComponent(docket)}`),

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

  // Organizations
  getTier1Orgs: () => fetchJSON('/tier1-orgs'),

  // Analysis
  getTierBreakdown: (docket) => fetchJSON(`/comments/tier-breakdown/${encodeURIComponent(docket)}`),
  getStatutoryAnalysis: (docket) => fetchJSON(`/comments/statutory-analysis/${encodeURIComponent(docket)}`),
  getCommentNarrative: (docket) => fetchJSON(`/comments/narrative/${encodeURIComponent(docket)}`),

  // Ingestion
  addDocket: (docketNumber) =>
    fetchJSON('/rules/add-docket', {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  fetchComments: (docketNumber) =>
    fetchJSON('/comments/fetch', {
      method: 'POST',
      body: JSON.stringify({ docket_number: docketNumber }),
    }),
  extractText: (docketNumber, batchSize = 50) => {
    let url = `/comments/extract-text?batch_size=${batchSize}`;
    if (docketNumber) url += `&docket_number=${encodeURIComponent(docketNumber)}`;
    return fetchJSON(url, { method: 'POST' });
  },
  browseCftcReleases: (year = 0) =>
    fetchJSON(year > 0 ? `/cftc-releases?year=${year}` : '/cftc-releases'),

  // Pipeline
  getKanban: (module, itemType = null) => {
    const params = new URLSearchParams({ module });
    if (itemType) params.set("item_type", itemType);
    return fetchJSON(`/pipeline/items/kanban?${params}`);
  },
  listPipelineItems: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetchJSON(`/pipeline/items?${q}`);
  },
  getPipelineItem: (id) => fetchJSON(`/pipeline/items/${id}`),
  createPipelineItem: (data) =>
    fetchJSON('/pipeline/items', { method: 'POST', body: JSON.stringify(data) }),
  updatePipelineItem: (id, data) =>
    fetchJSON(`/pipeline/items/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  advanceStage: (id, data = {}) =>
    fetchJSON(`/pipeline/items/${id}/advance`, { method: 'POST', body: JSON.stringify(data) }),
  getExecutiveSummary: () => fetchJSON('/pipeline/dashboard/summary'),
  getMetrics: () => fetchJSON('/pipeline/dashboard/metrics'),
  getNotifications: (unreadOnly = false) =>
    fetchJSON(`/pipeline/dashboard/notifications?unread_only=${unreadOnly}`),
  markNotificationRead: (id) =>
    fetchJSON(`/pipeline/dashboard/notifications/${id}/read`, { method: 'PATCH' }),
  getUnreadCount: () => fetchJSON('/pipeline/dashboard/notifications/count'),
  listTeam: () => fetchJSON('/pipeline/team'),
};
