import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { useToastContext as useToast } from "../../contexts/ToastContext";
import {
  getEntityReviewDetail,
  confirmEntity,
  linkEntity,
  editEntity,
  rejectEntity,
  confirmAllEntities,
  completeEntityReview,
  confirmMatterAssociation,
  rejectMatterAssociation,
  addMatterAssociation,
  confirmDirectiveAssociation,
  rejectDirectiveAssociation,
  addDirectiveAssociation,
  updateSegmentIntent,
  dismissIntelligenceFlag,
} from "../../api/ai";
import ConfidenceIndicator from "../../components/shared/ConfidenceIndicator";
import PersonOrgResolver from "../../components/shared/PersonOrgResolver";

// ── Entity type icons ────────────────────────────────────────────────────────

const TYPE_ICONS = {
  person: "\uD83D\uDC64",
  organization: "\uD83C\uDFE2",
  regulation: "\u00A7",
  legislation: "\uD83D\uDCDC",
  case: "\u2696",
  concept: "\uD83D\uDCA1",
};

const TYPE_LABELS = {
  person: "Person",
  organization: "Organization",
  regulation: "Regulation",
  legislation: "Legislation",
  case: "Case",
  concept: "Concept",
};



const INTENT_OPTIONS = [
  { value: "casual", label: "Casual", color: "#a78bfa" },
  { value: "planning", label: "Planning", color: "#60a5fa" },
  { value: "decision", label: "Decision", color: "#fbbf24" },
  { value: "strategic", label: "Strategic", color: "#f87171" },
  { value: "briefing", label: "Briefing", color: "#34d399" },
  { value: "policy", label: "Policy", color: "#fb923c" },
  { value: "negotiation", label: "Negotiation", color: "#e879f9" },
];

function formatTime(secs) {
  if (!secs && secs !== 0) return "";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return m + ":" + String(s).padStart(2, "0");
}

// ── Entity row (expandable) ─────────────────────────────────────────────────

function EntityRow({ entity, communicationId, onUpdate, isExpanded, onToggle }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const statusColor =
    entity.confirmed === 1 ? "#4ade80" :
    entity.confirmed === -1 ? "#f87171" :
    theme.text.faint;

  const statusLabel =
    entity.confirmed === 1 ? (entity.tracker_person_id || entity.tracker_org_id ? "Linked" : "Confirmed") :
    entity.confirmed === -1 ? "Rejected" :
    "Pending";

  const statusIcon =
    entity.confirmed === 1 ? "\u2713" :
    entity.confirmed === -1 ? "\u2717" :
    "\u2014";

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await confirmEntity(communicationId, entity.id);
      toast.success(`Confirmed: ${entity.mention_text}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await rejectEntity(communicationId, entity.id);
      toast.info(`Rejected: ${entity.mention_text}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const handleLink = async (trackerRecord) => {
    setBusy(true);
    try {
      const data = { entity_id: entity.id };
      if (entity.entity_type === "organization") {
        data.tracker_org_id = trackerRecord.id;
        data.proposed_name = trackerRecord.name || trackerRecord.short_name;
      } else {
        data.tracker_person_id = trackerRecord.id;
        data.proposed_name = trackerRecord.full_name;
        data.proposed_title = trackerRecord.title;
        data.proposed_org = trackerRecord.organization_name;
      }
      await linkEntity(communicationId, data);
      toast.success(`Linked ${entity.mention_text} to ${data.proposed_name}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const handleCreateNew = async (formData) => {
    setBusy(true);
    try {
      // Set proposed fields on the entity
      await editEntity(communicationId, {
        entity_id: entity.id,
        proposed_name: formData.proposed_name,
        proposed_title: formData.proposed_title || null,
        proposed_org: formData.proposed_org || formData.organization_type || null,
      });
      // Then confirm it
      await confirmEntity(communicationId, entity.id);
      toast.success(`Created provisional: ${formData.proposed_name}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const isPending = entity.confirmed === 0;

  return (
    <div style={{
      background: theme.bg.card,
      border: `1px solid ${entity.confirmed === 1 ? "rgba(74,222,128,0.2)" : entity.confirmed === -1 ? "rgba(248,113,113,0.2)" : theme.border.subtle}`,
      borderRadius: 8, marginBottom: 6,
      opacity: busy ? 0.6 : 1, pointerEvents: busy ? "none" : "auto",
    }}>
      {/* Row header (always visible, clickable to expand) */}
      <div
        onClick={onToggle}
        style={{
          display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
          cursor: "pointer",
        }}
      >
        {/* Type icon */}
        <span style={{ fontSize: 14, width: 22, textAlign: "center" }}>
          {TYPE_ICONS[entity.entity_type] || "\u2022"}
        </span>

        {/* Mention text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{ color: theme.text.primary, fontWeight: 600, fontSize: 13 }}>
            {entity.mention_text}
          </span>
          {entity.proposed_name && entity.proposed_name !== entity.mention_text && (
            <span style={{ color: theme.text.faint, fontSize: 11, marginLeft: 8 }}>
              {"\u2192"} {entity.proposed_name}
            </span>
          )}
        </div>

        {/* Type label */}
        <span style={{
          fontSize: 10, color: theme.text.faint, textTransform: "uppercase",
          fontWeight: 600, letterSpacing: "0.05em", width: 80,
        }}>
          {TYPE_LABELS[entity.entity_type] || entity.entity_type}
        </span>

        {/* Confidence */}
        <div style={{ width: 100 }}>
          <ConfidenceIndicator score={entity.confidence} size="bar" width={50} />
        </div>

        {/* Mention count */}
        <span style={{
          fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono,
          width: 40, textAlign: "center",
        }}>
          {entity.mention_count}x
        </span>

        {/* Status */}
        <span style={{
          fontSize: 12, fontWeight: 600, color: statusColor, width: 70, textAlign: "center",
        }}>
          {statusIcon} {statusLabel}
        </span>

        {/* Expand arrow */}
        <span style={{ fontSize: 10, color: theme.text.faint }}>
          {isExpanded ? "\u25B2" : "\u25BC"}
        </span>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div style={{
          padding: "0 14px 14px", borderTop: "1px solid " + theme.border.subtle,
          paddingTop: 12,
        }}>
          {/* Context snippet */}
          {entity.context_snippet && (
            <div style={{
              background: "rgba(255,255,255,0.03)", padding: "8px 12px",
              borderRadius: 6, fontSize: 12, color: theme.text.muted,
              lineHeight: 1.5, marginBottom: 10,
              borderLeft: "3px solid rgba(96,165,250,0.3)",
            }}>
              <div style={{ fontSize: 10, color: theme.text.faint, fontWeight: 600, marginBottom: 4 }}>
                Context
              </div>
              "{entity.context_snippet}"
            </div>
          )}

          {/* First mention from transcript */}
          {entity.first_mention_text && (
            <div style={{
              background: "rgba(255,255,255,0.02)", padding: "8px 12px",
              borderRadius: 6, fontSize: 12, color: theme.text.muted,
              lineHeight: 1.5, marginBottom: 10,
            }}>
              <div style={{ fontSize: 10, color: theme.text.faint, fontWeight: 600, marginBottom: 4 }}>
                First mention {entity.first_mention_speaker && `(${entity.first_mention_speaker})`}
              </div>
              "{entity.first_mention_text}"
            </div>
          )}

          {/* Match details if linked */}
          {entity.confirmed === 1 && (entity.tracker_person_id || entity.tracker_org_id) && (
            <div style={{
              padding: "8px 12px", borderRadius: 6,
              background: "rgba(74,222,128,0.06)", fontSize: 12, marginBottom: 10,
            }}>
              <span style={{ color: "#4ade80", fontWeight: 600 }}>Linked to: </span>
              <span style={{ color: theme.text.primary }}>
                {entity.proposed_name || entity.tracker_person_id || entity.tracker_org_id}
              </span>
              {entity.proposed_title && (
                <span style={{ color: theme.text.faint }}> {"\u2014"} {entity.proposed_title}</span>
              )}
              {entity.proposed_org && (
                <span style={{ color: theme.text.faint }}>, {entity.proposed_org}</span>
              )}
            </div>
          )}

          {/* Provisional details (confirmed but no tracker ID) */}
          {entity.confirmed === 1 && !entity.tracker_person_id && !entity.tracker_org_id && entity.proposed_name && (
            <div style={{
              padding: "8px 12px", borderRadius: 6,
              background: "rgba(250,204,21,0.06)", fontSize: 12, marginBottom: 10,
            }}>
              <span style={{
                background: "#fbbf24", color: "#000", fontSize: 9, fontWeight: 700,
                padding: "1px 5px", borderRadius: 3, marginRight: 6,
              }}>PROVISIONAL</span>
              <span style={{ color: theme.text.primary, fontWeight: 600 }}>
                {entity.proposed_name}
              </span>
              {entity.proposed_title && (
                <span style={{ color: theme.text.faint }}> {"\u2014"} {entity.proposed_title}</span>
              )}
              {entity.proposed_org && (
                <span style={{ color: theme.text.faint }}>, {entity.proposed_org}</span>
              )}
            </div>
          )}

          {/* Action buttons for pending entities */}
          {isPending && (
            <div>
              {/* Quick actions */}
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                <button
                  onClick={handleConfirm}
                  style={{
                    padding: "5px 12px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: "rgba(74,222,128,0.15)", color: "#4ade80",
                    border: "1px solid rgba(74,222,128,0.3)", cursor: "pointer",
                  }}
                >
                  Confirm as-is
                </button>
                <button
                  onClick={handleReject}
                  style={{
                    padding: "5px 12px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: "rgba(248,113,113,0.1)", color: "#f87171",
                    border: "1px solid rgba(248,113,113,0.3)", cursor: "pointer",
                  }}
                >
                  Reject (false positive)
                </button>
              </div>

              {/* Link to existing */}
              <div style={{ fontSize: 10, color: theme.text.faint, fontWeight: 600, marginBottom: 6, textTransform: "uppercase" }}>
                Link to existing
              </div>
              <PersonOrgResolver
                entityType={entity.entity_type === "organization" ? "organization" : "person"}
                onLink={handleLink}
                onCreateNew={handleCreateNew}
                onSkip={handleConfirm}
                showSkip={false}
              />
            </div>
          )}

          {/* Allow changing rejected/confirmed entities */}
          {!isPending && (
            <div style={{ display: "flex", gap: 6 }}>
              {entity.confirmed === -1 && (
                <button
                  onClick={handleConfirm}
                  style={{
                    padding: "5px 12px", borderRadius: 4, fontSize: 11,
                    background: "rgba(74,222,128,0.1)", color: "#4ade80",
                    border: "1px solid rgba(74,222,128,0.3)", cursor: "pointer",
                  }}
                >
                  Un-reject (Confirm)
                </button>
              )}
              {entity.confirmed === 1 && (
                <button
                  onClick={handleReject}
                  style={{
                    padding: "5px 12px", borderRadius: 4, fontSize: 11,
                    background: "rgba(248,113,113,0.1)", color: "#f87171",
                    border: "1px solid rgba(248,113,113,0.3)", cursor: "pointer",
                  }}
                >
                  Reject
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── Association Row (matter or directive) ────────────────────────────────────

function AssociationRow({ assoc, type, communicationId, onUpdate }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const confirmFn = type === "matter" ? confirmMatterAssociation : confirmDirectiveAssociation;
  const rejectFn = type === "matter" ? rejectMatterAssociation : rejectDirectiveAssociation;
  const label = type === "matter" ? assoc.matter_title : assoc.directive_label;

  const statusColor = assoc.confirmed === 1 ? "#4ade80" : assoc.confirmed === -1 ? "#f87171" : theme.text.faint;
  const statusLabel = assoc.confirmed === 1 ? "Confirmed" : assoc.confirmed === -1 ? "Rejected" : "Pending";

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await confirmFn(communicationId, assoc.id);
      toast.success(`Confirmed: ${label}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await rejectFn(communicationId, assoc.id);
      toast.info(`Rejected: ${label}`);
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "8px 14px",
      background: theme.bg.card, border: "1px solid " + (assoc.confirmed === 1 ? "rgba(74,222,128,0.2)" : assoc.confirmed === -1 ? "rgba(248,113,113,0.2)" : theme.border.subtle),
      borderRadius: 6, marginBottom: 4,
      opacity: busy ? 0.6 : 1,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ color: theme.text.primary, fontWeight: 600, fontSize: 13 }}>{label}</span>
        {assoc.reasoning && (
          <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>{assoc.reasoning}</div>
        )}
        {assoc.relevant_segments && Array.isArray(assoc.relevant_segments) && assoc.relevant_segments.length > 0 && (
          <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: 8 }}>
            Segments: {assoc.relevant_segments.join(", ")}
          </span>
        )}
      </div>
      <div style={{ width: 70 }}>
        <ConfidenceIndicator score={assoc.confidence} size="bar" width={50} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color: statusColor, width: 70, textAlign: "center" }}>
        {statusLabel}
      </span>
      {assoc.confirmed === 0 && (
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={handleConfirm} style={{ padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: "rgba(74,222,128,0.15)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.3)", cursor: "pointer" }}>Yes</button>
          <button onClick={handleReject} style={{ padding: "3px 10px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: "rgba(248,113,113,0.1)", color: "#f87171", border: "1px solid rgba(248,113,113,0.3)", cursor: "pointer" }}>No</button>
        </div>
      )}
      {assoc.confirmed !== 0 && (
        <button onClick={assoc.confirmed === 1 ? handleReject : handleConfirm} style={{ padding: "3px 10px", borderRadius: 4, fontSize: 10, background: "transparent", color: theme.text.faint, border: "1px solid " + theme.border.subtle, cursor: "pointer" }}>
          {assoc.confirmed === 1 ? "Reject" : "Confirm"}
        </button>
      )}
    </div>
  );
}

// ── Segment Intent Row ───────────────────────────────────────────────────────

function IntentRow({ segment, communicationId, onUpdate }) {
  const toast = useToast();

  const handleChange = async (e) => {
    try {
      await updateSegmentIntent(communicationId, segment.index, e.target.value);
      toast.success(`Updated intent for "${segment.topic}"`);
      onUpdate();
    } catch (err) { toast.error(err.message); }
  };

  const intentOption = INTENT_OPTIONS.find((o) => o.value === segment.intent) || INTENT_OPTIONS[4];

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "6px 14px",
      background: theme.bg.card, border: "1px solid " + theme.border.subtle,
      borderRadius: 6, marginBottom: 4,
    }}>
      <span style={{ fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono, width: 75 }}>
        {formatTime(segment.start_time)}-{formatTime(segment.end_time)}
      </span>
      <span style={{ flex: 1, color: theme.text.primary, fontSize: 13, fontWeight: 500 }}>
        {segment.topic}
      </span>
      <select
        value={segment.intent}
        onChange={handleChange}
        style={{
          padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
          background: theme.bg.card, color: intentOption.color,
          border: "1px solid " + theme.border.subtle, cursor: "pointer",
        }}
      >
        {INTENT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

// ── Intelligence Flag Row ────────────────────────────────────────────────────

function FlagRow({ flag, index, communicationId, onUpdate }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const handleDismiss = async () => {
    setBusy(true);
    try {
      await dismissIntelligenceFlag(communicationId, index);
      toast.info("Flag dismissed");
      onUpdate();
    } catch (e) { toast.error(e.message); }
    setBusy(false);
  };

  const FLAG_TYPE_COLORS = {
    personal_detail: "#a78bfa",
    org_operational: "#60a5fa",
    political_signal: "#f87171",
    relationship_dynamic: "#e879f9",
    process_insight: "#34d399",
    strategic_context: "#fbbf24",
    policy_detail: "#fb923c",
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "6px 14px",
      background: theme.bg.card, border: "1px solid " + theme.border.subtle,
      borderRadius: 6, marginBottom: 4,
      opacity: busy ? 0.6 : 1,
    }}>
      <span style={{
        fontSize: 9, fontWeight: 700, textTransform: "uppercase",
        padding: "2px 6px", borderRadius: 3,
        background: (FLAG_TYPE_COLORS[flag.flag_type] || theme.text.faint) + "20",
        color: FLAG_TYPE_COLORS[flag.flag_type] || theme.text.faint,
        whiteSpace: "nowrap",
      }}>
        {(flag.flag_type || "").replace(/_/g, " ")}
      </span>
      {flag.about_entity && (
        <span style={{ fontSize: 12, color: theme.text.muted, fontWeight: 600 }}>
          {flag.about_entity.name || "Unknown"}
        </span>
      )}
      <span style={{ flex: 1, fontSize: 12, color: theme.text.faint }}>
        {flag.hint}
      </span>
      <button onClick={handleDismiss} style={{
        padding: "2px 8px", borderRadius: 4, fontSize: 10,
        background: "transparent", color: theme.text.faint,
        border: "1px solid " + theme.border.subtle, cursor: "pointer",
      }}>
        Dismiss
      </button>
    </div>
  );
}

// ── Section Header ───────────────────────────────────────────────────────────

function SectionHeader({ title, count, pendingCount }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      marginTop: 20, marginBottom: 8,
    }}>
      <h2 style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
        {title}
      </h2>
      {count > 0 && (
        <span style={{ fontSize: 11, color: theme.text.faint }}>({count})</span>
      )}
      {pendingCount > 0 && (
        <span style={{
          fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 3,
          background: "rgba(251,191,36,0.15)", color: "#fbbf24",
        }}>
          {pendingCount} pending
        </span>
      )}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function EntityReviewDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, refetch } = useApi(() => getEntityReviewDetail(id), [id]);
  const [expandedId, setExpandedId] = useState(null);
  const scrollRef = React.useRef(null);

  // Preserve scroll position across refetches
  const refetchKeepScroll = React.useCallback(() => {
    const scrollTop = scrollRef.current?.scrollTop || 0;
    refetch().then(() => {
      // Double-RAF to ensure React has rendered before restoring scroll
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (scrollRef.current) scrollRef.current.scrollTop = scrollTop;
        });
      });
    }).catch(() => {});  // Swallow errors — refetch sets error state already
  }, [refetch]);
  const [completing, setCompleting] = useState(false);
  const [confirmingAll, setConfirmingAll] = useState(false);

  const entities = data?.entities || [];
  const counts = data?.entity_counts || {};

  const pendingCount = entities.filter((e) => e.confirmed === 0).length;
  const confirmedCount = entities.filter((e) => e.confirmed === 1).length;
  const rejectedCount = entities.filter((e) => e.confirmed === -1).length;
  const allReviewed = pendingCount === 0 && entities.length > 0;

  // Association data from v2 enrichment
  const matterAssociations = data?.matter_associations || [];
  const directiveAssociations = data?.directive_associations || [];
  const segmentIntents = data?.segment_intents || [];
  const intelligenceFlags = data?.intelligence_flags || [];

  // Only show reviewable entities (person/org) in the entity section
  const reviewableEntities = entities.filter(e => e.entity_type === "person" || e.entity_type === "organization");
  const infoEntities = entities.filter(e => e.entity_type !== "person" && e.entity_type !== "organization");

  const pendingMatterAssocs = matterAssociations.filter(a => a.confirmed === 0).length;
  const pendingDirectiveAssocs = directiveAssociations.filter(a => a.confirmed === 0).length;

  // All reviewable items must be resolved for completion
  const allAssociationsReviewed = pendingMatterAssocs === 0 && pendingDirectiveAssocs === 0;
  const canComplete = allReviewed && allAssociationsReviewed;

  // Auto-expand first pending entity
  useEffect(() => {
    if (entities.length > 0 && expandedId === null) {
      const firstPending = entities.find((e) => e.confirmed === 0);
      if (firstPending) setExpandedId(firstPending.id);
    }
  }, [entities.length]);

  const handleConfirmAll = async () => {
    setConfirmingAll(true);
    try {
      const result = await confirmAllEntities(id);
      toast.success(`Confirmed ${result.confirmed_count} entities`);
      refetchKeepScroll();
    } catch (e) {
      toast.error(`Confirm all failed: ${e.message}`);
    }
    setConfirmingAll(false);
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await completeEntityReview(id);
      toast.success("Entity review complete \u2014 extraction started");
      navigate("/review/entities");
    } catch (e) {
      toast.error(`Complete failed: ${e.message}`);
    }
    setCompleting(false);
  };

  if (loading && !data) {
    return (
      <div style={{ padding: "40px 32px", color: theme.text.faint }}>
        Loading entity review...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "40px 32px" }}>
        <div style={{
          padding: "12px 16px", borderRadius: 8,
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          color: "#f87171", fontSize: 13,
        }}>
          Failed to load: {error.message || String(error)}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{
        padding: "16px 24px", borderBottom: "1px solid " + theme.border.subtle,
      }}>
        <button
          onClick={() => navigate("/review/entities")}
          style={{
            background: "none", border: "none", color: theme.text.faint,
            cursor: "pointer", fontSize: 12, padding: 0, marginBottom: 4,
          }}
        >
          {"\u2190"} Entity Review Queue
        </button>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          {data?.title || data?.original_filename || "Untitled"}
        </h1>
        <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 2 }}>
          {reviewableEntities.length} entities \u00b7
          {" "}{confirmedCount} confirmed \u00b7
          {" "}{rejectedCount} rejected \u00b7
          {" "}{pendingCount} pending
          {matterAssociations.length > 0 && ` \u00b7 ${matterAssociations.length} matter assocs`}
          {directiveAssociations.length > 0 && ` \u00b7 ${directiveAssociations.length} directive assocs`}
        </div>

        {/* Summary from enrichment */}
        {data?.summary && (
          <div style={{
            marginTop: 10, padding: "10px 14px", borderRadius: 6,
            background: "rgba(96,165,250,0.06)", border: "1px solid rgba(96,165,250,0.15)",
            fontSize: 12, color: theme.text.muted, lineHeight: 1.5,
          }}>
            <div style={{ fontSize: 10, color: "#60a5fa", fontWeight: 600, marginBottom: 4 }}>
              Enrichment Summary
            </div>
            {data.summary}
          </div>
        )}

        {/* Sensitivity flags */}
        {data?.sensitivity_flags?.length > 0 && (
          <div style={{
            marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap",
          }}>
            {data.sensitivity_flags.map((flag, i) => (
              <span key={i} style={{
                padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                background: "rgba(239,68,68,0.1)", color: "#f87171",
                border: "1px solid rgba(239,68,68,0.2)",
              }}>
                {flag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Entity table (scrollable) */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
        {/* Pre-checked hint */}
        {pendingCount > 0 && entities.some((e) => e.confirmed === 0 && e.confidence >= 0.9) && (
          <div style={{
            padding: "8px 14px", borderRadius: 6, marginBottom: 12,
            background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.15)",
            fontSize: 12, color: theme.text.muted,
          }}>
            Entities with {"\u2265"}90% confidence can be bulk-confirmed with "Confirm All Pending."
          </div>
        )}

        {entities.length === 0 && (
          <div style={{ color: theme.text.faint, fontSize: 13, padding: 20, textAlign: "center" }}>
            No entities found. Haiku enrichment may not have detected any entities.
          </div>
        )}

        {/* People section */}
        {reviewableEntities.filter(e => e.entity_type === "person").length > 0 && (
          <SectionHeader
            title="People"
            count={reviewableEntities.filter(e => e.entity_type === "person").length}
            pendingCount={reviewableEntities.filter(e => e.entity_type === "person" && e.confirmed === 0).length}
          />
        )}
        {reviewableEntities.filter(e => e.entity_type === "person").map((entity) => (
          <EntityRow
            key={entity.id}
            entity={entity}
            communicationId={id}
            onUpdate={refetchKeepScroll}
            isExpanded={expandedId === entity.id}
            onToggle={() => setExpandedId(expandedId === entity.id ? null : entity.id)}
          />
        ))}

        {/* Organizations section */}
        {reviewableEntities.filter(e => e.entity_type === "organization").length > 0 && (
          <SectionHeader
            title="Organizations"
            count={reviewableEntities.filter(e => e.entity_type === "organization").length}
            pendingCount={reviewableEntities.filter(e => e.entity_type === "organization" && e.confirmed === 0).length}
          />
        )}
        {reviewableEntities.filter(e => e.entity_type === "organization").map((entity) => (
          <EntityRow
            key={entity.id}
            entity={entity}
            communicationId={id}
            onUpdate={refetchKeepScroll}
            isExpanded={expandedId === entity.id}
            onToggle={() => setExpandedId(expandedId === entity.id ? null : entity.id)}
          />
        ))}

        {/* Matter Associations */}
        {matterAssociations.length > 0 && (
          <>
            <SectionHeader title="Matter Associations" count={matterAssociations.length} pendingCount={pendingMatterAssocs} />
            {matterAssociations.map((assoc) => (
              <AssociationRow key={assoc.id} assoc={assoc} type="matter" communicationId={id} onUpdate={refetchKeepScroll} />
            ))}
          </>
        )}

        {/* Directive Associations */}
        {directiveAssociations.length > 0 && (
          <>
            <SectionHeader title="Directive Associations" count={directiveAssociations.length} pendingCount={pendingDirectiveAssocs} />
            {directiveAssociations.map((assoc) => (
              <AssociationRow key={assoc.id} assoc={assoc} type="directive" communicationId={id} onUpdate={refetchKeepScroll} />
            ))}
          </>
        )}

        {/* Segment Intents */}
        {segmentIntents.length > 0 && (
          <>
            <SectionHeader title="Segment Intents" count={segmentIntents.length} pendingCount={0} />
            {segmentIntents.map((seg, i) => (
              <IntentRow key={i} segment={seg} communicationId={id} onUpdate={refetchKeepScroll} />
            ))}
          </>
        )}

        {/* Intelligence Flags */}
        {intelligenceFlags.length > 0 && (
          <>
            <SectionHeader title="Intelligence Flags" count={intelligenceFlags.length} pendingCount={0} />
            <div style={{ fontSize: 11, color: theme.text.faint, marginBottom: 6 }}>
              These flags guide downstream extraction. Dismiss any that seem incorrect.
            </div>
            {intelligenceFlags.map((flag, i) => (
              <FlagRow key={i} flag={flag} index={i} communicationId={id} onUpdate={refetchKeepScroll} />
            ))}
          </>
        )}

        {/* Info entities (auto-confirmed, not reviewable) */}
        {infoEntities.length > 0 && (
          <>
            <SectionHeader title="Other Mentions (auto-confirmed)" count={infoEntities.length} pendingCount={0} />
            <div style={{ fontSize: 11, color: theme.text.faint, marginBottom: 8 }}>
              Regulations, legislation, cases, and concepts — no review needed, provided to extraction as context.
            </div>
            {infoEntities.map((entity) => (
              <div key={entity.id} style={{
                display: "flex", alignItems: "center", gap: 8, padding: "4px 14px",
                fontSize: 12, color: theme.text.faint,
              }}>
                <span>{TYPE_ICONS[entity.entity_type] || "\u2022"}</span>
                <span style={{ color: theme.text.muted }}>{entity.mention_text}</span>
                <span style={{ fontSize: 10 }}>({entity.entity_type})</span>
                <span style={{ fontSize: 10, fontFamily: theme.font.mono }}>{entity.mention_count}x</span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Bottom bar */}
      <div style={{
        padding: "12px 24px",
        borderTop: "1px solid " + theme.border.subtle,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: theme.bg.card,
      }}>
        <span style={{ fontSize: 13, color: theme.text.muted }}>
          {confirmedCount + rejectedCount} of {entities.length} entities reviewed
          {counts.linked > 0 && ` (${counts.linked} linked)`}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => navigate("/review/entities")}
            style={{
              padding: "8px 16px", borderRadius: 6, fontSize: 13,
              background: "transparent", color: theme.text.faint,
              border: "1px solid " + theme.border.subtle, cursor: "pointer",
            }}
          >
            Back to Queue
          </button>
          {pendingCount > 0 && (
            <button
              onClick={handleConfirmAll}
              disabled={confirmingAll}
              style={{
                padding: "8px 16px", borderRadius: 6, fontSize: 13, fontWeight: 600,
                background: "rgba(74,222,128,0.15)", color: "#4ade80",
                border: "1px solid rgba(74,222,128,0.3)",
                cursor: confirmingAll ? "not-allowed" : "pointer",
                opacity: confirmingAll ? 0.6 : 1,
              }}
            >
              {confirmingAll ? "Confirming..." : `Confirm All Pending (${pendingCount})`}
            </button>
          )}
          <button
            onClick={handleComplete}
            disabled={!canComplete || completing}
            style={{
              padding: "8px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: canComplete && !completing ? "#3b82f6" : "#374151",
              color: canComplete && !completing ? "#fff" : "#6b7280",
              border: "none",
              cursor: canComplete && !completing ? "pointer" : "not-allowed",
            }}
          >
            {completing ? "Completing..." : "Confirm All & Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
