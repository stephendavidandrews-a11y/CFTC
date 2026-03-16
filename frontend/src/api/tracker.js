/**
 * API client for the CFTC Regulatory Ops Tracker backend.
 * All endpoints are prefixed with /tracker/.
 */

import { fetchJSON, uploadFile } from "./client";

const P = "/tracker";

// ── Health ──────────────────────────────────────────────────────────────────

export function getTrackerHealth() {
  return fetchJSON(`${P}/health`);
}

// ── Dashboard ───────────────────────────────────────────────────────────────

export function getDashboard() {
  return fetchJSON(`${P}/dashboard`);
}

export function getDashboardStats() {
  return fetchJSON(`${P}/dashboard/stats`);
}

// ── Lookups / Enums ─────────────────────────────────────────────────────────

export function getEnums() {
  return fetchJSON(`${P}/lookups/enums`);
}

export function getEnum(name) {
  return fetchJSON(`${P}/lookups/enums/${encodeURIComponent(name)}`);
}

// ── Matters ─────────────────────────────────────────────────────────────────

function qs(params) {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") s.append(k, v);
  });
  const str = s.toString();
  return str ? `?${str}` : "";
}

export function listMatters({ status, priority, matter_type, assigned_to, search, sort, order, limit, offset } = {}) {
  return fetchJSON(`${P}/matters${qs({ status, priority, matter_type, assigned_to, search, sort, order, limit, offset })}`);
}

export function createMatter(data) {
  return fetchJSON(`${P}/matters`, { method: "POST", body: JSON.stringify(data) });
}

export function getMatter(id) {
  return fetchJSON(`${P}/matters/${id}`);
}

export function updateMatter(id, data) {
  return fetchJSON(`${P}/matters/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteMatter(id) {
  return fetchJSON(`${P}/matters/${id}`, { method: "DELETE" });
}

// ── Matter Stakeholders (People) ────────────────────────────────────────────

export function addMatterPerson(matterId, data) {
  return fetchJSON(`${P}/matters/${matterId}/people`, { method: "POST", body: JSON.stringify(data) });
}

export function removeMatterPerson(matterId, personId) {
  return fetchJSON(`${P}/matters/${matterId}/people/${personId}`, { method: "DELETE" });
}

// ── Matter Organizations ────────────────────────────────────────────────────

export function addMatterOrg(matterId, data) {
  return fetchJSON(`${P}/matters/${matterId}/orgs`, { method: "POST", body: JSON.stringify(data) });
}

export function removeMatterOrg(matterId, orgId) {
  return fetchJSON(`${P}/matters/${matterId}/orgs/${orgId}`, { method: "DELETE" });
}

// ── Matter Updates ──────────────────────────────────────────────────────────

export function addMatterUpdate(matterId, data) {
  return fetchJSON(`${P}/matters/${matterId}/updates`, { method: "POST", body: JSON.stringify(data) });
}

// ── Tasks ───────────────────────────────────────────────────────────────────

export function listTasks({ matter_id, assigned_to, status, mode, sort, order, limit, offset } = {}) {
  return fetchJSON(`${P}/tasks${qs({ matter_id, assigned_to, status, mode, sort, order, limit, offset })}`);
}

export function createTask(data) {
  return fetchJSON(`${P}/tasks`, { method: "POST", body: JSON.stringify(data) });
}

export function getTask(id) {
  return fetchJSON(`${P}/tasks/${id}`);
}

export function updateTask(id, data) {
  return fetchJSON(`${P}/tasks/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteTask(id) {
  return fetchJSON(`${P}/tasks/${id}`, { method: "DELETE" });
}

// ── People ──────────────────────────────────────────────────────────────────

export function listPeople({ organization_id, is_active, search, limit, offset } = {}) {
  return fetchJSON(`${P}/people${qs({ organization_id, is_active, search, limit, offset })}`);
}

export function createPerson(data) {
  return fetchJSON(`${P}/people`, { method: "POST", body: JSON.stringify(data) });
}

export function getPerson(id) {
  return fetchJSON(`${P}/people/${id}`);
}

export function updatePerson(id, data) {
  return fetchJSON(`${P}/people/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deletePerson(id) {
  return fetchJSON(`${P}/people/${id}`, { method: "DELETE" });
}

// ── Organizations ───────────────────────────────────────────────────────────

export function listOrganizations({ parent_id, organization_type, search, limit, offset } = {}) {
  return fetchJSON(`${P}/organizations${qs({ parent_id, organization_type, search, limit, offset })}`);
}

export function createOrganization(data) {
  return fetchJSON(`${P}/organizations`, { method: "POST", body: JSON.stringify(data) });
}

export function getOrganization(id) {
  return fetchJSON(`${P}/organizations/${id}`);
}

export function updateOrganization(id, data) {
  return fetchJSON(`${P}/organizations/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteOrganization(id) {
  return fetchJSON(`${P}/organizations/${id}`, { method: "DELETE" });
}

// ── Meetings ────────────────────────────────────────────────────────────────

export function listMeetings({ matter_id, date_from, date_to, limit, offset } = {}) {
  return fetchJSON(`${P}/meetings${qs({ matter_id, date_from, date_to, limit, offset })}`);
}

export function createMeeting(data) {
  return fetchJSON(`${P}/meetings`, { method: "POST", body: JSON.stringify(data) });
}

export function getMeeting(id) {
  return fetchJSON(`${P}/meetings/${id}`);
}

export function updateMeeting(id, data) {
  return fetchJSON(`${P}/meetings/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteMeeting(id) {
  return fetchJSON(`${P}/meetings/${id}`, { method: "DELETE" });
}

// ── Documents ───────────────────────────────────────────────────────────────

export function listDocuments({ matter_id, document_type, limit, offset } = {}) {
  return fetchJSON(`${P}/documents${qs({ matter_id, document_type, limit, offset })}`);
}

export function createDocument(data) {
  return fetchJSON(`${P}/documents`, { method: "POST", body: JSON.stringify(data) });
}

export function getDocument(id) {
  return fetchJSON(`${P}/documents/${id}`);
}

export function updateDocument(id, data) {
  return fetchJSON(`${P}/documents/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteDocument(id) {
  return fetchJSON(`${P}/documents/${id}`, { method: "DELETE" });
}

export function uploadDocumentFile(id, formData) {
  return uploadFile(`${P}/documents/${id}/upload`, formData);
}

// ── Decisions ───────────────────────────────────────────────────────────────

export function listDecisions({ matter_id, status, limit, offset } = {}) {
  return fetchJSON(`${P}/decisions${qs({ matter_id, status, limit, offset })}`);
}

export function createDecision(data) {
  return fetchJSON(`${P}/decisions`, { method: "POST", body: JSON.stringify(data) });
}

export function getDecision(id) {
  return fetchJSON(`${P}/decisions/${id}`);
}

export function updateDecision(id, data) {
  return fetchJSON(`${P}/decisions/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function deleteDecision(id) {
  return fetchJSON(`${P}/decisions/${id}`, { method: "DELETE" });
}

// ── Recent Updates ──────────────────────────────────────────────────────────

export function getRecentUpdates({ limit } = {}) {
  return fetchJSON(`${P}/updates/recent${qs({ limit })}`);
}
