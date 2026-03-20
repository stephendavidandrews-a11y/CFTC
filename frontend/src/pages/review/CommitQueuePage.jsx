import React, { useState, useEffect, useCallback } from "react";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { useToastContext } from "../../contexts/ToastContext";
import { listCommunications, undoCommunication, retryCommunication } from "../../api/ai";
import Badge from "../../components/shared/Badge";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import Modal from "../../components/shared/Modal";
import EmptyState from "../../components/shared/EmptyState";
import SSEBanner from "../../components/shared/SSEBanner";

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatDuration(seconds) {
  if (seconds == null) return "\u2014";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return "\u2014";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString();
}

const STATUS_BADGE = {
  reviewed: { bg: "#14532d", text: "#4ade80", label: "Ready" },
  committing: { bg: "#422006", text: "#fbbf24", label: "Committing" },
  complete: { bg: "#14532d", text: "#4ade80", label: "Complete" },
  error: { bg: "#450a0a", text: "#f87171", label: "Error" },
};

const cardStyle = {
  background: theme.bg.card,
  borderRadius: theme.card.radius,
  border: `1px solid ${theme.border.default}`,
  padding: "16px 20px",
  marginBottom: 10,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 16,
};

const btnStyle = (bg, color) => ({
  padding: "7px 16px", borderRadius: 7, fontSize: 12, fontWeight: 600,
  background: bg, color, border: "none", cursor: "pointer",
});

/**
 * Classify raw error messages into operator-friendly descriptions.
 * Returns { summary, detail, suggestion }.
 */
function classifyError(errorMessage, errorStage) {
  const msg = (errorMessage || "").toLowerCase();

  if (msg.includes("connect") || msg.includes("refused") || msg.includes("unreachable") || msg.includes("econnrefused")) {
    return {
      summary: "Tracker service unreachable",
      detail: "The tracker service is not responding.",
      suggestion: "Check service status and retry.",
    };
  }
  if (msg.includes("timeout") || msg.includes("timed out") || msg.includes("deadline")) {
    return {
      summary: "Request timed out",
      detail: "The commit timed out before completing.",
      suggestion: "The tracker may still be processing \u2014 check before retrying.",
    };
  }
  if (msg.includes("validation") || msg.includes("invalid") || msg.includes("required field") || msg.includes("constraint")) {
    return {
      summary: "Validation error",
      detail: "The tracker rejected the data due to a validation rule.",
      suggestion: "Edit the item to fix the issue and retry.",
    };
  }
  if (msg.includes("schema") || msg.includes("format") || msg.includes("unprocessable") || msg.includes("422")) {
    return {
      summary: "Schema mismatch",
      detail: "The tracker rejected the data format.",
      suggestion: "This may indicate a version mismatch between services.",
    };
  }
  if (msg.includes("401") || msg.includes("403") || msg.includes("unauthorized") || msg.includes("forbidden")) {
    return {
      summary: "Authentication error",
      detail: "The AI service could not authenticate with the tracker.",
      suggestion: "Check tracker credentials in the service configuration.",
    };
  }
  if (msg.includes("500") || msg.includes("internal server")) {
    return {
      summary: "Tracker internal error",
      detail: "The tracker encountered an internal error.",
      suggestion: "Check tracker logs and retry.",
    };
  }

  // Fallback — show the raw message but still provide stage context
  return {
    summary: errorStage === "writeback" ? "Writeback failed" : "Commit failed",
    detail: errorMessage || "Unknown error during commit.",
    suggestion: "Review the error details and retry.",
  };
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CommitQueuePage() {
  const toast = useToastContext();
  const { connected, on } = useAIEvents(["commit_complete", "communication_undo"]);

  // Fetch each section
  const ready = useApi(
    () => Promise.all([
      listCommunications({ status: "reviewed" }),
      listCommunications({ status: "committing" }),
    ]).then(([r, c]) => ({ items: [...(r.items || []), ...(c.items || [])] })),
    []
  );
  const committed = useApi(
    () => listCommunications({ status: "complete" }),
    []
  );
  const failed = useApi(
    () => listCommunications({ status: "error" }),
    []
  );

  const refetchAll = useCallback(() => {
    ready.refetch();
    committed.refetch();
    failed.refetch();
  }, [ready, committed, failed]);

  // Auto-refresh on SSE events
  useEffect(() => {
    const unsub1 = on("commit_complete", () => refetchAll());
    const unsub2 = on("communication_undo", () => refetchAll());
    return () => { unsub1(); unsub2(); };
  }, [on, refetchAll]);

  // Undo state
  const [undoConfirm, setUndoConfirm] = useState(null);
  const [conflictModal, setConflictModal] = useState(null);
  const [busy, setBusy] = useState({});

  const handleUndo = async (id, force = false) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try {
      await undoCommunication(id, force);
      toast.success("Communication undone successfully");
      setConflictModal(null);
      refetchAll();
    } catch (err) {
      if (err.isConflict) {
        setConflictModal({ id, detail: err.detail });
      } else {
        toast.error(`Undo failed: ${err.message}`);
      }
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  };

  const handleRetry = async (id) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try {
      await retryCommunication(id);
      toast.success("Retry initiated");
      refetchAll();
    } catch (err) {
      toast.error(`Retry failed: ${err.message}`);
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  };

  const readyItems = ready.data?.items || [];
  const committedItems = committed.data?.items || [];
  const failedItems = (failed.data?.items || []).filter(
    (c) => c.error_stage === "committing" || c.error_stage === "writeback"
  );

  const anyLoading = ready.loading || committed.loading || failed.loading;

  return (
    <div style={{ padding: "28px 32px" }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{
          fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0,
          fontFamily: theme.font.family,
        }}>
          Ready to Commit
        </h1>
        <p style={{ fontSize: 13, color: theme.text.dim, margin: "4px 0 0" }}>
          Reviewed communications awaiting writeback, recently committed, and failed commits
        </p>
      </div>

      <SSEBanner connected={connected} />

      {anyLoading && (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.faint, fontSize: 13 }}>
          Loading commit queue...
        </div>
      )}

      {!anyLoading && (
        <>
          {/* ── Ready / In Progress ─────────────────── */}
          <SectionHeader title="Ready / In Progress" count={readyItems.length} />
          {readyItems.length === 0 ? (
            <EmptyCard message="No communications are ready to commit." />
          ) : (
            readyItems.map((c) => (
              <div key={c.id} style={cardStyle}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>
                    {c.title || c.original_filename || "Untitled"}
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.dim, display: "flex", gap: 12 }}>
                    <span>{formatDuration(c.duration_seconds)}</span>
                    <span>{c.bundle_count || 0} bundles</span>
                    <span>{c.item_count || 0} items</span>
                    <span>{formatRelativeTime(c.updated_at)}</span>
                  </div>
                </div>
                <Badge {...(STATUS_BADGE[c.processing_status] || STATUS_BADGE.reviewed)} />
              </div>
            ))
          )}

          {/* ── Recently Committed ───────────────────── */}
          <SectionHeader title="Recently Committed" count={committedItems.length} />
          {committedItems.length === 0 ? (
            <EmptyCard message="No recently committed communications." />
          ) : (
            committedItems.map((c) => (
              <div key={c.id} style={cardStyle}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>
                    {c.title || c.original_filename || "Untitled"}
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.dim, display: "flex", gap: 12 }}>
                    <span>{formatDuration(c.duration_seconds)}</span>
                    <span>{c.bundle_count || 0} bundles</span>
                    <span>{c.item_count || 0} items</span>
                    <span>Committed {formatRelativeTime(c.updated_at)}</span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Badge {...STATUS_BADGE.complete} />
                  <button
                    disabled={busy[c.id]}
                    onClick={() => setUndoConfirm(c.id)}
                    style={{
                      ...btnStyle("#991b1b", "#fff"),
                      opacity: busy[c.id] ? 0.5 : 1,
                    }}
                  >
                    {busy[c.id] ? "Undoing..." : "Undo"}
                  </button>
                </div>
              </div>
            ))
          )}

          {/* ── Failed ──────────────────────────────── */}
          <SectionHeader title="Failed Commits" count={failedItems.length} />
          {failedItems.length === 0 ? (
            <EmptyCard message="No failed commits." />
          ) : (
            failedItems.map((c) => {
              const err = classifyError(c.error_message, c.error_stage);
              return (
              <div key={c.id} style={{ ...cardStyle, borderColor: "rgba(239,68,68,0.3)" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>
                    {c.title || c.original_filename || "Untitled"}
                  </div>
                  <div style={{ fontSize: 12, color: theme.accent.red, fontWeight: 600, marginBottom: 2 }}>
                    {err.summary}
                  </div>
                  <div style={{ fontSize: 12, color: theme.accent.redLight, marginBottom: 2, opacity: 0.85 }}>
                    {err.detail}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 4 }}>
                    {err.suggestion}
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.dim }}>
                    {formatRelativeTime(c.updated_at)}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Badge {...STATUS_BADGE.error} />
                  <button
                    disabled={busy[c.id]}
                    onClick={() => handleRetry(c.id)}
                    style={{
                      ...btnStyle("#1e40af", "#fff"),
                      opacity: busy[c.id] ? 0.5 : 1,
                    }}
                  >
                    {busy[c.id] ? "Retrying..." : "Retry"}
                  </button>
                </div>
              </div>
              );
            })
          )}
        </>
      )}

      {/* Undo confirm dialog */}
      <ConfirmDialog
        isOpen={!!undoConfirm}
        onClose={() => setUndoConfirm(null)}
        onConfirm={() => handleUndo(undoConfirm)}
        title="Undo Commit"
        message="This will reverse all tracker writes for this communication. Are you sure?"
        confirmLabel="Undo Commit"
        danger
      />

      {/* Conflict modal (409) */}
      <Modal
        isOpen={!!conflictModal}
        onClose={() => setConflictModal(null)}
        title="Undo Conflict"
        width={520}
      >
        <div style={{ color: theme.text.muted, fontSize: 13, lineHeight: 1.6 }}>
          <p style={{ marginTop: 0 }}>
            Some fields have been modified since the commit. Forcing the undo may overwrite these changes.
          </p>
          {conflictModal?.detail && (() => {
            const d = conflictModal.detail;
            const conflicts = d.conflicts || [];
            // Group by record
            const grouped = {};
            conflicts.forEach((c) => {
              const key = c.target_record_id;
              if (!grouped[key]) grouped[key] = { table: c.target_table, write_type: c.write_type, fields: [] };
              grouped[key].fields.push(c);
            });
            return (
              <div style={{ margin: "12px 0" }}>
                <div style={{ fontSize: 13, color: theme.accent.yellow, fontWeight: 600, marginBottom: 8 }}>
                  {d.conflict_count || conflicts.length} conflict{(d.conflict_count || conflicts.length) !== 1 ? "s" : ""} detected
                </div>
                <div style={{ maxHeight: 280, overflow: "auto" }}>
                  {Object.entries(grouped).map(([recId, info]) => (
                    <div key={recId} style={{
                      background: theme.bg.input, borderRadius: 6, padding: 10,
                      marginBottom: 8, border: `1px solid ${theme.border.subtle}`,
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, marginBottom: 6 }}>
                        {info.table} <span style={{ color: theme.text.dim, fontWeight: 400 }}>({info.write_type})</span>
                      </div>
                      {info.fields.map((f, i) => (
                        <div key={i} style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gap: 6, fontSize: 11, marginBottom: 4 }}>
                          <span style={{ color: theme.accent.blue, fontFamily: theme.font.mono }}>{f.field_name}</span>
                          <span style={{ color: theme.accent.red }}>was: {String(f.written_value).substring(0, 40)}</span>
                          <span style={{ color: theme.accent.green }}>now: {String(f.current_value).substring(0, 40)}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 8 }}>
                  These fields were modified after the AI commit. Force undo will delete/restore records regardless.
                </div>
              </div>
            );
          })()}
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
            <button
              onClick={() => setConflictModal(null)}
              style={btnStyle(theme.bg.input, theme.text.muted)}
            >
              Cancel
            </button>
            <button
              disabled={busy[conflictModal?.id]}
              onClick={() => handleUndo(conflictModal.id, true)}
              style={{
                ...btnStyle("#991b1b", "#fff"),
                opacity: busy[conflictModal?.id] ? 0.5 : 1,
              }}
            >
              {busy[conflictModal?.id] ? "Forcing..." : "Force Undo"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ title, count }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      margin: "24px 0 12px", paddingBottom: 8,
      borderBottom: `1px solid ${theme.border.subtle}`,
    }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, color: theme.text.secondary, margin: 0 }}>
        {title}
      </h2>
      <span style={{
        fontSize: 11, fontWeight: 600, color: theme.text.faint,
        background: theme.bg.input, padding: "2px 8px", borderRadius: 4,
      }}>
        {count}
      </span>
    </div>
  );
}

function EmptyCard({ message }) {
  return (
    <div style={{
      background: theme.bg.card,
      borderRadius: theme.card.radius,
      border: `1px solid ${theme.border.default}`,
      padding: "24px 20px",
      textAlign: "center",
      color: theme.text.faint,
      fontSize: 13,
    }}>
      {message}
    </div>
  );
}
