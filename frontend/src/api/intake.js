/**
 * API client for the CFTC Intake Service (port 8005) and
 * Tracker people lookup (port 8004 via /tracker proxy).
 *
 * Speaker identity lives in the Tracker — intake only stores
 * voiceprints and mappings keyed by tracker_person_id.
 */

import { fetchJSON, uploadFile } from "./client";

const INTAKE = "/intake/api";
const TRACKER = "/tracker";

// ── Conversations ──

export function listConversations({ status, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (limit) params.set("limit", String(limit));
  if (offset) params.set("offset", String(offset));
  const qs = params.toString();
  return fetchJSON(INTAKE + "/conversations" + (qs ? "?" + qs : ""));
}

export function getConversation(id) {
  return fetchJSON(INTAKE + "/conversations/" + id);
}

export function getQueueCounts() {
  return fetchJSON(INTAKE + "/conversations/queue-counts");
}

export function editTranscriptSegment(transcriptId, text) {
  return fetchJSON(INTAKE + "/conversations/transcripts/" + transcriptId, {
    method: "PATCH",
    body: JSON.stringify({ text }),
  });
}

export function confirmSpeakers(conversationId) {
  return fetchJSON(INTAKE + "/conversations/" + conversationId + "/confirm-speakers", {
    method: "POST",
  });
}

export function discardConversation(conversationId) {
  return fetchJSON(INTAKE + "/conversations/" + conversationId + "/discard", {
    method: "PATCH",
  });
}

// ── Speaker Assignment ──

export function assignSpeaker({ conversation_id, speaker_label, tracker_person_id }) {
  return fetchJSON(INTAKE + "/correct-speaker", {
    method: "POST",
    body: JSON.stringify({ conversation_id, speaker_label, tracker_person_id }),
  });
}

export function mergeSpeakers({ conversation_id, from_label, to_label }) {
  return fetchJSON(INTAKE + "/merge-speakers", {
    method: "POST",
    body: JSON.stringify({ conversation_id, from_label, to_label }),
  });
}

export function reassignSegment({ transcript_segment_id, new_speaker_label }) {
  return fetchJSON(INTAKE + "/reassign-segment", {
    method: "POST",
    body: JSON.stringify({ transcript_segment_id, new_speaker_label }),
  });
}

export function getSpeakerSuggestions(conversationId) {
  return fetchJSON(INTAKE + "/speaker-suggestions/" + conversationId);
}

// ── People (from Tracker — single source of truth) ──

export function listTrackerPeople({ search, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return fetchJSON(TRACKER + "/people" + (qs ? "?" + qs : "")).then(
    (data) => data.items || []
  );
}

export function getTrackerPerson(id) {
  return fetchJSON(TRACKER + "/people/" + id);
}

// Batch-resolve person IDs to names (for voiceprint suggestions)
export async function resolvePersonNames(personIds) {
  if (!personIds || personIds.length === 0) return {};
  // Fetch each person — small N (typically 2-6 speakers per conversation)
  const results = {};
  await Promise.all(
    personIds.map(async (pid) => {
      try {
        const person = await getTrackerPerson(pid);
        results[pid] = {
          full_name: person.full_name,
          title: person.title,
          org_name: person.org_name,
        };
      } catch (e) {
        // Person may have been deleted from tracker
        results[pid] = { full_name: "Unknown (" + pid.slice(0, 8) + ")", title: null, org_name: null };
      }
    })
  );
  return results;
}

// ── Audio ──

export function audioUrl(conversationId) {
  return INTAKE + "/audio/" + conversationId;
}

export function audioClipUrl(conversationId, start, end) {
  return INTAKE + "/audio/" + conversationId + "/clip?start=" + start + "&end=" + end;
}

export function speakerSampleUrl(conversationId, speakerLabel) {
  return INTAKE + "/audio/" + conversationId + "/speaker-sample/" + encodeURIComponent(speakerLabel);
}

// ── Pipeline ──

export function uploadRecording(file, source, note) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source", source || "phone");
  if (note) formData.append("note", note);
  return uploadFile(INTAKE + "/pipeline/upload", formData);
}

export function getPipelineStatus() {
  return fetchJSON(INTAKE + "/pipeline/status");
}

export function getHealth() {
  return fetchJSON(INTAKE + "/health");
}
