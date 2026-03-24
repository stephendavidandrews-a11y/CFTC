import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import { getParticipantReviewDetail, confirmParticipant, completeParticipantReview, getEmailMessages } from "../../api/ai";
import { listPeople } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import EmptyState from "../../components/shared/EmptyState";

const cardStyle = { background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "16px 20px", marginBottom: 12 };
const btnPrimary = { background: "#1e40af", color: "#fff", border: "none", padding: "6px 16px", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600 };
const btnSecondary = { background: "#334155", color: "#e2e8f0", border: "none", padding: "6px 16px", borderRadius: 6, cursor: "pointer", fontSize: 13 };

export default function ParticipantReviewDetailPage() {
  const { id } = useParams();
  const toast = useToastContext();
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(() => getParticipantReviewDetail(id), [id]);
  const { data: messages } = useApi(() => getEmailMessages(id), [id]);
  const { data: peopleData } = useApi(() => listPeople({ limit: 500 }), []);
  const [completing, setCompleting] = useState(false);

  const people = peopleData?.items || peopleData || [];
  const participants = data?.participants || [];
  const communication = data?.communication || data || {};

  const handleConfirm = async (participantId, personId) => {
    try {
      await confirmParticipant(id, { participant_id: participantId, tracker_person_id: personId });
      refetch();
    } catch (e) {
      toast.error("Failed to confirm participant: " + (e.message || e));
    }
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeParticipantReview(id);
      navigate("/review/participants");
    } catch (e) {
      toast.error("Failed to complete review: " + (e.message || e));
      setCompleting(false);
    }
  };

  if (loading) return <div style={{ padding: 40, color: theme.text.muted }}>Loading...</div>;
  if (error) return <div style={{ padding: 40, color: "#f87171" }}>Error: {error.message || String(error)}</div>;

  const allConfirmed = participants.length > 0 && participants.every(p => p.confirmed);

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1000 }}>
      <button onClick={() => navigate("/review/participants")} style={{ ...btnSecondary, marginBottom: 16 }}>
        &larr; Back to Queue
      </button>

      <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
        {communication.title || "Participant Review"}
      </h1>
      <p style={{ color: theme.text.muted, fontSize: 13, marginBottom: 24 }}>
        Confirm participant identities before extraction proceeds.
      </p>

      <h2 style={{ fontSize: 15, fontWeight: 600, color: theme.text.secondary, marginBottom: 12 }}>
        Participants ({participants.length})
      </h2>

      {participants.length === 0 && (
        <EmptyState icon="person" title="No participants found" message="This communication has no participants to review." />
      )}

      {participants.map((p) => (
        <div key={p.id} style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ color: theme.text.primary, fontWeight: 600, fontSize: 14 }}>
                {p.proposed_name || p.participant_email || p.speaker_label || "Unknown"}
              </div>
              {p.proposed_title && <div style={{ color: theme.text.muted, fontSize: 12 }}>{p.proposed_title}</div>}
              {p.proposed_org && <div style={{ color: theme.text.faint, fontSize: 12 }}>{p.proposed_org}</div>}
              {p.participant_email && <div style={{ color: theme.text.faint, fontSize: 12 }}>{p.participant_email}</div>}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {p.confirmed ? (
                <Badge bg="#14532d" text="#4ade80" label="Confirmed" />
              ) : p.tracker_person_id ? (
                <Badge bg="#422006" text="#fbbf24" label="Linked" />
              ) : (
                <Badge bg="#1f2937" text="#9ca3af" label="Unconfirmed" />
              )}
              {!p.confirmed && (
                <select
                  style={{ background: theme.bg.input, color: theme.text.primary, border: `1px solid ${theme.border.default}`, borderRadius: 6, padding: "4px 8px", fontSize: 12 }}
                  value={p.tracker_person_id || ""}
                  onChange={(e) => { if (e.target.value) handleConfirm(p.id, e.target.value); }}
                >
                  <option value="">Link to person...</option>
                  {people.map(person => (
                    <option key={person.id} value={person.id}>{person.full_name}{person.title ? ` (${person.title})` : ""}</option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>
      ))}

      {messages?.items?.length > 0 && (
        <>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: theme.text.secondary, marginTop: 24, marginBottom: 12 }}>
            Email Messages ({messages.items.length})
          </h2>
          {messages.items.map((msg, i) => (
            <div key={msg.id || i} style={{ ...cardStyle, fontSize: 13 }}>
              <div style={{ color: theme.text.muted, marginBottom: 4 }}>
                <strong>From:</strong> {msg.sender_name || msg.sender_email || "Unknown"}
              </div>
              {msg.subject && <div style={{ color: theme.text.secondary, marginBottom: 4 }}><strong>Subject:</strong> {msg.subject}</div>}
            </div>
          ))}
        </>
      )}

      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
        <button
          style={{ ...btnPrimary, opacity: allConfirmed && !completing ? 1 : 0.5 }}
          disabled={!allConfirmed || completing}
          onClick={handleComplete}
        >
          {completing ? "Completing..." : "Complete Review"}
        </button>
        <button style={btnSecondary} onClick={() => navigate("/review/participants")}>Cancel</button>
      </div>
    </div>
  );
}
