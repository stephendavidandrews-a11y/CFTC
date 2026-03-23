import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { getBundleReviewQueue } from "../../api/ai";
import DataTable from "../../components/shared/DataTable";
import Badge from "../../components/shared/Badge";
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

const STATUS_STYLES = {
  awaiting_bundle_review: { bg: "#1e3a5f", text: "#60a5fa", label: "Awaiting Review" },
  bundle_review_in_progress: { bg: "#422006", text: "#fbbf24", label: "In Progress" },
  reviewed: { bg: "#14532d", text: "#4ade80", label: "Reviewed" },
};

function statusBadge(status) {
  const s = STATUS_STYLES[status] || { bg: "#1f2937", text: "#9ca3af", label: status || "Unknown" };
  return <Badge bg={s.bg} text={s.text} label={s.label} />;
}

// ── Columns ─────────────────────────────────────────────────────────────────

const columns = [
  {
    key: "title",
    label: "Communication",
    width: "25%",
    render: (val, row) => (
      <span style={{ color: theme.text.primary, fontWeight: 600, fontSize: 13 }}>
        {val || row.original_filename || "Untitled"}
      </span>
    ),
  },
  {
    key: "duration_seconds",
    label: "Duration",
    width: 90,
    render: (val) => (
      <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.muted }}>
        {formatDuration(val)}
      </span>
    ),
  },
  {
    key: "bundle_count",
    label: "Bundles",
    width: 130,
    render: (_, row) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        <span style={{ color: theme.text.primary, fontWeight: 600 }}>{row.bundles_proposed || 0}</span>
        <span style={{ color: theme.text.faint }}> / </span>
        <span style={{ color: theme.accent.green }}>{row.bundles_accepted || 0}</span>
        {(row.bundles_rejected || 0) > 0 && (
          <>
            <span style={{ color: theme.text.faint }}> / </span>
            <span style={{ color: theme.accent.red }}>{row.bundles_rejected}</span>
          </>
        )}
        <span style={{ color: theme.text.faint, marginLeft: 4 }}>
          ({row.bundle_count || 0})
        </span>
      </span>
    ),
  },
  {
    key: "item_count",
    label: "Items",
    width: 100,
    render: (_, row) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        <span style={{ color: theme.text.primary, fontWeight: 600 }}>{row.items_proposed || 0}</span>
        <span style={{ color: theme.text.faint }}> / {row.item_count || 0}</span>
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
    key: "sensitivity_flags",
    label: "Sensitivity",
    width: 120,
    render: (val) => {
      if (!val || val.length === 0) return <span style={{ color: theme.text.faint }}>\u2014</span>;
      return (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {val.map((flag) => (
            <Badge key={flag} bg="#450a0a" text="#f87171" label={flag.replace(/_/g, " ")} />
          ))}
        </div>
      );
    },
  },
  {
    key: "created_at",
    label: "Created",
    width: 100,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.dim }}>{formatRelativeTime(val)}</span>
    ),
  },
];

// ── Component ───────────────────────────────────────────────────────────────

export default function BundleReviewQueuePage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(() => getBundleReviewQueue(), []);
  const { connected, on } = useAIEvents(["review_ready", "bundle_review_complete", "communication_undo"]);

  // Auto-refresh on SSE events
  useEffect(() => {
    const unsub1 = on("review_ready", () => refetch());
    const unsub2 = on("bundle_review_complete", () => refetch());
    return () => { unsub1(); unsub2(); };
  }, [on, refetch]);

  const items = data?.items || [];
  const total = data?.total ?? items.length;

  return (
    <div style={{ padding: "28px 32px" }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{
          fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0,
          fontFamily: theme.font.family,
        }}>
          Bundle Review
        </h1>
        <p style={{ fontSize: 13, color: theme.text.dim, margin: "4px 0 0" }}>
          {total} communication{total !== 1 ? "s" : ""} awaiting review
        </p>
      </div>

      <SSEBanner connected={connected} />

      {/* Content */}
      <div style={{
        background: theme.bg.card,
        borderRadius: theme.card.radius,
        border: `1px solid ${theme.border.default}`,
        padding: "4px 0",
      }}>
        {loading && (
          <div style={{ padding: 40, textAlign: "center", color: theme.text.faint, fontSize: 13 }}>
            Loading review queue...
          </div>
        )}

        {error && (
          <div style={{ padding: 40, textAlign: "center" }}>
            <div style={{ color: theme.accent.red, fontSize: 14, marginBottom: 8 }}>
              Failed to load review queue
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
            icon="▤"
            title="No communications awaiting review"
            message="When the AI pipeline extracts bundles from a communication, they will appear here for your review."
          />
        )}

        {!loading && !error && items.length > 0 && (
          <DataTable
            columns={columns}
            data={items}
            onRowClick={(row) => navigate(`/review/bundles/${row.id}`)}
            pageSize={25}
            emptyMessage="No items in queue"
          />
        )}
      </div>
    </div>
  );
}
