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
import { listPeople, listOrganizations, listMatters } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import Modal from "../../components/shared/Modal";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import SourceExcerptViewer from "../../components/shared/SourceExcerptViewer";

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

function ConfidenceIndicator({ value }) {
  const pct = (value * 100).toFixed(0);
  const color = confidenceColor(value);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 40, height: 4, borderRadius: 2, background: theme.border.subtle,
        overflow: "hidden",
      }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 2, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, fontFamily: theme.font.mono }}>
        {pct}%
      </span>
    </div>
  );
}

// ── Field Schemas ───────────────────────────────────────────────────────────
// Defines every field for every item type: input type, options, required flag.
// Types: text, textarea, select, person_picker, org_picker, matter_picker, date, boolean, json

const FIELD_SCHEMAS = {
  task: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "status", label: "Status", type: "select", required: true, options: ["not started", "in progress", "waiting on others", "needs review", "done", "deferred"], defaultValue: "not started" },
    { key: "task_mode", label: "Task Mode", type: "select", required: true, options: ["action", "follow_up", "monitoring"] },
    { key: "task_type", label: "Task Type", type: "select", options: ["research issue", "draft memo", "review markup", "prepare talking points", "schedule meeting", "get clearance", "follow up with client", "redline document", "produce options memo", "send readout", "coordinate with agency partner", "other"] },
    { key: "priority", label: "Priority", type: "select", options: ["critical", "high", "normal", "low"], defaultValue: "normal" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "delegated_by_person_id", label: "Delegated By", type: "person_picker" },
    { key: "supervising_person_id", label: "Supervisor", type: "person_picker" },
    { key: "waiting_on_person_id", label: "Waiting On (Person)", type: "person_picker" },
    { key: "waiting_on_org_id", label: "Waiting On (Org)", type: "org_picker" },
    { key: "waiting_on_description", label: "Waiting On Description", type: "text" },
    { key: "trigger_description", label: "Trigger Description", type: "text" },
    { key: "expected_output", label: "Expected Output", type: "text" },
    { key: "due_date", label: "Due Date", type: "date" },
    { key: "deadline_type", label: "Deadline Type", type: "select", options: ["hard", "soft", "internal"] },
    { key: "next_follow_up_date", label: "Next Follow-up Date", type: "date" },
    { key: "description", label: "Description", type: "textarea" },
  ],
  task_update: [
    { key: "existing_task_id", label: "Task ID", type: "text", required: true },
    { key: "existing_task_title", label: "Task Title", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  decision: [
    { key: "title", label: "Title (framed as question/choice)", type: "text", required: true },
    { key: "status", label: "Status", type: "select", required: true, options: ["pending", "under consideration", "made", "deferred", "no longer needed"] },
    { key: "decision_type", label: "Decision Type", type: "select", options: ["policy", "legal", "resource", "timing", "personnel", "procedural"] },
    { key: "decision_assigned_to_person_id", label: "Decision Maker", type: "person_picker" },
    { key: "decision_due_date", label: "Decision Due Date", type: "date" },
    { key: "options_summary", label: "Options Summary", type: "textarea" },
    { key: "recommended_option", label: "Recommended Option", type: "text" },
    { key: "decision_result", label: "Decision Result", type: "text" },
    { key: "made_at", label: "Made At", type: "date" },
    { key: "notes", label: "Notes", type: "textarea" },
  ],
  decision_update: [
    { key: "existing_decision_id", label: "Decision ID", type: "text", required: true },
    { key: "existing_decision_title", label: "Decision Title", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  meeting_record: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "date_time_start", label: "Start Time", type: "date", required: true },
    { key: "date_time_end", label: "End Time", type: "date" },
    { key: "meeting_type", label: "Meeting Type", type: "select", options: ["internal working meeting", "leadership meeting", "client meeting", "interagency meeting", "industry meeting", "Hill meeting", "briefing", "check-in", "commissioner office", "other"] },
    { key: "purpose", label: "Purpose", type: "text" },
    { key: "readout_summary", label: "Readout Summary", type: "textarea" },
    { key: "boss_attends", label: "Boss Attends", type: "boolean" },
    { key: "external_parties_attend", label: "External Parties Attend", type: "boolean" },
    { key: "participants", label: "Participants", type: "participants" },
    { key: "matter_links", label: "Matter Links (JSON)", type: "json" },
  ],
  matter_update: [
    { key: "summary", label: "Summary", type: "textarea", required: true },
    { key: "update_type", label: "Update Type", type: "select", required: true, options: ["status update", "meeting readout", "document milestone", "decision made", "blocker identified", "deadline changed", "escalation", "closure note"] },
  ],
  status_change: [
    { key: "field", label: "Field to Change", type: "select", required: true, options: ["status", "priority", "sensitivity", "next_step", "blocker"] },
    { key: "old_value", label: "Old Value", type: "text" },
    { key: "new_value", label: "New Value", type: "text", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  stakeholder_addition: [
    { key: "person_id", label: "Person", type: "person_picker" },
    { key: "organization_id", label: "Organization", type: "org_picker" },
    { key: "role", label: "Role", type: "select", required: true, options: ["lead attorney", "supervisor", "requesting stakeholder", "substantive client", "reviewing stakeholder", "leadership stakeholder", "external partner", "Hill stakeholder", "outside party", "subject matter contributor", "FYI only", "requesting office", "client office", "reviewing office", "lead office", "partner agency", "counterparty", "Hill office", "affected office"] },
    { key: "engagement_level", label: "Engagement Level", type: "select", options: ["lead", "core", "consulted", "informed", "escalation only"] },
    { key: "rationale_detail", label: "Rationale", type: "text" },
  ],
  document: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "document_type", label: "Document Type", type: "select", required: true, options: ["rulemaking_text", "legal_memo", "options_memo", "comment_letter", "testimony", "talking_points", "briefing_paper", "correspondence", "report", "other"] },
    { key: "status", label: "Status", type: "select", options: ["not started", "drafting", "internal_review", "client_review", "leadership_review", "clearance", "final", "sent", "archived"], defaultValue: "not started" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "due_date", label: "Due Date", type: "date" },
    { key: "summary", label: "Summary", type: "textarea" },
  ],
  context_note: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "category", label: "Category", type: "select", required: true, options: ["people_insight", "institutional_knowledge", "process_note", "policy_operating_rule", "strategic_context", "culture_climate", "relationship_dynamic"] },
    { key: "body", label: "Body", type: "textarea", required: true },
    { key: "posture", label: "Posture", type: "select", required: true, options: ["factual", "attributed_view", "tentative", "interpretive", "sensitive"] },
    { key: "speaker_attribution", label: "Speaker Attribution", type: "text" },
    { key: "durability", label: "Durability", type: "select", options: ["ephemeral", "medium_term", "durable"], defaultValue: "durable" },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["low", "moderate", "high"], defaultValue: "low" },
    { key: "effective_date", label: "Effective Date", type: "date" },
    { key: "stale_after", label: "Stale After", type: "date" },
    { key: "linked_entities", label: "Linked Entities (JSON)", type: "json" },
  ],
  person_detail_update: [
    { key: "person_id", label: "Person", type: "person_picker", required: true },
    { key: "person_name", label: "Person Name", type: "text", required: true },
    { key: "fields", label: "Profile Fields (JSON)", type: "json", required: true, hint: '{"education_summary":"...","prior_roles_summary":"...","email":"..."}' },
  ],
  new_person: [
    { key: "full_name", label: "Full Name", type: "text", required: true },
    { key: "title", label: "Title / Role", type: "text" },
    { key: "organization_name", label: "Organization", type: "text" },
    { key: "relationship_category", label: "Relationship Category", type: "select", options: ["Boss", "Leadership", "Direct report", "Indirect report", "OGC peer", "Internal client", "Commissioner office", "Partner agency", "Hill", "Outside party"] },
    { key: "substantive_areas", label: "Substantive Areas", type: "text" },
    { key: "context", label: "Context", type: "textarea" },
  ],
  new_organization: [
    { key: "name", label: "Name", type: "text", required: true },
    { key: "organization_type", label: "Organization Type", type: "select", options: ["CFTC office", "CFTC division", "Commissioner office", "Federal agency", "White House / OMB", "Congressional office", "Regulated entity", "Exchange", "Clearinghouse", "Trade association", "Outside counsel", "Inspector General / auditor", "Other"] },
    { key: "parent_name", label: "Parent Organization", type: "text" },
    { key: "jurisdiction", label: "Jurisdiction", type: "text" },
    { key: "context", label: "Context", type: "textarea" },
  ],
  org_detail_update: [
    { key: "existing_org_id", label: "Organization", type: "org_picker", required: true },
    { key: "existing_org_name", label: "Organization Name", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true, hint: '{"jurisdiction":"..."}' },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  directive_update: [
    { key: "directive_id", label: "Directive ID", type: "text", required: true },
    { key: "directive_label", label: "Directive", type: "text", required: true },
    { key: "changes", label: "Proposed Changes (JSON)", type: "json", required: true },
    { key: "add_matter_links", label: "New Matter Links (JSON)", type: "json" },
    { key: "rationale", label: "Rationale", type: "textarea" },
  ],
  new_matter: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "matter_type", label: "Matter Type", type: "select", required: true, options: ["rulemaking", "interpretive guidance", "no-action letter", "exemptive letter", "staff advisory", "other letter", "interagency coordination", "enforcement support", "congressional response", "speech / testimony / briefing prep", "litigation-sensitive issue", "personnel / management", "administrative / ethics / process", "industry inquiry", "international matter", "regulatory review", "prospective policy", "other"] },
    { key: "status", label: "Status", type: "select", options: ["new intake", "framing issue", "research in progress", "draft in progress", "internal review", "client review", "leadership review", "external coordination", "awaiting decision", "awaiting comments", "parked / monitoring", "closed"], defaultValue: "new intake" },
    { key: "priority", label: "Priority", type: "select", required: true, options: ["critical this week", "important this month", "strategic / slow burn", "monitoring only"] },
    { key: "sensitivity", label: "Sensitivity", type: "select", required: true, options: ["routine", "internal only", "leadership-sensitive", "deliberative / predecisional", "enforcement-sensitive", "congressional-sensitive"] },
    { key: "next_step", label: "Next Step", type: "text", required: true },
    { key: "description", label: "Description", type: "textarea" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "requesting_organization_id", label: "Requesting Organization", type: "org_picker" },
    { key: "regulatory_stage", label: "Regulatory Stage", type: "select", options: ["concept", "drafting", "proposed", "comment_period", "final_review", "published", "effective", "withdrawn", "long_term"] },
    { key: "rin", label: "RIN", type: "text" },
    { key: "docket_number", label: "Docket Number", type: "text" },
    { key: "cfr_citation", label: "CFR Citation", type: "text" },
  ],
};

const ITEM_TYPES = Object.keys(FIELD_SCHEMAS);

const INPUT_STYLE = {
  width: "100%", background: theme.bg.input, color: theme.text.secondary,
  border: `1px solid ${theme.border.default}`, borderRadius: 6,
  padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
};

// ── Schema Field Renderer ──────────────────────────────────────────────────

function SchemaField({ field, value, onChange, people, orgs, matters }) {
  const label = (
    <label style={{
      display: "block", fontSize: 11, fontWeight: 600,
      color: theme.text.faint, marginBottom: 4,
    }}>
      {field.label}{field.required ? <span style={{ color: theme.accent.red }}> *</span> : ""}
    </label>
  );

  const wrap = (input) => (
    <div style={{ marginBottom: 14 }}>
      {label}
      {input}
      {field.hint && <div style={{ fontSize: 10, color: theme.text.dim, marginTop: 2 }}>e.g. {field.hint}</div>}
    </div>
  );

  switch (field.type) {
    case "select":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">--</option>
          {(field.options || []).map((o) => (
            <option key={o} value={o}>{formatLabel(o)}</option>
          ))}
        </select>
      );

    case "person_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select person --</option>
          {(people || []).map((p) => (
            <option key={p.id} value={p.id}>{p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.id}</option>
          ))}
        </select>
      );

    case "org_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select organization --</option>
          {(orgs || []).map((o) => (
            <option key={o.id} value={o.id}>{o.name || o.id}</option>
          ))}
        </select>
      );

    case "matter_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select matter --</option>
          {(matters || []).map((m) => (
            <option key={m.id} value={m.id}>{m.title || m.id}</option>
          ))}
        </select>
      );

    case "date":
      return wrap(
        <input type="date" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE} />
      );

    case "boolean":
      return (
        <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={!!value}
            onChange={(e) => onChange(e.target.checked ? 1 : 0)}
            style={{ width: 16, height: 16, accentColor: theme.accent.blue }} />
          <label style={{ fontSize: 12, color: theme.text.secondary }}>{field.label}</label>
        </div>
      );

    case "textarea":
      return wrap(
        <textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          rows={3} style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.family, resize: "vertical" }} />
      );

    case "participants": {
      const MEETING_ROLES = ["chair", "presenter", "attendee", "decision-maker", "note-taker", "guest"];
      const parts = Array.isArray(value) ? value : [];
      const updatePart = (idx, key, val) => {
        const updated = parts.map((p, i) => i === idx ? { ...p, [key]: val } : p);
        onChange(updated);
      };
      const addPart = () => onChange([...parts, { person_id: "", meeting_role: "attendee", attended: true, key_contribution_summary: "", stance_summary: "", follow_up_expected: false }]);
      const removePart = (idx) => onChange(parts.filter((_, i) => i !== idx));
      const personName = (pid) => {
        const p = (people || []).find((x) => x.id === pid);
        return p ? (p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || pid) : pid;
      };

      return (
        <div style={{ marginBottom: 14 }}>
          {label}
          {parts.map((p, idx) => (
            <div key={idx} style={{
              background: theme.bg.input, border: `1px solid ${theme.border.subtle}`,
              borderRadius: 6, padding: "10px 12px", marginBottom: 6,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint }}>Participant {idx + 1}</span>
                <button onClick={() => removePart(idx)} style={{ ...btnBase, padding: "2px 8px", fontSize: 10, background: "transparent", color: theme.accent.red, border: `1px solid ${theme.accent.red}` }}>Remove</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Person</div>
                  <select value={p.person_id || ""} onChange={(e) => updatePart(idx, "person_id", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }}>
                    <option value="">--</option>
                    {(people || []).map((pp) => <option key={pp.id} value={pp.id}>{pp.full_name || `${pp.first_name || ""} ${pp.last_name || ""}`.trim() || pp.id}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Role</div>
                  <select value={p.meeting_role || ""} onChange={(e) => updatePart(idx, "meeting_role", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }}>
                    <option value="">--</option>
                    {MEETING_ROLES.map((r) => <option key={r} value={r}>{formatLabel(r)}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={!!p.attended} onChange={(e) => updatePart(idx, "attended", e.target.checked)} style={{ width: 14, height: 14 }} />
                  <span style={{ fontSize: 11, color: theme.text.secondary }}>Attended</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={!!p.follow_up_expected} onChange={(e) => updatePart(idx, "follow_up_expected", e.target.checked)} style={{ width: 14, height: 14 }} />
                  <span style={{ fontSize: 11, color: theme.text.secondary }}>Follow-up expected</span>
                </div>
              </div>
              <div style={{ marginBottom: 4 }}>
                <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Key Contribution</div>
                <input type="text" value={p.key_contribution_summary || ""} onChange={(e) => updatePart(idx, "key_contribution_summary", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Stance</div>
                <input type="text" value={p.stance_summary || ""} onChange={(e) => updatePart(idx, "stance_summary", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }} />
              </div>
            </div>
          ))}
          <button onClick={addPart} style={{ ...btnBase, background: "transparent", color: theme.text.dim, border: `1px dashed ${theme.border.default}`, width: "100%", padding: "8px" }}>
            + Add Participant
          </button>
        </div>
      );
    }

    case "json":
      return wrap(
        <textarea
          value={typeof value === "object" && value !== null ? JSON.stringify(value, null, 2) : (value ?? "")}
          onChange={(e) => {
            try { onChange(JSON.parse(e.target.value)); }
            catch { onChange(e.target.value); }
          }}
          rows={4}
          style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.mono, resize: "vertical" }}
        />
      );

    default: // text
      return wrap(
        <input type="text" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE} />
      );
  }
}

// ── Lookup data hook ───────────────────────────────────────────────────────

function useReviewLookups(isOpen) {
  const [people, setPeople] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [matters, setMatters] = useState([]);

  useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      listPeople({ limit: 200 }).catch(() => ({ items: [] })),
      listOrganizations({ limit: 200 }).catch(() => ({ items: [] })),
      listMatters({ limit: 200 }).catch(() => ({ items: [] })),
    ]).then(([ppl, orgList, matterList]) => {
      setPeople(ppl.items || ppl || []);
      setOrgs(orgList.items || orgList || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  return { people, orgs, matters };
}

// ── Edit Item Modal ─────────────────────────────────────────────────────────

function EditItemModal({ isOpen, onClose, item, busy, onSave }) {
  const [fields, setFields] = useState({});
  const { people, orgs, matters } = useReviewLookups(isOpen);

  useEffect(() => {
    if (item?.proposed_data) {
      setFields({ ...item.proposed_data });
    }
  }, [item]);

  if (!isOpen || !item) return null;

  const schema = FIELD_SCHEMAS[item.item_type] || [];
  const schemaKeys = new Set(schema.map((f) => f.key));

  const handleFieldChange = (key, val) => {
    setFields((f) => ({ ...f, [key]: val }));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit ${formatLabel(item.item_type)}`} width={560}>
      <div style={{ maxHeight: "60vh", overflowY: "auto", paddingRight: 8 }}>
        {/* Schema-defined fields first */}
        {schema.map((field) => (
          <SchemaField
            key={field.key}
            field={field}
            value={fields[field.key]}
            onChange={(val) => handleFieldChange(field.key, val)}
            people={people} orgs={orgs} matters={matters}
          />
        ))}

        {/* Extra fields in proposed_data not in schema (backward compat) */}
        {Object.entries(fields)
          .filter(([key]) => !schemaKeys.has(key))
          .map(([key, val]) => (
            <div key={key} style={{ marginBottom: 14 }}>
              <label style={{
                display: "block", fontSize: 11, fontWeight: 600,
                color: theme.text.dim, marginBottom: 4, fontStyle: "italic",
              }}>
                {key.replace(/_/g, " ")} (extra)
              </label>
              {typeof val === "object" && val !== null ? (
                <textarea
                  value={JSON.stringify(val, null, 2)}
                  onChange={(e) => {
                    try { handleFieldChange(key, JSON.parse(e.target.value)); }
                    catch { handleFieldChange(key, e.target.value); }
                  }}
                  rows={3}
                  style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.mono, resize: "vertical" }}
                />
              ) : (
                <input type="text" value={val ?? ""}
                  onChange={(e) => handleFieldChange(key, e.target.value)}
                  style={INPUT_STYLE} />
              )}
            </div>
          ))}
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
        <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
          Cancel
        </button>
        <button
          disabled={busy}
          onClick={() => onSave(fields)}
          style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
        >
          {busy ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </Modal>
  );
}

// ── Add Item Modal ──────────────────────────────────────────────────────────

function AddItemModal({ isOpen, onClose, busy, onSave }) {
  const [itemType, setItemType] = useState("task");
  const [fields, setFields] = useState({});
  const { people, orgs, matters } = useReviewLookups(isOpen);

  useEffect(() => {
    // Build initial values from schema
    const schema = FIELD_SCHEMAS[itemType] || [];
    const initial = {};
    schema.forEach((f) => {
      if (f.defaultValue !== undefined) initial[f.key] = f.defaultValue;
      else if (f.type === "json") initial[f.key] = {};
      else if (f.type === "boolean") initial[f.key] = 0;
      else initial[f.key] = "";
    });
    setFields(initial);
  }, [itemType]);

  if (!isOpen) return null;

  const schema = FIELD_SCHEMAS[itemType] || [];

  const handleFieldChange = (key, val) => {
    setFields((f) => ({ ...f, [key]: val }));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Item" width={560}>
      <div>
        <div style={{ marginBottom: 14 }}>
          <label style={{
            display: "block", fontSize: 11, fontWeight: 600,
            color: theme.text.faint, marginBottom: 4,
          }}>
            Item Type
          </label>
          <select
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
            style={INPUT_STYLE}
          >
            {ITEM_TYPES.map((t) => (
              <option key={t} value={t}>{formatLabel(t)}</option>
            ))}
          </select>
        </div>

        <div style={{ maxHeight: "60vh", overflowY: "auto", paddingRight: 8 }}>
          {schema.map((field) => (
            <SchemaField
              key={field.key}
              field={field}
              value={fields[field.key]}
              onChange={(val) => handleFieldChange(field.key, val)}
              people={people} orgs={orgs} matters={matters}
            />
          ))}
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={busy}
            onClick={() => onSave(itemType, fields)}
            style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
          >
            {busy ? "Adding..." : "Add Item"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Create Bundle Modal ─────────────────────────────────────────────────────

function CreateBundleModal({ isOpen, onClose, busy, onSave }) {
  const [bundleType, setBundleType] = useState("standalone");
  const [matterTitle, setMatterTitle] = useState("");
  const [rationale, setRationale] = useState("");
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Bundle" width={480}>
      <div>
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Bundle Type
          </label>
          <select
            value={bundleType}
            onChange={(e) => setBundleType(e.target.value)}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          >
            <option value="standalone">Standalone</option>
            <option value="existing_matter">Existing Matter</option>
            <option value="new_matter">New Matter</option>
          </select>
        </div>

        {(bundleType === "existing_matter" || bundleType === "new_matter") && (
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
              Matter Title
            </label>
            <input
              type="text"
              value={matterTitle}
              onChange={(e) => setMatterTitle(e.target.value)}
              placeholder="Enter matter title..."
              style={{
                width: "100%", background: theme.bg.input, color: theme.text.secondary,
                border: `1px solid ${theme.border.default}`, borderRadius: 6,
                padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              }}
            />
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Rationale
          </label>
          <input
            type="text"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            placeholder="Why create this bundle?"
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Intelligence Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              resize: "vertical",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={busy}
            onClick={() => onSave({
              bundleType,
              targetMatterTitle: matterTitle || null,
              rationale: rationale || "Reviewer-created bundle",
              intelligenceNotes: notes || null,
            })}
            style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
          >
            {busy ? "Creating..." : "Create Bundle"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Merge Bundles Modal ─────────────────────────────────────────────────────

function MergeBundlesModal({ isOpen, onClose, bundles, sourceId, busy, onMerge }) {
  const [source, setSource] = useState(sourceId || "");
  const [target, setTarget] = useState("");

  useEffect(() => {
    if (sourceId) setSource(sourceId);
  }, [sourceId]);

  if (!isOpen) return null;

  const availableTargets = bundles.filter((b) => b.id !== source);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Merge Bundles" width={480}>
      <div>
        <p style={{ fontSize: 13, color: theme.text.muted, margin: "0 0 16px", lineHeight: 1.5 }}>
          All items from the source bundle will be moved into the target bundle. The source bundle will be removed.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Source Bundle (will be removed)
          </label>
          <select
            value={source}
            onChange={(e) => { setSource(e.target.value); setTarget(""); }}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          >
            <option value="">Select source...</option>
            {bundles.map((b) => (
              <option key={b.id} value={b.id}>
                {b.target_matter_title || formatLabel(b.bundle_type)} ({b.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Target Bundle (will receive items)
          </label>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={!source}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              opacity: source ? 1 : 0.5,
            }}
          >
            <option value="">Select target...</option>
            {availableTargets.map((b) => (
              <option key={b.id} value={b.id}>
                {b.target_matter_title || formatLabel(b.bundle_type)} ({b.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={!source || !target || busy}
            onClick={() => onMerge(source, target)}
            style={{
              ...btnBase, background: "#1e40af", color: "#fff",
              opacity: (!source || !target || busy) ? 0.5 : 1,
              cursor: (!source || !target) ? "not-allowed" : "pointer",
            }}
          >
            {busy ? "Merging..." : "Merge Bundles"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Shared sub-components ───────────────────────────────────────────────────

function CountBox({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || theme.text.primary, fontFamily: theme.font.mono }}>
        {value}
      </div>
    </div>
  );
}

function CollapsiblePanel({ title, open, onToggle, children }) {
  return (
    <div style={{
      background: theme.bg.card, borderRadius: theme.card.radius,
      border: `1px solid ${theme.border.default}`, marginTop: 12,
      overflow: "hidden",
    }}>
      <button
        onClick={onToggle}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          width: "100%", padding: "12px 20px", background: "transparent",
          border: "none", cursor: "pointer", color: theme.text.muted,
          fontSize: 13, fontWeight: 600, fontFamily: theme.font.family,
          borderBottom: open ? `1px solid ${theme.border.subtle}` : "none",
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: 10, color: theme.text.faint }}>{open ? "\u25b2" : "\u25bc"}</span>
      </button>
      {open && (
        <div style={{ padding: "14px 20px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function SuppressionSection({ title, items }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: theme.text.faint,
        textTransform: "uppercase", marginBottom: 6,
      }}>
        {title} ({items.length})
      </div>
      {items.map((item, i) => (
        <div key={i} style={{
          fontSize: 12, color: theme.text.dim, padding: "5px 0",
          borderBottom: i < items.length - 1 ? `1px solid ${theme.border.subtle}` : "none",
          lineHeight: 1.4,
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

function MetaField({ label, value, mono }) {
  return (
    <div>
      <div style={{
        fontSize: 10, fontWeight: 700, color: theme.text.faint,
        textTransform: "uppercase", marginBottom: 2,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 12, color: theme.text.secondary,
        fontFamily: mono ? theme.font.mono : theme.font.family,
        wordBreak: "break-all",
      }}>
        {value || "\u2014"}
      </div>
    </div>
  );
}
