import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { getSpeakerReviewQueue } from "../../api/ai";
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
  const d = new Date(dateStr + "Z");
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
  awaiting_speaker_review: { bg: "#1e3a5f", text: "#60a5fa", label: "Awaiting Review" },
  speaker_review_in_progress: { bg: "#422006", text: "#fbbf24", label: "In Progress" },
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
    width: "30%",
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
    key: "speaker_count",
    label: "Speakers",
    width: 120,
    render: (_, row) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        <span style={{ color: "#4ade80", fontWeight: 600 }}>{row.confirmed_count || 0}</span>
        <span style={{ color: theme.text.faint }}> / </span>
        <span style={{ fontWeight: 600 }}>{row.speaker_count || 0}</span>
        <span style={{ color: theme.text.faint }}> confirmed</span>
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
    key: "created_at",
    label: "Uploaded",
    width: 110,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.faint }}>{formatRelativeTime(val)}</span>
    ),
  },
];

// ── Page ────────────────────────────────────────────────────────────────────

export default function SpeakerReviewQueuePage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(getSpeakerReviewQueue);
  const { lastEvent, connected } = useAIEvents();

  useEffect(() => {
    if (lastEvent?.type === "communication_status" || lastEvent?.type === "speaker_review_complete") {
      refetch();
    }
  }, [lastEvent]);

  const items = data?.items || [];

  return (
    <div style={{ padding: "28px 32px" }}>
      <SSEBanner connected={connected} />

      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          Speaker Review
        </h1>
        {items.length > 0 && (
          <span style={{
            background: "#1e3a5f", color: "#60a5fa",
            padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600,
          }}>
            {items.length}
          </span>
        )}
      </div>

      {error && (
        <div style={{
          padding: "12px 16px", borderRadius: 8,
          background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
          color: "#f87171", marginBottom: 16, fontSize: 13,
        }}>
          Failed to load speaker review queue: {error.message || String(error)}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <EmptyState
          icon="🎙️"
          title="No communications awaiting speaker review"
          message="Upload audio to get started. Communications will appear here after transcription."
        />
      )}

      {items.length > 0 && (
        <DataTable
          columns={columns}
          data={items}
          loading={loading}
          onRowClick={(row) => navigate(`/review/speakers/${row.id}`)}
          rowStyle={{ cursor: "pointer" }}
        />
      )}
    </div>
  );
}
