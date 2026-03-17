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

export function listMatters({ status, priority, matter_type, assigned_to, search, source, source_id, sort_by, sort_dir, limit, offset } = {}) {
  return fetchJSON(`${P}/matters${qs({ status, priority, matter_type, assigned_to, search, source, source_id, sort_by, sort_dir, limit, offset })}`);
}

export function createMatter(data) {
  return fetchJSON(`${P}/matters`, { method: "POST", body: JSON.stringify(data) });
}

export function getMatter(id) {
  return fetchJSON(`${P}/matters/${id}`);
}

export function updateMatter(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/matters/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteMatter(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/matters/${id}`, { method: "DELETE", headers });
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

export function listTasks({ matter_id, assigned_to, status, mode, sort_by, sort_dir, limit, offset } = {}) {
  return fetchJSON(`${P}/tasks${qs({ matter_id, assigned_to, status, mode, sort_by, sort_dir, limit, offset })}`);
}

export function createTask(data) {
  return fetchJSON(`${P}/tasks`, { method: "POST", body: JSON.stringify(data) });
}

export function getTask(id) {
  return fetchJSON(`${P}/tasks/${id}`);
}

export function updateTask(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/tasks/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteTask(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/tasks/${id}`, { method: "DELETE", headers });
}

// ── People ──────────────────────────────────────────────────────────────────

export function listPeople({ organization_id, is_active, search, relationship_category, relationship_lane, limit, offset } = {}) {
  return fetchJSON(`${P}/people${qs({ organization_id, is_active, search, relationship_category, relationship_lane, limit, offset })}`);
}

export function createPerson(data) {
  return fetchJSON(`${P}/people`, { method: "POST", body: JSON.stringify(data) });
}

export function getPerson(id) {
  return fetchJSON(`${P}/people/${id}`);
}

export function updatePerson(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/people/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deletePerson(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/people/${id}`, { method: "DELETE", headers });
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

export function updateOrganization(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/organizations/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteOrganization(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/organizations/${id}`, { method: "DELETE", headers });
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

export function updateMeeting(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/meetings/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteMeeting(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/meetings/${id}`, { method: "DELETE", headers });
}

// ── Documents ───────────────────────────────────────────────────────────────

export function listDocuments({ matter_id, document_type, status, limit, offset } = {}) {
  return fetchJSON(`${P}/documents${qs({ matter_id, document_type, status, limit, offset })}`);
}

export function createDocument(data) {
  return fetchJSON(`${P}/documents`, { method: "POST", body: JSON.stringify(data) });
}

export function getDocument(id) {
  return fetchJSON(`${P}/documents/${id}`);
}

export function updateDocument(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/documents/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteDocument(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/documents/${id}`, { method: "DELETE", headers });
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

export function updateDecision(id, data, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/decisions/${id}`, { method: "PUT", headers, body: JSON.stringify(data) });
}

export function deleteDecision(id, etag) {
  const headers = etag ? { "If-Match": etag } : {};
  return fetchJSON(`${P}/decisions/${id}`, { method: "DELETE", headers });
}

// ── Recent Updates ──────────────────────────────────────────────────────────

export function getRecentUpdates({ limit } = {}) {
  return fetchJSON(`${P}/updates/recent${qs({ limit })}`);
}


// ── Tags ────────────────────────────────────────────────────────────────────

export function listTags(tagType) {
  let url = P + "/tags";
  if (tagType) url += "?tag_type=" + encodeURIComponent(tagType);
  return fetchJSON(url);
}

export function createTag(data) {
  return fetchJSON(P + "/tags", { method: "POST", body: JSON.stringify(data) });
}

export function deleteTag(tagId) {
  return fetchJSON(P + "/tags/" + tagId, { method: "DELETE" });
}

export function getMatterTags(matterId) {
  return fetchJSON(P + "/matters/" + matterId + "/tags");
}

export function addMatterTag(matterId, tagId) {
  return fetchJSON(P + "/matters/" + matterId + "/tags", { method: "POST", body: JSON.stringify({ tag_id: tagId }) });
}

export function removeMatterTag(matterId, tagId) {
  return fetchJSON(P + "/matters/" + matterId + "/tags/" + tagId, { method: "DELETE" });
}

// ── Meeting Participants (post-creation) ────────────────────────────────────

export function addMeetingParticipant(meetingId, data) {
  return fetchJSON(P + "/meetings/" + meetingId + "/participants", { method: "POST", body: JSON.stringify(data) });
}

export function updateMeetingParticipant(meetingId, participantId, data) {
  return fetchJSON(P + "/meetings/" + meetingId + "/participants/" + participantId, { method: "PUT", body: JSON.stringify(data) });
}

export function removeMeetingParticipant(meetingId, participantId) {
  return fetchJSON(P + "/meetings/" + meetingId + "/participants/" + participantId, { method: "DELETE" });
}

export function updateMeetingMatters(meetingId, matterIds) {
  return fetchJSON(P + "/meetings/" + meetingId + "/matters", { method: "PUT", body: JSON.stringify({ matter_ids: matterIds }) });
}

// ── Matter Dependencies ─────────────────────────────────────────────────────

export function addMatterDependency(matterId, data) {
  return fetchJSON(P + "/matters/" + matterId + "/dependencies", { method: "POST", body: JSON.stringify(data) });
}

export function removeMatterDependency(matterId, depId) {
  return fetchJSON(P + "/matters/" + matterId + "/dependencies/" + depId, { method: "DELETE" });
}

// ── Pipeline Integration ────────────────────────────────────────────────────

export function findMatterByPipelineItem(pipelineItemId) {
  return listMatters({ source: "pipeline", source_id: String(pipelineItemId), limit: 1 });
}
