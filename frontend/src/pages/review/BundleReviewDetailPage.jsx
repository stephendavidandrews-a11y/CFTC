import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { useToastContext } from "../../contexts/ToastContext";
import {
  getBundleReviewDetail, acceptItem, rejectItem, editItem, restoreItem,
  addItem, acceptBundle, rejectBundle, editBundle, acceptAllBundles,
  moveItem, createBundle, mergeBundles, completeBundleReview,
} from "../../api/ai";
import Badge from "../../components/shared/Badge";
import ConfidenceIndicator from "../../components/shared/ConfidenceIndicator";
import Modal from "../../components/shared/Modal";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import SourceExcerptViewer from "../../components/shared/SourceExcerptViewer";

// ── Extracted sub-components ────────────────────────────────────────────────
import {
  FIELD_SCHEMAS, ITEM_TYPES, SchemaField, useReviewLookups,
  EditItemModal, AddItemModal, CreateBundleModal, MergeBundlesModal,
  CountBox, CollapsiblePanel, SuppressionSection, MetaField,
} from "../../components/review/BundleReviewComponents.jsx";


// ── Constants ───────────────────────────────────────────────────────────────

const BUNDLE_STATUS = {
  proposed: { bg: "#1e3a5f", text: "#60a5fa" },
  accepted: { bg: "#14532d", text: "#4ade80" },
  rejected: { bg: "#450a0a", text: "#f87171" },
  edited: { bg: "#422006", text: "#fbbf24" },
  moved: { bg: "#1f2937", text: "#9ca3af" },
};

const ITEM_TYPE_COLORS = {
  task: { bg: "#1e3a5f", text: "#60a5fa" },
  task_update: { bg: "#1e3a5f", text: "#93c5fd" },
  decision: { bg: "#1e1b4b", text: "#a78bfa" },
  decision_update: { bg: "#1e1b4b", text: "#c4b5fd" },
  meeting_record: { bg: "#0c4a6e", text: "#34d399" },
  matter_update: { bg: "#422006", text: "#fbbf24" },
  new_matter: { bg: "#14532d", text: "#4ade80" },
  new_person: { bg: "#1e3a5f", text: "#60a5fa" },
  new_organization: { bg: "#1e3a5f", text: "#60a5fa" },
  stakeholder_addition: { bg: "#1e1b4b", text: "#a78bfa" },
  status_change: { bg: "#422006", text: "#fbbf24" },
  document: { bg: "#1f2937", text: "#9ca3af" },
  context_note: { bg: "#134e4a", text: "#5eead4" },
  person_detail_update: { bg: "#1f2937", text: "#d1d5db" },
  org_detail_update: { bg: "#1f2937", text: "#d1d5db" },
  directive_update: { bg: "#312e81", text: "#818cf8" },
};

const BUNDLE_TYPE_COLORS = {
  existing_matter: { bg: "#1e3a5f", text: "#60a5fa" },
  new_matter: { bg: "#14532d", text: "#4ade80" },
  standalone: { bg: "#1f2937", text: "#9ca3af" },
};

function formatDuration(seconds) {
  if (seconds == null) return "\u2014";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function confidenceColor(c) {
  if (c >= 0.8) return theme.accent.green;
  if (c >= 0.5) return theme.accent.yellow;
  return theme.accent.red;
}

function formatLabel(str) {
  if (!str) return "";
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const btnBase = {
  padding: "6px 14px", borderRadius: 6, fontSize: 11, fontWeight: 600,
  border: "none", cursor: "pointer", transition: "opacity 0.15s",
};

// ── Component ───────────────────────────────────────────────────────────────

export default function BundleReviewDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToastContext();
  const { on } = useAIEvents(["review_ready", "bundle_review_complete"]);

  const { data, loading, error, refetch } = useApi(
    () => getBundleReviewDetail(id), [id]
  );

  const bundleScrollRef = React.useRef(null);
  const refetchKeepScroll = React.useCallback(() => {
    const el = bundleScrollRef.current || document.scrollingElement || document.documentElement;
    const scrollTop = el.scrollTop;
    refetch();
    // Restore after React re-render
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.scrollTop = scrollTop;
      });
    });
  }, [refetch]);

  useEffect(() => {
    const unsub = on("bundle_review_complete", (evt) => {
      if (evt.data?.communication_id === id) refetch();
    });
    return unsub;
  }, [on, id, refetch]);

  const { people: lookupPeople, orgs: lookupOrgs, matters: lookupMatters } = useReviewLookups(!!data);
  const [busy, setBusy] = useState({});
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [editModal, setEditModal] = useState(null);
  const [addModal, setAddModal] = useState(null);
  const [createBundleModal, setCreateBundleModal] = useState(false);
  const [mergeModal, setMergeModal] = useState(null);
  const [suppressionOpen, setSuppressionOpen] = useState(false);
  const [metaOpen, setMetaOpen] = useState(false);

  // busy guard
  const withBusy = useCallback(async (key, fn) => {
    setBusy((b) => ({ ...b, [key]: true }));
    try {
      await fn();
      refetchKeepScroll();
    } catch (err) {
      toast.error(err.message || "Action failed");
    } finally {
      setBusy((b) => ({ ...b, [key]: false }));
    }
  }, [refetch, toast]);

  if (loading && !data) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint, fontSize: 13 }}>
        Loading bundle review...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center" }}>
        <div style={{ color: theme.accent.red, fontSize: 14, marginBottom: 8 }}>
          Failed to load bundle review
        </div>
        <div style={{ color: theme.text.faint, fontSize: 12, marginBottom: 16 }}>{error.message}</div>
        <button onClick={refetch} style={{ ...btnBase, background: "#1e40af", color: "#fff" }}>Retry</button>
      </div>
    );
  }

  if (!data) return null;

  const bundles = data.bundles || [];
  const nonRejectedBundles = bundles.filter((b) => b.status !== "rejected");

  // ── Handlers ──────────────────────────────────────────────

  const handleAcceptItem = (bundleId, itemId) =>
    withBusy(`ai-${itemId}`, () => acceptItem(id, bundleId, itemId).then(() => toast.success("Item accepted")));

  const handleRejectItem = (bundleId, itemId) =>
    withBusy(`ri-${itemId}`, () => rejectItem(id, bundleId, itemId).then(() => toast.success("Item rejected")));

  const handleRestoreItem = (bundleId, itemId) =>
    withBusy(`rs-${itemId}`, () => restoreItem(id, bundleId, itemId).then(() => toast.success("Item restored")));

  const handleEditItemSave = async (bundleId, itemId, proposedData) => {
    await withBusy(`ei-${itemId}`, () => editItem(id, bundleId, itemId, proposedData).then(() => toast.success("Item updated")));
    setEditModal(null);
  };

  const handleAddItemSave = async (bundleId, itemType, proposedData) => {
    await withBusy(`add-${bundleId}`, () => addItem(id, bundleId, itemType, proposedData).then(() => toast.success("Item added")));
    setAddModal(null);
  };

  const handleAcceptBundle = (bundleId) =>
    withBusy(`ab-${bundleId}`, () => acceptBundle(id, bundleId).then(() => toast.success("Bundle accepted")));

  const handleRejectBundle = (bundleId) =>
    withBusy(`rb-${bundleId}`, () => rejectBundle(id, bundleId).then(() => toast.success("Bundle rejected")));

  const handleAcceptAll = () =>
    withBusy("accept-all", () => acceptAllBundles(id).then(() => toast.success("All bundles accepted")));

  const handleMoveItem = (itemId, fromBundleId, toBundleId) =>
    withBusy(`mv-${itemId}`, () => moveItem(id, itemId, fromBundleId, toBundleId).then(() => toast.success("Item moved")));

  const handleCreateBundle = async (opts) => {
    await withBusy("create-bundle", () => createBundle(id, opts).then(() => toast.success("Bundle created")));
    setCreateBundleModal(false);
  };

  const handleMergeBundles = async (sourceId, targetId) => {
    await withBusy(`merge-${sourceId}`, () => mergeBundles(id, sourceId, targetId).then(() => toast.success("Bundles merged")));
    setMergeModal(null);
  };

  const handleComplete = () =>
    withBusy("complete", () => completeBundleReview(id).then(() => {
      toast.success("Review completed");
      navigate("/review/bundles");
    }));

  // ── Render ────────────────────────────────────────────────

  return (
    <div style={{ padding: "28px 32px", maxWidth: 1100 }}>
      {/* ── Header ──────────────────────────────────────── */}
      <button
        onClick={() => navigate("/review/bundles")}
        style={{
          ...btnBase, background: "transparent", color: theme.text.dim,
          border: `1px solid ${theme.border.subtle}`, marginBottom: 16,
        }}
      >
        &larr; Back to Queue
      </button>

      <div style={{
        background: theme.bg.card, borderRadius: theme.card.radius,
        border: `1px solid ${theme.border.default}`, padding: "20px 24px",
        marginBottom: 20,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
              {data.original_filename || "Untitled Communication"}
            </h1>
            <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 4, display: "flex", gap: 16 }}>
              <span>{formatDuration(data.duration_seconds)}</span>
              {data.extraction_meta?.model_used && (
                <span style={{ fontFamily: theme.font.mono }}>{data.extraction_meta.model_used}</span>
              )}
              {data.created_at && <span>{new Date(data.created_at).toLocaleDateString()}</span>}
            </div>
          </div>
          {(() => {
            const s = BUNDLE_STATUS[data.processing_status] || BUNDLE_STATUS.proposed;
            return <Badge bg={s.bg} text={s.text} label={formatLabel(data.processing_status)} />;
          })()}
        </div>

        {/* Summary */}
        {data.summary && (
          <p style={{ fontSize: 13, color: theme.text.muted, lineHeight: 1.6, margin: "8px 0 0" }}>
            {data.summary}
          </p>
        )}

        {/* Sensitivity flags */}
        {data.sensitivity_flags?.length > 0 && (
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            {data.sensitivity_flags.map((f) => (
              <Badge key={f} bg="#450a0a" text="#f87171" label={f.replace(/_/g, " ")} />
            ))}
          </div>
        )}

        {/* Counts row */}
        <div style={{
          display: "flex", gap: 24, marginTop: 14, paddingTop: 12,
          borderTop: `1px solid ${theme.border.subtle}`,
        }}>
          <CountBox label="Bundles" value={data.bundle_counts?.total ?? bundles.length} />
          <CountBox label="Proposed" value={data.bundle_counts?.proposed ?? 0} color={theme.accent.blue} />
          <CountBox label="Accepted" value={data.bundle_counts?.accepted ?? 0} color={theme.accent.green} />
          <CountBox label="Rejected" value={data.bundle_counts?.rejected ?? 0} color={theme.accent.red} />
        </div>
      </div>

      {/* ── Bundle Cards ────────────────────────────────── */}
      {bundles.map((bundle) => (
        <BundleCard
          key={bundle.id}
          bundle={bundle}
          allBundles={nonRejectedBundles}
          commId={id}
          busy={busy}
          lookups={{ people: lookupPeople, orgs: lookupOrgs, matters: lookupMatters }}
          onAcceptItem={handleAcceptItem}
          onRejectItem={handleRejectItem}
          onRestoreItem={handleRestoreItem}
          onEditItem={(b, item) => setEditModal({ bundleId: b, item })}
          onAddItem={(bundleId) => setAddModal({ bundleId })}
          onAcceptBundle={handleAcceptBundle}
          onRejectBundle={(bundleId) => setConfirmDialog({
            title: "Reject Bundle",
            message: "This will reject the entire bundle and all its items. Continue?",
            danger: true,
            onConfirm: () => handleRejectBundle(bundleId),
          })}
          onMoveItem={handleMoveItem}
          onMerge={(sourceId) => setMergeModal({ sourceId })}
        />
      ))}

      {/* ── Restructuring Actions ───────────────────────── */}
      <div style={{
        display: "flex", gap: 10, margin: "16px 0",
        padding: "14px 0", borderTop: `1px solid ${theme.border.subtle}`,
      }}>
        <button
          onClick={() => setCreateBundleModal(true)}
          style={{ ...btnBase, background: "#1e40af", color: "#fff" }}
        >
          + Create Bundle
        </button>
        {nonRejectedBundles.length >= 2 && (
          <button
            onClick={() => setMergeModal({ sourceId: null })}
            style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}
          >
            Merge Bundles
          </button>
        )}
      </div>

      {/* ── Suppression Panel ───────────────────────────── */}
      {(data.suppressed_observations?.length > 0 || data.code_suppressions?.length > 0 ||
        data.dedup_warnings?.length > 0 || data.invalid_refs_cleaned?.length > 0) && (
        <CollapsiblePanel
          title="Suppressions &amp; Warnings"
          open={suppressionOpen}
          onToggle={() => setSuppressionOpen(!suppressionOpen)}
        >
          {data.suppressed_observations?.length > 0 && (
            <SuppressionSection title="Suppressed Observations" items={data.suppressed_observations} />
          )}
          {data.code_suppressions?.length > 0 && (
            <SuppressionSection
              title="Code Suppressions"
              items={data.code_suppressions.map((cs) => `${cs.item_type}: ${cs.reason}`)}
            />
          )}
          {data.dedup_warnings?.length > 0 && (
            <SuppressionSection
              title="Dedup Warnings"
              items={data.dedup_warnings.map((w) => typeof w === "string" ? w : JSON.stringify(w))}
            />
          )}
          {data.invalid_refs_cleaned?.length > 0 && (
            <SuppressionSection
              title="Invalid Refs Cleaned"
              items={data.invalid_refs_cleaned.map((r) => typeof r === "string" ? r : JSON.stringify(r))}
            />
          )}
        </CollapsiblePanel>
      )}

      {/* ── Extraction Metadata Panel ───────────────────── */}
      {data.extraction_meta && (
        <CollapsiblePanel
          title="Extraction Metadata"
          open={metaOpen}
          onToggle={() => setMetaOpen(!metaOpen)}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, fontSize: 12 }}>
            <MetaField label="Model" value={data.extraction_meta.model_used} />
            <MetaField label="Input Tokens" value={data.extraction_meta.input_tokens?.toLocaleString()} />
            <MetaField label="Output Tokens" value={data.extraction_meta.output_tokens?.toLocaleString()} />
            <MetaField label="Processing Time" value={data.extraction_meta.processing_seconds ? `${data.extraction_meta.processing_seconds.toFixed(1)}s` : null} />
            <MetaField label="Extraction ID" value={data.extraction_meta.extraction_id} mono />
          </div>
          {data.extraction_summary && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 4 }}>
                Extraction Summary
              </div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>
                {data.extraction_summary}
              </div>
            </div>
          )}
        </CollapsiblePanel>
      )}

      {/* ── Completion Section ──────────────────────────── */}
      <div style={{
        background: theme.bg.card, borderRadius: theme.card.radius,
        border: `1px solid ${theme.border.default}`, padding: "20px 24px",
        marginTop: 20,
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: theme.text.primary, margin: "0 0 12px" }}>
          Complete Review
        </h3>

        {data.completion_blockers?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.accent.yellow, marginBottom: 6 }}>
              Blockers ({data.completion_blockers.length})
            </div>
            {data.completion_blockers.map((b, i) => (
              <div key={i} style={{
                fontSize: 12, color: theme.text.muted, padding: "6px 10px",
                background: "rgba(245,158,11,0.06)", borderRadius: 6,
                border: "1px solid rgba(245,158,11,0.15)", marginBottom: 4,
              }}>
                {b.type === "bundle_not_resolved"
                  ? `Bundle not resolved (status: ${b.current_status})`
                  : typeof b === "string" ? b : JSON.stringify(b)}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button
            disabled={busy["accept-all"]}
            onClick={handleAcceptAll}
            style={{
              ...btnBase, background: theme.bg.input, color: theme.accent.green,
              border: `1px solid ${theme.border.default}`,
              opacity: busy["accept-all"] ? 0.5 : 1,
            }}
          >
            {busy["accept-all"] ? "Accepting..." : "Accept All"}
          </button>
          <button
            disabled={!data.ready_to_complete || busy.complete}
            onClick={() => setConfirmDialog({
              title: "Complete Review",
              message: "This will finalize the review and send all accepted items to the commit pipeline. Continue?",
              confirmLabel: "Complete Review",
              onConfirm: handleComplete,
            })}
            style={{
              ...btnBase, background: data.ready_to_complete ? "#1e40af" : theme.bg.input,
              color: data.ready_to_complete ? "#fff" : theme.text.faint,
              opacity: (!data.ready_to_complete || busy.complete) ? 0.5 : 1,
              cursor: data.ready_to_complete ? "pointer" : "not-allowed",
            }}
          >
            {busy.complete ? "Completing..." : "Complete Review"}
          </button>
        </div>
      </div>

      {/* ── Modals ──────────────────────────────────────── */}
      <ConfirmDialog
        isOpen={!!confirmDialog}
        onClose={() => setConfirmDialog(null)}
        onConfirm={() => confirmDialog?.onConfirm?.()}
        title={confirmDialog?.title || "Confirm"}
        message={confirmDialog?.message || "Are you sure?"}
        confirmLabel={confirmDialog?.confirmLabel || "Confirm"}
        danger={confirmDialog?.danger || false}
      />

      {/* Edit Item Modal */}
      <EditItemModal
        isOpen={!!editModal}
        onClose={() => setEditModal(null)}
        item={editModal?.item}
        busy={busy[`ei-${editModal?.item?.id}`]}
        onSave={(proposedData) => handleEditItemSave(editModal.bundleId, editModal.item.id, proposedData)}
      />

      {/* Add Item Modal */}
      <AddItemModal
        isOpen={!!addModal}
        onClose={() => setAddModal(null)}
        busy={busy[`add-${addModal?.bundleId}`]}
        onSave={(itemType, proposedData) => handleAddItemSave(addModal.bundleId, itemType, proposedData)}
      />

      {/* Create Bundle Modal */}
      <CreateBundleModal
        isOpen={createBundleModal}
        onClose={() => setCreateBundleModal(false)}
        busy={busy["create-bundle"]}
        onSave={handleCreateBundle}
      />

      {/* Merge Bundles Modal */}
      <MergeBundlesModal
        isOpen={!!mergeModal}
        onClose={() => setMergeModal(null)}
        bundles={nonRejectedBundles}
        sourceId={mergeModal?.sourceId}
        busy={busy[`merge-${mergeModal?.sourceId}`]}
        onMerge={handleMergeBundles}
      />
    </div>
  );
}

// ── Bundle Card ─────────────────────────────────────────────────────────────

function BundleCard({
  bundle, allBundles, commId, busy, lookups,
  onAcceptItem, onRejectItem, onRestoreItem, onEditItem, onAddItem,
  onAcceptBundle, onRejectBundle, onMoveItem, onMerge,
}) {
  const isTerminal = bundle.status === "accepted" || bundle.status === "rejected";
  const bType = BUNDLE_TYPE_COLORS[bundle.bundle_type] || BUNDLE_TYPE_COLORS.standalone;
  const bStatus = BUNDLE_STATUS[bundle.status] || BUNDLE_STATUS.proposed;

  return (
    <div style={{
      background: theme.bg.card, borderRadius: theme.card.radius,
      border: `1px solid ${bundle.status === "rejected" ? "rgba(239,68,68,0.3)" : theme.border.default}`,
      marginBottom: 16, overflow: "hidden",
      opacity: bundle.status === "rejected" ? 0.6 : 1,
    }}>
      {/* Bundle Header */}
      <div style={{ padding: "16px 20px", borderBottom: `1px solid ${theme.border.subtle}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <Badge bg={bType.bg} text={bType.text} label={formatLabel(bundle.bundle_type)} />
          <Badge bg={bStatus.bg} text={bStatus.text} label={formatLabel(bundle.status)} />
          {bundle.reviewer_created && (
            <Badge bg="#1e1b4b" text="#a78bfa" label="Reviewer Created" />
          )}
          {bundle.confidence != null && (
            <span style={{
              fontSize: 11, fontWeight: 700, color: confidenceColor(bundle.confidence),
              fontFamily: theme.font.mono,
            }}>
              {(bundle.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>
          {bundle.target_matter_title || (bundle.bundle_type === "new_matter" ? "New Matter" : "Standalone")}
        </div>

        {bundle.rationale && (
          <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, marginBottom: 4 }}>
            {bundle.rationale}
          </div>
        )}

        {bundle.intelligence_notes && (
          <div style={{
            fontSize: 12, color: theme.text.dim, lineHeight: 1.5,
            fontStyle: "italic", marginTop: 4,
          }}>
            Intel: {bundle.intelligence_notes}
          </div>
        )}

        {/* Bundle actions */}
        {!isTerminal && (
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button
              disabled={busy[`ab-${bundle.id}`]}
              onClick={() => onAcceptBundle(bundle.id)}
              style={{ ...btnBase, background: "#14532d", color: "#4ade80", opacity: busy[`ab-${bundle.id}`] ? 0.5 : 1 }}
            >
              Accept All Items
            </button>
            <button
              disabled={busy[`rb-${bundle.id}`]}
              onClick={() => onRejectBundle(bundle.id)}
              style={{ ...btnBase, background: "#450a0a", color: "#f87171", opacity: busy[`rb-${bundle.id}`] ? 0.5 : 1 }}
            >
              Reject Bundle
            </button>
            {allBundles.length >= 2 && (
              <button
                onClick={() => onMerge(bundle.id)}
                style={{ ...btnBase, background: theme.bg.input, color: theme.text.dim, border: `1px solid ${theme.border.subtle}` }}
              >
                Merge Into...
              </button>
            )}
          </div>
        )}

        {/* Item counts */}
        {bundle.item_counts && (
          <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 8, display: "flex", gap: 12 }}>
            <span>{bundle.item_counts.total} items</span>
            <span style={{ color: theme.accent.blue }}>{bundle.item_counts.proposed} proposed</span>
            <span style={{ color: theme.accent.green }}>{bundle.item_counts.accepted} accepted</span>
          </div>
        )}
      </div>

      {/* Items — grouped: actionable → updates → context */}
      <div style={{ padding: "0 20px" }}>
        {(() => {
          const CONTEXT_TYPES = new Set(["context_note", "person_detail_update", "org_detail_update"]);
          const UPDATE_TYPES = new Set(["task_update", "decision_update"]);
          const items = bundle.items || [];
          const actionable = items.filter((i) => !CONTEXT_TYPES.has(i.item_type) && !UPDATE_TYPES.has(i.item_type));
          const updates = items.filter((i) => UPDATE_TYPES.has(i.item_type));
          const context = items.filter((i) => CONTEXT_TYPES.has(i.item_type));
          const renderGroup = (groupItems, label) => groupItems.length === 0 ? null : (
            <>
              {label && (
                <div style={{ fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em", padding: "10px 0 4px", borderTop: `1px solid ${theme.border.subtle}` }}>
                  {label} ({groupItems.length})
                </div>
              )}
              {groupItems.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  bundleId={bundle.id}
                  bundleStatus={bundle.status}
                  allBundles={allBundles}
                  busy={busy}
                  lookups={lookups}
                  onAccept={() => onAcceptItem(bundle.id, item.id)}
                  onReject={() => onRejectItem(bundle.id, item.id)}
                  onRestore={() => onRestoreItem(bundle.id, item.id)}
                  onEdit={() => onEditItem(bundle.id, item)}
                  onMove={(toBundleId) => onMoveItem(item.id, bundle.id, toBundleId)}
                />
              ))}
            </>
          );
          return (
            <>
              {renderGroup(actionable, items.length > 3 && (updates.length > 0 || context.length > 0) ? "Actionable Items" : null)}
              {renderGroup(updates, "Updates to Existing Records")}
              {renderGroup(context, "Context & Profile Items")}
            </>
          );
        })()}

        {/* Add item button */}
        {!isTerminal && (
          <div style={{ padding: "12px 0" }}>
            <button
              onClick={() => onAddItem(bundle.id)}
              style={{
                ...btnBase, background: "transparent", color: theme.text.dim,
                border: `1px dashed ${theme.border.default}`, width: "100%",
                padding: "10px 14px",
              }}
            >
              + Add Item
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Item Card ───────────────────────────────────────────────────────────────

function ItemCard({ item, bundleId, bundleStatus, allBundles, busy, lookups, onAccept, onReject, onRestore, onEdit, onMove }) {
  const [moveTarget, setMoveTarget] = useState("");
  const tColor = ITEM_TYPE_COLORS[item.item_type] || ITEM_TYPE_COLORS.task;
  const sColor = BUNDLE_STATUS[item.status] || BUNDLE_STATUS.proposed;
  const isTerminal = item.status === "accepted" || item.status === "rejected";
  const bundleTerminal = bundleStatus === "accepted" || bundleStatus === "rejected";

  const people = lookups?.people || [];
  const orgs = lookups?.orgs || [];
  const personName = (id) => { const p = people.find((x) => x.id === id); return p ? (p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim()) : null; };
  const orgName = (id) => { const o = orgs.find((x) => x.id === id); return o ? o.name : null; };

  // Fields from proposed_data — resolve IDs to names for display
  const resolveValue = (key, val) => {
    if (val && typeof val === "string" && key.endsWith("_person_id")) return personName(val) || val;
    if (val && typeof val === "string" && key.endsWith("_org_id") || key === "organization_id") return orgName(val) || val;
    // Parse JSON strings that should be objects
    if (typeof val === "string" && (key === "linked_entities" || key === "participants" || key === "matter_links" || key === "changes" || key === "fields")) {
      try { return JSON.parse(val); } catch { return val; }
    }
    return val;
  };
  const proposedFields = item.proposed_data
    ? Object.entries(item.proposed_data).map(([k, v]) => [k, resolveValue(k, v)])
    : [];
  const hasOriginal = item.original_proposed_data && item.status === "edited";

  const movableBundles = allBundles.filter((b) => b.id !== bundleId);

  return (
    <div style={{
      padding: "14px 0",
      borderBottom: `1px solid ${theme.border.subtle}`,
      opacity: item.status === "rejected" ? 0.5 : 1,
    }}>
      {/* Item header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
        <Badge bg={tColor.bg} text={tColor.text} label={formatLabel(item.item_type)} />
        <Badge bg={sColor.bg} text={sColor.text} label={formatLabel(item.status)} />
        {item.reviewer_created && (
          <Badge bg="#1e1b4b" text="#a78bfa" label="Reviewer" />
        )}
        {item.confidence != null && (
          <ConfidenceIndicator value={item.confidence} />
        )}
      </div>

      {/* Update items: show existing record + changes distinctly */}
      {item.item_type.endsWith("_update") && item.proposed_data && (item.proposed_data.existing_task_id || item.proposed_data.existing_decision_id || item.proposed_data.existing_org_id) ? (
        <div style={{
          background: "rgba(96,165,250,0.06)", borderRadius: 6, padding: "10px 12px",
          marginBottom: 8, border: "1px solid rgba(96,165,250,0.15)",
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: theme.accent.blue || "#60a5fa", marginBottom: 6, textTransform: "uppercase" }}>
            Updating: {item.proposed_data.existing_task_title || item.proposed_data.existing_decision_title || item.proposed_data.existing_org_name || "existing record"}
          </div>
          {item.proposed_data.changes && typeof item.proposed_data.changes === "object" && Object.entries(item.proposed_data.changes).map(([key, val]) => (
            <div key={key} style={{ marginBottom: 4, display: "flex", gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, minWidth: 100, textTransform: "capitalize" }}>
                {key.replace(/_/g, " ")}:
              </span>
              <span style={{ fontSize: 12, color: "#93c5fd" }}>
                {typeof val === "object" ? JSON.stringify(val) : String(val ?? "")}
              </span>
            </div>
          ))}
          {item.proposed_data.change_summary && (
            <div style={{ marginTop: 6, fontSize: 12, color: theme.text.secondary, fontStyle: "italic" }}>
              {item.proposed_data.change_summary}
            </div>
          )}
        </div>
      ) : (
        /* Standard proposed data rendering */
        proposedFields.length > 0 && (
          <div style={{
            background: theme.bg.input, borderRadius: 6, padding: "10px 12px",
            marginBottom: 8, border: `1px solid ${theme.border.subtle}`,
          }}>
            {proposedFields.map(([key, val]) => {
              // Participants: render as readable cards
              if (key === "participants" && Array.isArray(val)) {
                return (
                  <div key={key} style={{ marginBottom: 6 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, textTransform: "capitalize" }}>
                      participants ({val.length}):
                    </span>
                    {val.map((p, i) => (
                      <div key={i} style={{
                        background: "rgba(96,165,250,0.06)", borderRadius: 4,
                        padding: "6px 10px", marginTop: 4, border: "1px solid rgba(96,165,250,0.1)",
                      }}>
                        <div style={{ fontSize: 12, color: theme.text.secondary }}>
                          <strong style={{ color: "#93c5fd" }}>{p.person_name || personName(p.person_id) || p.person_id?.slice(0, 8) || "?"}</strong>
                          {p.meeting_role && <span style={{ color: theme.text.dim }}> ({p.meeting_role})</span>}
                          {p.attended === false && <span style={{ color: theme.accent.red }}> [absent]</span>}
                          {p.follow_up_expected && <span style={{ color: theme.accent.yellow }}> [follow-up]</span>}
                        </div>
                        {p.key_contribution_summary && (
                          <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>{p.key_contribution_summary}</div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              }
              // Linked entities: render as readable tags
              if (key === "linked_entities" && Array.isArray(val)) {
                return (
                  <div key={key} style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint }}>linked entities: </span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 2 }}>
                      {val.map((le, i) => (
                        <span key={i} style={{
                          display: "inline-block", padding: "2px 8px", borderRadius: 4,
                          fontSize: 11, background: "rgba(94,234,212,0.1)", color: "#5eead4",
                          border: "1px solid rgba(94,234,212,0.2)",
                        }}>
                          {le.entity_name || le.entity_id?.slice(0, 8) || "?"} <span style={{ color: theme.text.dim }}>({le.relationship_role || le.entity_type})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              }
              // Matter links: render as readable list
              if (key === "matter_links" && Array.isArray(val)) {
                return (
                  <div key={key} style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint }}>matter links: </span>
                    {val.map((ml, i) => (
                      <span key={i} style={{ fontSize: 12, color: theme.text.secondary }}>
                        {ml.matter_title || (allBundles || []).find(b => b.target_matter_id === ml.matter_id)?.target_matter_title || ml.matter_id?.slice(0, 8) || "?"}{ml.relationship_type ? ` (${ml.relationship_type})` : ""}{i < val.length - 1 ? ", " : ""}
                      </span>
                    ))}
                  </div>
                );
              }
              // Fields dict (person_detail_update): render as key-value pairs
              if (key === "fields" && typeof val === "object" && val !== null && !Array.isArray(val)) {
                return (
                  <div key={key} style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint }}>profile fields:</span>
                    {Object.entries(val).map(([fk, fv]) => (
                      <div key={fk} style={{ marginLeft: 12, fontSize: 12 }}>
                        <span style={{ color: theme.text.dim }}>{fk.replace(/_/g, " ")}: </span>
                        <span style={{ color: theme.text.secondary }}>{String(fv)}</span>
                      </div>
                    ))}
                  </div>
                );
              }
              // Changes dict (task_update etc): render as field changes
              if (key === "changes" && typeof val === "object" && val !== null && !Array.isArray(val)) {
                return (
                  <div key={key} style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint }}>changes:</span>
                    {Object.entries(val).map(([ck, cv]) => (
                      <div key={ck} style={{ marginLeft: 12, fontSize: 12 }}>
                        <span style={{ color: theme.text.dim }}>{ck.replace(/_/g, " ")}: </span>
                        <span style={{ color: "#93c5fd" }}>{String(cv)}</span>
                      </div>
                    ))}
                  </div>
                );
              }
              // Default: text or JSON
              // Clean up display label: remove _person_id, _org_id suffixes
              const displayKey = key.replace(/_person_id$/, "").replace(/_org_id$/, "").replace(/^organization_id$/, "organization").replace(/_/g, " ");
              return (
                <div key={key} style={{ marginBottom: 4, display: "flex", gap: 8 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600, color: theme.text.faint,
                    minWidth: 80, textTransform: "capitalize",
                  }}>
                    {displayKey}:
                  </span>
                  <span style={{ fontSize: 12, color: theme.text.secondary }}>
                    {typeof val === "object" ? JSON.stringify(val) : String(val ?? "")}
                  </span>
                </div>
              );
            })}
          </div>
        )
      )}

      {/* Diff against original if edited */}
      {hasOriginal && (
        <div style={{
          background: "rgba(251,191,36,0.06)", borderRadius: 6, padding: "8px 12px",
          marginBottom: 8, border: "1px solid rgba(251,191,36,0.15)",
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: theme.accent.yellow, marginBottom: 4, textTransform: "uppercase" }}>
            Original (before edit)
          </div>
          {Object.entries(item.original_proposed_data).map(([key, val]) => {
            const current = item.proposed_data?.[key];
            const changed = JSON.stringify(current) !== JSON.stringify(val);
            return (
              <div key={key} style={{ marginBottom: 2, display: "flex", gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: theme.text.faint, minWidth: 80, textTransform: "capitalize" }}>
                  {key.replace(/_/g, " ")}:
                </span>
                <span style={{
                  fontSize: 12,
                  color: changed ? theme.accent.red : theme.text.dim,
                  textDecoration: changed ? "line-through" : "none",
                }}>
                  {typeof val === "object" ? JSON.stringify(val) : String(val ?? "")}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Source excerpt */}
      {item.source_excerpt && (
        <SourceExcerptViewer
          excerpt={item.source_excerpt}
          locator={item.source_locator_json}
          startTime={item.source_start_time}
          endTime={item.source_end_time}
        />
      )}

      {/* Rationale */}
      {item.rationale && (
        <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 6, lineHeight: 1.4 }}>
          {item.rationale}
        </div>
      )}

      {/* Provenance */}
      {item.moved_from_bundle_id && (
        <div style={{ fontSize: 10, color: theme.text.faint, marginBottom: 6 }}>
          Moved from bundle {item.moved_from_bundle_id.slice(0, 8)}...
        </div>
      )}

      {/* Warnings */}
      {item.warnings?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {item.warnings.map((w, i) => (
            <div key={i} style={{
              fontSize: 11, color: theme.accent.yellow, padding: "4px 8px",
              background: "rgba(245,158,11,0.08)", borderRadius: 4, marginBottom: 2,
            }}>
              {typeof w === "string" ? w : JSON.stringify(w)}
            </div>
          ))}
        </div>
      )}

      {/* Action buttons */}
      {!bundleTerminal && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {item.status === "proposed" && (
            <>
              <button
                disabled={busy[`ai-${item.id}`]}
                onClick={onAccept}
                style={{ ...btnBase, background: "#14532d", color: "#4ade80", opacity: busy[`ai-${item.id}`] ? 0.5 : 1 }}
              >
                Accept
              </button>
              <button
                disabled={busy[`ri-${item.id}`]}
                onClick={onReject}
                style={{ ...btnBase, background: "#450a0a", color: "#f87171", opacity: busy[`ri-${item.id}`] ? 0.5 : 1 }}
              >
                Reject
              </button>
              <button onClick={onEdit} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.subtle}` }}>
                Edit
              </button>
            </>
          )}
          {item.status === "edited" && (
            <>
              <button
                disabled={busy[`ai-${item.id}`]}
                onClick={onAccept}
                style={{ ...btnBase, background: "#14532d", color: "#4ade80", opacity: busy[`ai-${item.id}`] ? 0.5 : 1 }}
              >
                Accept
              </button>
              <button onClick={onEdit} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.subtle}` }}>
                Edit Again
              </button>
            </>
          )}
          {item.status === "rejected" && (
            <button
              disabled={busy[`rs-${item.id}`]}
              onClick={onRestore}
              style={{ ...btnBase, background: theme.bg.input, color: theme.accent.yellow, border: `1px solid ${theme.border.subtle}`, opacity: busy[`rs-${item.id}`] ? 0.5 : 1 }}
            >
              Restore
            </button>
          )}

          {/* Move dropdown */}
          {!isTerminal && movableBundles.length > 0 && (
            <div style={{ display: "flex", gap: 4, alignItems: "center", marginLeft: 8 }}>
              <select
                value={moveTarget}
                onChange={(e) => setMoveTarget(e.target.value)}
                style={{
                  background: theme.bg.input, color: theme.text.muted,
                  border: `1px solid ${theme.border.subtle}`, borderRadius: 5,
                  padding: "5px 8px", fontSize: 11, fontFamily: theme.font.family,
                }}
              >
                <option value="">Move to...</option>
                {movableBundles.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.target_matter_title || formatLabel(b.bundle_type)} ({b.id.slice(0, 8)})
                  </option>
                ))}
              </select>
              {moveTarget && (
                <button
                  disabled={busy[`mv-${item.id}`]}
                  onClick={() => { onMove(moveTarget); setMoveTarget(""); }}
                  style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy[`mv-${item.id}`] ? 0.5 : 1 }}
                >
                  Move
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Confidence Indicator ────────────────────────────────────────────────────

