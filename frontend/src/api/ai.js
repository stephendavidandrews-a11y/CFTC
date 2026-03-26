/**
 * AI Service API client — matches backend router endpoints exactly.
 *
 * All AI endpoints are proxied through nginx at /ai/api/*.
 * Bundle review routes: /ai/api/bundle-review/*
 * Communication routes: /ai/api/communications/*
 */

import { fetchJSON, uploadFile, ApiError } from "./client";

// ── Health ──────────────────────────────────────────────────────────────────
export function getAIHealth() {
  return fetchJSON("/ai/api/health");
}

// ── Config / Policy ─────────────────────────────────────────────────────────
export function getAIConfig() {
  return fetchJSON("/ai/api/config");
}

export function updateAIConfigSection(section, data) {
  return fetchJSON(`/ai/api/config/${section}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function getConfigAudit() {
  return fetchJSON("/ai/api/config/audit");
}

export function getConfigStats() {
  return fetchJSON("/ai/api/config/stats");
}

// ── Communications ──────────────────────────────────────────────────────────
export function listCommunications(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return fetchJSON(`/ai/api/communications${qs ? "?" + qs : ""}`);
}

export function getCommunication(id) {
  return fetchJSON(`/ai/api/communications/${id}`);
}

export function retryCommunication(id) {
  return fetchJSON(`/ai/api/communications/${id}/retry`, { method: "POST" });
}

export function undoCommunication(id, force = false) {
  return fetchJSON(`/ai/api/communications/${id}/undo?force=${force}`, {
    method: "POST",
  });
}

export function archiveCommunication(id) {
  return fetchJSON(`/ai/api/communications/${id}/archive`, { method: "POST" });
}

export function unarchiveCommunication(id) {
  return fetchJSON(`/ai/api/communications/${id}/unarchive`, { method: "POST" });
}

export function deleteCommunication(id) {
  return fetchJSON(`/ai/api/communications/${id}`, { method: "DELETE" });
}

// ── Bundle Review ───────────────────────────────────────────────────────────
export function getBundleReviewQueue() {
  return fetchJSON("/ai/api/bundle-review/queue");
}

export function getBundleReviewDetail(communicationId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}`);
}

export function acceptItem(communicationId, bundleId, itemId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/accept-item`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, item_id: itemId }),
  });
}

export function rejectItem(communicationId, bundleId, itemId, reason = null) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/reject-item`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, item_id: itemId, reason }),
  });
}

export function editItem(communicationId, bundleId, itemId, proposedData) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/edit-item`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, item_id: itemId, proposed_data: proposedData }),
  });
}

export function restoreItem(communicationId, bundleId, itemId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/restore-item`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, item_id: itemId }),
  });
}

export function addItem(communicationId, bundleId, itemType, proposedData, opts = {}) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/add-item`, {
    method: "POST",
    body: JSON.stringify({
      bundle_id: bundleId, item_type: itemType, proposed_data: proposedData,
      rationale: opts.rationale || "Reviewer-created item",
      source_excerpt: opts.sourceExcerpt || null,
      source_start_time: opts.sourceStartTime || null,
      source_end_time: opts.sourceEndTime || null,
    }),
  });
}

export function acceptBundle(communicationId, bundleId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/accept-bundle`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId }),
  });
}

export function rejectBundle(communicationId, bundleId, reason = null) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/reject-bundle`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, reason }),
  });
}

export function editBundle(communicationId, bundleId, updates) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/edit-bundle`, {
    method: "POST",
    body: JSON.stringify({ bundle_id: bundleId, ...updates }),
  });
}

export function acceptAllBundles(communicationId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/accept-all`, {
    method: "POST",
  });
}

export function moveItem(communicationId, itemId, fromBundleId, toBundleId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/move-item`, {
    method: "POST",
    body: JSON.stringify({ item_id: itemId, from_bundle_id: fromBundleId, to_bundle_id: toBundleId }),
  });
}

export function createBundle(communicationId, opts = {}) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/create-bundle`, {
    method: "POST",
    body: JSON.stringify({
      bundle_type: opts.bundleType || "standalone",
      target_matter_id: opts.targetMatterId || null,
      target_matter_title: opts.targetMatterTitle || null,
      rationale: opts.rationale || "Reviewer-created bundle",
      intelligence_notes: opts.intelligenceNotes || null,
    }),
  });
}

export function mergeBundles(communicationId, sourceBundleId, targetBundleId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/merge-bundles`, {
    method: "POST",
    body: JSON.stringify({ source_bundle_id: sourceBundleId, target_bundle_id: targetBundleId }),
  });
}

export function completeBundleReview(communicationId) {
  return fetchJSON(`/ai/api/bundle-review/${communicationId}/complete`, {
    method: "POST",
  });
}

// ── Audio Upload ───────────────────────────────────────────────────────────
export function uploadAudio(file, title, sensitivityFlags) {
  const form = new FormData();
  form.append("audio", file);
  if (title) form.append("title", title);
  if (sensitivityFlags) form.append("sensitivity_flags", sensitivityFlags);
  return uploadFile("/ai/api/communications/audio-upload", form);
}

// ── Email Intake ────────────────────────────────────────────────────────────
export function uploadEmail(file, title, sensitivityFlags) {
  const form = new FormData();
  form.append("email_file", file);
  if (title) form.append("title", title);
  if (sensitivityFlags) form.append("sensitivity_flags", sensitivityFlags);
  return uploadFile("/ai/api/communications/email-upload", form);
}

// ── Participant Review ──────────────────────────────────────────────────────
export function getParticipantReviewQueue() {
  return fetchJSON("/ai/api/participant-review/queue");
}

export function getParticipantReviewDetail(communicationId) {
  return fetchJSON(`/ai/api/participant-review/${communicationId}`);
}

export function confirmParticipant(communicationId, data) {
  return fetchJSON(`/ai/api/participant-review/${communicationId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function completeParticipantReview(communicationId) {
  return fetchJSON(`/ai/api/participant-review/${communicationId}/complete`, {
    method: "POST",
  });
}

// ── Email Content ───────────────────────────────────────────────────────────
export function getEmailMessages(communicationId) {
  return fetchJSON(`/ai/api/participant-review/${communicationId}/messages`);
}

export function getEmailArtifacts(communicationId) {
  return fetchJSON(`/ai/api/participant-review/${communicationId}/artifacts`);
}

// ── Speaker Review ─────────────────────────────────────────────────────────
export function getSpeakerReviewQueue() {
  return fetchJSON("/ai/api/speaker-review/queue");
}

export function getSpeakerReviewDetail(communicationId) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}`);
}

export function linkSpeaker(communicationId, data) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/link-speaker`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function createProvisionalPerson(communicationId, data) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/new-person`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function skipSpeaker(communicationId, participantId) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/skip-speaker`, {
    method: "POST",
    body: JSON.stringify({ participant_id: participantId }),
  });
}

export function rejectVoiceprintMatch(communicationId, data) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/reject-match`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function completeSpeakerReview(communicationId) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/complete`, {
    method: "POST",
  });
}

// ── Entity Review ──────────────────────────────────────────────────────────
export function getEntityReviewQueue() {
  return fetchJSON("/ai/api/entity-review/queue");
}

export function getEntityReviewDetail(communicationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}`);
}

export function confirmEntity(communicationId, entityId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/confirm-entity`, {
    method: "POST",
    body: JSON.stringify({ entity_id: entityId }),
  });
}

export function linkEntity(communicationId, data) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/link-entity`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function editEntity(communicationId, data) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/edit-entity`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function rejectEntity(communicationId, entityId, reason = null) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/reject-entity`, {
    method: "POST",
    body: JSON.stringify({ entity_id: entityId, reason }),
  });
}

export function mergeEntities(communicationId, fromEntityId, toEntityId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/merge-entities`, {
    method: "POST",
    body: JSON.stringify({ from_entity_id: fromEntityId, to_entity_id: toEntityId }),
  });
}

export function confirmAllEntities(communicationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/confirm-all`, {
    method: "POST",
  });
}

export function completeEntityReview(communicationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/complete`, {
    method: "POST",
  });
}


// ── Association Review (Phase 2A) ────────────────────────────────────────────
export function confirmMatterAssociation(communicationId, associationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/confirm-matter-association`, {
    method: "POST",
    body: JSON.stringify({ association_id: associationId }),
  });
}

export function rejectMatterAssociation(communicationId, associationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/reject-matter-association`, {
    method: "POST",
    body: JSON.stringify({ association_id: associationId }),
  });
}

export function addMatterAssociation(communicationId, data) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/add-matter-association`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function confirmDirectiveAssociation(communicationId, associationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/confirm-directive-association`, {
    method: "POST",
    body: JSON.stringify({ association_id: associationId }),
  });
}

export function rejectDirectiveAssociation(communicationId, associationId) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/reject-directive-association`, {
    method: "POST",
    body: JSON.stringify({ association_id: associationId }),
  });
}

export function addDirectiveAssociation(communicationId, data) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/add-directive-association`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateSegmentIntent(communicationId, segmentIndex, intent) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/update-segment-intent`, {
    method: "POST",
    body: JSON.stringify({ segment_index: segmentIndex, intent }),
  });
}

export function dismissIntelligenceFlag(communicationId, flagIndex) {
  return fetchJSON(`/ai/api/entity-review/${communicationId}/dismiss-intelligence-flag`, {
    method: "POST",
    body: JSON.stringify({ flag_index: flagIndex }),
  });
}
// ── Intelligence ─────────────────────────────────────────────────────────────
export function getIntelligenceBriefs(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return fetchJSON(`/ai/api/intelligence/briefs${qs ? "?" + qs : ""}`);
}

// ── Transcript Editing ──────────────────────────────────────────────────────
export async function editTranscriptSegment(communicationId, transcriptId, reviewedText) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/transcripts/${transcriptId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewed_text: reviewedText }),
  });
}

export async function findSimilarCorrections(communicationId, correctionId) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/transcripts/find-similar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correction_id: correctionId }),
  });
}

export async function applyCorrections(communicationId, correctionId, corrections) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/transcripts/apply-corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correction_id: correctionId, corrections }),
  });
}


// -- Meeting Intelligence ------------------------------------------------
export function getMeetingIntelligence(meetingId) {
  return fetchJSON(`/ai/api/meeting-intelligence/by-meeting/${meetingId}`);
}


// ── Speaker Review — Unlink & Merge ─────────────────────────────────────────

export function unlinkSpeaker(communicationId, participantId) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/unlink-speaker`, {
    method: "POST",
    body: JSON.stringify({ participant_id: participantId }),
  });
}

export function mergeSpeakers(communicationId, targetLabel, sourceLabels) {
  return fetchJSON(`/ai/api/speaker-review/${communicationId}/merge-speakers`, {
    method: "POST",
    body: JSON.stringify({ target_label: targetLabel, source_labels: sourceLabels }),
  });
}

export { ApiError };
