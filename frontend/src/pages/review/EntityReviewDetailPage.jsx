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

// ── Main Page ────────────────────────────────────────────────────────────────

export default function EntityReviewDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, refetch } = useApi(() => getEntityReviewDetail(id), [id]);
  const [expandedId, setExpandedId] = useState(null);
  const [completing, setCompleting] = useState(false);
  const [confirmingAll, setConfirmingAll] = useState(false);

  const entities = data?.entities || [];
  const counts = data?.entity_counts || {};

  const pendingCount = entities.filter((e) => e.confirmed === 0).length;
  const confirmedCount = entities.filter((e) => e.confirmed === 1).length;
  const rejectedCount = entities.filter((e) => e.confirmed === -1).length;
  const allReviewed = pendingCount === 0 && entities.length > 0;

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
      refetch();
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

  if (loading) {
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
          {entities.length} entities \u00b7
          {" "}{confirmedCount} confirmed \u00b7
          {" "}{rejectedCount} rejected \u00b7
          {" "}{pendingCount} pending
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
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
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

        {entities.map((entity) => (
          <EntityRow
            key={entity.id}
            entity={entity}
            communicationId={id}
            onUpdate={refetch}
            isExpanded={expandedId === entity.id}
            onToggle={() => setExpandedId(expandedId === entity.id ? null : entity.id)}
          />
        ))}
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
            disabled={!allReviewed || completing}
            style={{
              padding: "8px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: allReviewed && !completing ? "#3b82f6" : "#374151",
              color: allReviewed && !completing ? "#fff" : "#6b7280",
              border: "none",
              cursor: allReviewed && !completing ? "pointer" : "not-allowed",
            }}
          >
            {completing ? "Completing..." : "Confirm All & Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
