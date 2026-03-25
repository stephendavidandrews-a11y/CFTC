import React, { useState, useMemo } from "react";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import {
  listCommunications, uploadAudio, retryCommunication,
  archiveCommunication, unarchiveCommunication, deleteCommunication,
} from "../../api/ai";
import { useToastContext } from "../../contexts/ToastContext";
import DataTable from "../../components/shared/DataTable";
import Badge from "../../components/shared/Badge";
import Modal from "../../components/shared/Modal";
import EmptyState from "../../components/shared/EmptyState";
import { formatDate, formatDateTime } from "../../utils/dateUtils";
import UploadAudioModal from "../../components/shared/UploadAudioModal";

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



const ALL_STATUSES = [
  { value: "", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "awaiting_bundle_review", label: "Awaiting Bundle Review" },
  { value: "bundle_review_in_progress", label: "Bundle Review In Progress" },
  { value: "reviewed", label: "Reviewed" },
  { value: "committing", label: "Committing" },
  { value: "complete", label: "Complete" },
  { value: "error", label: "Error" },
];

const STATUS_STYLES = {
  pending: { bg: "#1f2937", text: "#9ca3af", label: "Pending" },
  processing: { bg: "#1e3a5f", text: "#60a5fa", label: "Processing" },
  awaiting_bundle_review: { bg: "#1e3a5f", text: "#60a5fa", label: "Awaiting Review" },
  bundle_review_in_progress: { bg: "#422006", text: "#fbbf24", label: "In Progress" },
  reviewed: { bg: "#14532d", text: "#4ade80", label: "Reviewed" },
  committing: { bg: "#422006", text: "#fbbf24", label: "Committing" },
  complete: { bg: "#14532d", text: "#4ade80", label: "Complete" },
  error: { bg: "#450a0a", text: "#f87171", label: "Error" },
};

function statusBadge(status) {
  const s = STATUS_STYLES[status] || { bg: "#1f2937", text: "#9ca3af", label: status || "Unknown" };
  return <Badge bg={s.bg} text={s.text} label={s.label} />;
}

// ── Columns ─────────────────────────────────────────────────────────────────

const columns = [
  {
    key: "title",
    label: "Title",
    width: "22%",
    render: (val, row) => (
      <span style={{ color: theme.text.primary, fontWeight: 600, fontSize: 13 }}>
        {row?.title || val || row?.original_filename || "Untitled"}
      </span>
    ),
  },
  {
    key: "source_type",
    label: "Source",
    width: 90,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        {val || "\u2014"}
      </span>
    ),
  },
  {
    key: "processing_status",
    label: "Status",
    width: 140,
    render: (val) => statusBadge(val),
  },
  {
    key: "duration_seconds",
    label: "Duration",
    width: 80,
    render: (val) => (
      <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.muted }}>
        {formatDuration(val)}
      </span>
    ),
  },
  {
    key: "bundle_count",
    label: "Bundles",
    width: 70,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>{val ?? "\u2014"}</span>
    ),
  },
  {
    key: "item_count",
    label: "Items",
    width: 60,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>{val ?? "\u2014"}</span>
    ),
  },
  {
    key: "created_at",
    label: "Created",
    width: 110,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.dim }}>{formatDate(val)}</span>
    ),
  },
  {
    key: "updated_at",
    label: "Updated",
    width: 110,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.dim }}>{formatDate(val)}</span>
    ),
  },
];

// ── Component ───────────────────────────────────────────────────────────────

export default function CommunicationsArchivePage() {
  const toast = useToastContext();
  const [statusFilter, setStatusFilter] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [detailItem, setDetailItem] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const params = useMemo(() => {
    const p = {};
    if (statusFilter) p.status = statusFilter;
    if (showArchived) p.include_archived = "true";
    return p;
  }, [statusFilter, showArchived]);

  const { data, loading, error, refetch } = useApi(
    () => listCommunications(params),
    [statusFilter, showArchived]
  );

  const items = data?.items || [];

  return (
    <div style={{ padding: "28px 32px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{
            fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0,
            fontFamily: theme.font.family,
          }}>
            Communications
          </h1>
          <p style={{ fontSize: 13, color: theme.text.dim, margin: "4px 0 0" }}>
            Archive of all processed communications
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 7,
              padding: "8px 12px", fontSize: 13, fontFamily: theme.font.family,
              cursor: "pointer", outline: "none",
            }}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          {/* Show archived toggle */}
          <label style={{
            display: "flex", alignItems: "center", gap: 6,
            fontSize: 12, color: theme.text.dim, cursor: "pointer", whiteSpace: "nowrap",
          }}>
            <input
              type="checkbox"
              checked={showArchived}
              onChange={() => setShowArchived((v) => !v)}
              style={{ accentColor: theme.accent.blue }}
            />
            Show archived
          </label>

          {/* Upload button */}
          <button
            onClick={() => setUploadOpen(true)}
            style={{
              padding: "8px 16px", borderRadius: 7, fontSize: 13, fontWeight: 600,
              background: "#1e40af", color: "#fff", border: "none", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap",
            }}
          >
            <span style={{ fontSize: 15 }}>{"\u2191"}</span> Upload Audio
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{
        background: theme.bg.card,
        borderRadius: theme.card.radius,
        border: `1px solid ${theme.border.default}`,
        padding: "4px 0",
      }}>
        {loading && (
          <div style={{ padding: 40, textAlign: "center", color: theme.text.faint, fontSize: 13 }}>
            Loading communications...
          </div>
        )}

        {error && (
          <div style={{ padding: 40, textAlign: "center" }}>
            <div style={{ color: theme.accent.red, fontSize: 14, marginBottom: 8 }}>
              Failed to load communications
            </div>
            <div style={{ color: theme.text.faint, fontSize: 12, marginBottom: 16 }}>
              {error.message}
            </div>
            <button
              onClick={refetch}
              style={{
                padding: "8px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: "#1e40af", color: "#fff", border: "none", cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <EmptyState
            icon="◎"
            title="No communications found"
            message={statusFilter
              ? `No communications with status "${statusFilter}".`
              : "No communications have been processed yet."}
          />
        )}

        {!loading && !error && items.length > 0 && (
          <DataTable
            columns={columns}
            data={items}
            onRowClick={(row) => setDetailItem(row)}
            pageSize={25}
            emptyMessage="No communications"
          />
        )}
      </div>

      {/* Detail Modal */}
      <Modal
        isOpen={!!detailItem}
        onClose={() => setDetailItem(null)}
        title={detailItem?.title || detailItem?.original_filename || "Communication Detail"}
        width={620}
      >
        {detailItem && (
          <CommunicationDetail
            item={detailItem}
            onRetry={async () => {
              try {
                await retryCommunication(detailItem.id);
                toast.success("Retry started");
                setDetailItem(null);
                refetch();
              } catch (e) { toast.error(e.message); }
            }}
            onArchive={async () => {
              try {
                await archiveCommunication(detailItem.id);
                toast.success("Communication archived");
                setDetailItem(null);
                refetch();
              } catch (e) { toast.error(e.message); }
            }}
            onUnarchive={async () => {
              try {
                await unarchiveCommunication(detailItem.id);
                toast.success("Communication restored");
                setDetailItem(null);
                refetch();
              } catch (e) { toast.error(e.message); }
            }}
            onDelete={async () => {
              if (!window.confirm("Permanently delete this communication and all its data? This cannot be undone.")) return;
              try {
                await deleteCommunication(detailItem.id);
                toast.success("Communication deleted");
                setDetailItem(null);
                refetch();
              } catch (e) { toast.error(e.message); }
            }}
          />
        )}
      </Modal>

      {/* Upload Audio Modal */}
      <UploadAudioModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={async (file, title, sensitivityFlags) => {
          await uploadAudio(file, title, sensitivityFlags);
          toast.success("Upload started \u2014 processing will begin automatically");
          refetch();
        }}
      />
    </div>
  );
}

// ── Detail view (read-only) ─────────────────────────────────────────────────

function CommunicationDetail({ item, onRetry, onArchive, onUnarchive, onDelete }) {
  const fieldStyle = { marginBottom: 14 };
  const labelStyle = {
    fontSize: 10, fontWeight: 700, color: theme.text.faint,
    textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4,
  };
  const valueStyle = { fontSize: 13, color: theme.text.secondary, lineHeight: 1.5 };

  return (
    <div>
      {/* Status */}
      <div style={{ ...fieldStyle, display: "flex", alignItems: "center", gap: 12 }}>
        <div>
          <div style={labelStyle}>Status</div>
          {(() => {
            const s = STATUS_STYLES[item.processing_status] || STATUS_STYLES.pending;
            return <Badge bg={s.bg} text={s.text} label={s.label} />;
          })()}
        </div>
        <div>
          <div style={labelStyle}>Duration</div>
          <div style={{ ...valueStyle, fontFamily: theme.font.mono }}>
            {formatDuration(item.duration_seconds)}
          </div>
        </div>
      </div>

      {/* Metadata grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
        <div style={fieldStyle}>
          <div style={labelStyle}>Source</div>
          <div style={valueStyle}>{item.source_type || "\u2014"}</div>
        </div>
        <div style={fieldStyle}>
          <div style={labelStyle}>Created</div>
          <div style={valueStyle}>{formatDateTime(item.created_at)}</div>
        </div>
        <div style={fieldStyle}>
          <div style={labelStyle}>Updated</div>
          <div style={valueStyle}>{formatDateTime(item.updated_at)}</div>
        </div>
        <div style={fieldStyle}>
          <div style={labelStyle}>ID</div>
          <div style={{
            ...valueStyle, fontFamily: theme.font.mono, fontSize: 11,
            color: theme.text.dim, wordBreak: "break-all",
          }}>
            {item.id}
          </div>
        </div>
      </div>

      {/* Bundle/Item summary */}
      {(item.bundle_count != null || item.item_count != null) && (
        <div style={{ ...fieldStyle, display: "flex", gap: 20 }}>
          <div>
            <div style={labelStyle}>Bundles</div>
            <div style={{ ...valueStyle, fontSize: 18, fontWeight: 700, color: theme.text.primary }}>
              {item.bundle_count ?? 0}
            </div>
          </div>
          <div>
            <div style={labelStyle}>Items</div>
            <div style={{ ...valueStyle, fontSize: 18, fontWeight: 700, color: theme.text.primary }}>
              {item.item_count ?? 0}
            </div>
          </div>
        </div>
      )}

      {/* Sensitivity flags */}
      {item.sensitivity_flags && item.sensitivity_flags.length > 0 && (
        <div style={fieldStyle}>
          <div style={labelStyle}>Sensitivity Flags</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {item.sensitivity_flags.map((f) => (
              <Badge key={f} bg="#450a0a" text="#f87171" label={f.replace(/_/g, " ")} />
            ))}
          </div>
        </div>
      )}

      {/* Error info */}
      {item.processing_status === "error" && (
        <div style={{
          ...fieldStyle,
          background: "rgba(239,68,68,0.08)",
          borderRadius: 8, padding: 12,
          border: "1px solid rgba(239,68,68,0.2)",
        }}>
          <div style={labelStyle}>Error</div>
          <div style={{ ...valueStyle, color: theme.accent.red }}>
            {item.error_message || "Unknown error"}
          </div>
          {item.error_stage && (
            <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 4 }}>
              Stage: {item.error_stage}
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      {item.summary && (
        <div style={fieldStyle}>
          <div style={labelStyle}>Summary</div>
          <div style={valueStyle}>{item.summary}</div>
        </div>
      )}

      {/* Actions */}
      <div style={{
        display: "flex", gap: 8, marginTop: 20, paddingTop: 16,
        borderTop: `1px solid ${theme.border.default}`,
      }}>
        {/* Retry — only for error state */}
        {item.processing_status === "error" && onRetry && (
          <button onClick={onRetry} style={{
            padding: "8px 16px", borderRadius: 7, fontSize: 12, fontWeight: 600,
            background: "#1e40af", color: "#fff", border: "none", cursor: "pointer",
          }}>
            Retry from {item.error_stage || "start"}
          </button>
        )}

        <div style={{ flex: 1 }} />

        {/* Archive / Unarchive */}
        {item.archived_at ? (
          onUnarchive && (
            <button onClick={onUnarchive} style={{
              padding: "8px 16px", borderRadius: 7, fontSize: 12, fontWeight: 600,
              background: theme.bg.input, color: theme.text.muted,
              border: `1px solid ${theme.border.default}`, cursor: "pointer",
            }}>
              Restore
            </button>
          )
        ) : (
          onArchive && (
            <button onClick={onArchive} style={{
              padding: "8px 16px", borderRadius: 7, fontSize: 12, fontWeight: 600,
              background: theme.bg.input, color: theme.text.muted,
              border: `1px solid ${theme.border.default}`, cursor: "pointer",
            }}>
              Archive
            </button>
          )
        )}

        {/* Delete */}
        {onDelete && (
          <button onClick={onDelete} style={{
            padding: "8px 16px", borderRadius: 7, fontSize: 12, fontWeight: 600,
            background: "rgba(239,68,68,0.1)", color: "#f87171",
            border: "1px solid rgba(239,68,68,0.25)", cursor: "pointer",
          }}>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
