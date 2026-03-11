/**
 * Pipeline API calls.
 */

import { fetchJSON, uploadFile } from "./client";

const P = "/pipeline";

// ── Items ──────────────────────────────────────────────────────────

export const listItems = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${P}/items?${q}`);
};

export const getKanban = (module, itemType = null) => {
  const params = new URLSearchParams({ module });
  if (itemType) params.set("item_type", itemType);
  return fetchJSON(`${P}/items/kanban?${params}`);
};

export const getItem = (id) => fetchJSON(`${P}/items/${id}`);

export const createItem = (data) =>
  fetchJSON(`${P}/items`, { method: "POST", body: JSON.stringify(data) });

export const updateItem = (id, data) =>
  fetchJSON(`${P}/items/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const advanceStage = (id, data = {}) =>
  fetchJSON(`${P}/items/${id}/advance`, { method: "POST", body: JSON.stringify(data) });

// ── Decision Log ───────────────────────────────────────────────────

export const getDecisionLog = (itemId) =>
  fetchJSON(`${P}/items/${itemId}/decision-log`);

export const addDecisionLog = (itemId, data) =>
  fetchJSON(`${P}/items/${itemId}/decision-log`, { method: "POST", body: JSON.stringify(data) });

// ── Deadlines ──────────────────────────────────────────────────────

export const listDeadlines = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${P}/deadlines?${q}`);
};

export const getUpcomingDeadlines = (days = 30) =>
  fetchJSON(`${P}/deadlines/upcoming?days=${days}`);

export const createDeadline = (data) =>
  fetchJSON(`${P}/deadlines`, { method: "POST", body: JSON.stringify(data) });

export const updateDeadline = (id, data) =>
  fetchJSON(`${P}/deadlines/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const extendDeadline = (id, data) =>
  fetchJSON(`${P}/deadlines/${id}/extend`, { method: "POST", body: JSON.stringify(data) });

export const backwardCalculate = (data) =>
  fetchJSON(`${P}/deadlines/backward-calculate`, { method: "POST", body: JSON.stringify(data) });

// ── Team ───────────────────────────────────────────────────────────

export const listTeam = () => fetchJSON(`${P}/team`);

export const getTeamDashboard = () => fetchJSON(`${P}/team/dashboard`);

export const getMemberWorkload = (id) => fetchJSON(`${P}/team/${id}/workload`);

export const createTeamMember = (data) =>
  fetchJSON(`${P}/team`, { method: "POST", body: JSON.stringify(data) });

export const updateTeamMember = (id, data) =>
  fetchJSON(`${P}/team/${id}`, { method: "PATCH", body: JSON.stringify(data) });

// ── Dashboard ──────────────────────────────────────────────────────

export const getExecutiveSummary = () => fetchJSON(`${P}/dashboard/summary`);

export const getMetrics = () => fetchJSON(`${P}/dashboard/metrics`);

export const getNotifications = (unreadOnly = false) =>
  fetchJSON(`${P}/dashboard/notifications?unread_only=${unreadOnly}`);

export const markNotificationRead = (id) =>
  fetchJSON(`${P}/dashboard/notifications/${id}/read`, { method: "PATCH" });

export const getUnreadCount = () => fetchJSON(`${P}/dashboard/notifications/count`);

// ── Documents ──────────────────────────────────────────────────────

export const listDocuments = (itemId) =>
  fetchJSON(`${P}/documents?item_id=${itemId}`);

export const uploadDocument = (formData) =>
  uploadFile(`${P}/documents`, formData);

// ── Stakeholders ───────────────────────────────────────────────────

export const listStakeholders = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${P}/stakeholders?${q}`);
};

export const createStakeholder = (data) =>
  fetchJSON(`${P}/stakeholders`, { method: "POST", body: JSON.stringify(data) });

export const listMeetings = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${P}/stakeholders/meetings?${q}`);
};

export const createMeeting = (data) =>
  fetchJSON(`${P}/stakeholders/meetings`, { method: "POST", body: JSON.stringify(data) });

// ── Integrations ───────────────────────────────────────────────────

export const getStage1Scores = (frCitation) =>
  fetchJSON(`${P}/integrations/stage1-scores/${encodeURIComponent(frCitation)}`);

export const getEOActions = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${P}/integrations/eo-actions?${q}`);
};

export const crossSearch = (query) =>
  fetchJSON(`${P}/integrations/search?q=${encodeURIComponent(query)}`);
