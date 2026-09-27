import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, btnPrimary } from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import useAIEvents from "../../hooks/useAIEvents";
import { listEnrichmentJobs, getEnrichmentStatus } from "../../api/ai";
import { formatDateTime } from "../../utils/dateUtils";
import DataTable from "../../components/shared/DataTable";
import Badge from "../../components/shared/Badge";
import EmptyState from "../../components/shared/EmptyState";
import UploadContactsModal from "../../components/enrichment/UploadContactsModal";

// Module-level so useAIEvents does not reconnect on every render.
const ENRICHMENT_EVENTS = [
  "enrichment_progress",
  "enrichment_complete",
  "enrichment_paused",
  "enrichment_error",
];

const STATUS_STYLES = {
  uploaded: { bg: "#1f2937", text: "#9ca3af", label: "Uploaded" },
  mapping: { bg: "#1f2937", text: "#9ca3af", label: "Needs mapping" },
  ready: { bg: "#172554", text: "#60a5fa", label: "Ready" },
  running: { bg: "#1e3a5f", text: "#60a5fa", label: "Running" },
  paused: { bg: "#422006", text: "#fbbf24", label: "Paused" },
  awaiting_review: { bg: "#422006", text: "#fbbf24", label: "Needs review" },
  committing: { bg: "#1e3a5f", text: "#60a5fa", label: "Committing" },
  complete: { bg: "#14532d", text: "#4ade80", label: "Complete" },
  failed: { bg: "#3f1d1d", text: "#f87171", label: "Failed" },
  cancelled: { bg: "#1f2937", text: "#6b7280", label: "Cancelled" },
};

function statusBadge(status) {
  const s = STATUS_STYLES[status] || {
    bg: "#1f2937",
    text: "#9ca3af",
    label: status || "Unknown",
  };
  return <Badge bg={s.bg} text={s.text} label={s.label} />;
}

const columns = [
  {
    key: "original_filename",
    label: "File",
    width: "28%",
    render: (val, row) => (
      <div>
        <div style={{ color: theme.text.primary, fontWeight: 600, fontSize: 13 }}>
          {val || "Untitled"}
        </div>
        {row.source_type === "linkedin_export" && (
          <div style={{ fontSize: 10, color: theme.accent.blueLight, marginTop: 2 }}>
            LinkedIn export
          </div>
        )}
      </div>
    ),
  },
  {
    key: "status",
    label: "Status",
    width: 130,
    render: (val) => statusBadge(val),
  },
  {
    key: "row_count",
    label: "Rows",
    width: 80,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>{val ?? "—"}</span>
    ),
  },
  {
    key: "rows_found",
    label: "Found",
    width: 110,
    render: (_, row) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        <span style={{ color: theme.accent.greenLight, fontWeight: 600 }}>
          {row.rows_found || 0}
        </span>
        <span style={{ color: theme.text.faint }}> / {row.rows_processed || 0}</span>
      </span>
    ),
  },
  {
    key: "credits_spent",
    label: "Credits",
    width: 100,
    render: (val, row) => (
      <span style={{ fontSize: 12, color: theme.text.muted }}>
        <span style={{ fontWeight: 600, color: theme.accent.yellowLight }}>{val || 0}</span>
        {row.credit_cap ? (
          <span style={{ color: theme.text.faint }}> / {row.credit_cap}</span>
        ) : null}
      </span>
    ),
  },
  {
    key: "created_at",
    label: "Uploaded",
    width: 150,
    render: (val) => (
      <span style={{ fontSize: 12, color: theme.text.faint }}>{formatDateTime(val)}</span>
    ),
  },
];

export default function ContactEnrichmentPage() {
  const navigate = useNavigate();
  const [uploadOpen, setUploadOpen] = useState(false);
  const { data, loading, error, refetch } = useApi(() => listEnrichmentJobs());
  const { data: config } = useApi(getEnrichmentStatus);
  const { lastEvent } = useAIEvents(ENRICHMENT_EVENTS);

  useEffect(() => {
    if (lastEvent) {
      refetch().catch(() => {});
    }
  }, [lastEvent, refetch]);

  const jobs = data?.items || [];
  const unavailable = config && (!config.enabled || !config.api_key_configured);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h1 style={titleStyle}>Contact Enrichment</h1>
          <p style={subtitleStyle}>
            Upload a contact spreadsheet and let Hunter.io fill in the work email
            addresses, then review before anything is saved.
          </p>
        </div>
        <button
          onClick={() => setUploadOpen(true)}
          disabled={unavailable}
          style={{ ...btnPrimary, opacity: unavailable ? 0.5 : 1 }}
        >
          Upload contacts
        </button>
      </div>

      {unavailable && (
        <div
          style={{
            background: "#422006",
            border: `1px solid ${theme.accent.yellow}`,
            borderRadius: 6,
            padding: "12px 14px",
            fontSize: 12,
            color: theme.accent.yellowLight,
            marginBottom: 18,
          }}
        >
          {!config.api_key_configured
            ? "Set HUNTER_API_KEY in .env to use contact enrichment."
            : "Contact enrichment is turned off in AI Configuration."}
        </div>
      )}

      {error && (
        <div
          style={{
            background: "#3f1d1d",
            border: `1px solid ${theme.accent.red}`,
            borderRadius: 6,
            padding: "12px 14px",
            fontSize: 12,
            color: theme.accent.redLight,
            marginBottom: 18,
          }}
        >
          {error.message}
        </div>
      )}

      {!loading && jobs.length === 0 ? (
        <EmptyState
          title="No enrichment jobs yet"
          message="Upload a spreadsheet of names and organizations to get started. A LinkedIn connections export works well."
        />
      ) : (
        <DataTable
          columns={columns}
          data={jobs}
          onRowClick={(row) => navigate(`/enrichment/${row.id}`)}
          emptyMessage="No enrichment jobs"
        />
      )}

      <UploadContactsModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        config={config}
        onComplete={(jobId) => {
          setUploadOpen(false);
          refetch().catch(() => {});
          navigate(`/enrichment/${jobId}`);
        }}
      />
    </div>
  );
}
