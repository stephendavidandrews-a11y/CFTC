import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getContextNote, deleteContextNote } from "../../api/tracker";
import Breadcrumb from "../../components/shared/Breadcrumb";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import { useToastContext } from "../../contexts/ToastContext";
import { formatDate, timeAgo } from "../../utils/dateUtils";

const CATEGORY_COLORS = {
  people_insight: { bg: "#312e81", text: "#c4b5fd" },
  institutional_knowledge: { bg: "#1e3a5f", text: "#60a5fa" },
  process_note: { bg: "#0c4a6e", text: "#67e8f9" },
  policy_operating_rule: { bg: "#14532d", text: "#4ade80" },
  strategic_context: { bg: "#422006", text: "#fbbf24" },
  culture_climate: { bg: "#431407", text: "#fb923c" },
  relationship_dynamic: { bg: "#1e1b4b", text: "#a78bfa" },
};

const POSTURE_COLORS = {
  factual: { bg: "#1e3a5f", text: "#60a5fa" },
  attributed_view: { bg: "#78350f", text: "#fbbf24" },
  tentative: { bg: "#1f2937", text: "#9ca3af" },
  interpretive: { bg: "#1e1b4b", text: "#a78bfa" },
  sensitive: { bg: "#7f1d1d", text: "#fca5a5" },
};

const ENTITY_ROUTES = {
  person: (id) => `/people/${id}`,
  organization: (id) => `/organizations/${id}`,
  matter: (id) => `/matters/${id}`,
  meeting: (id) => `/meetings/${id}`,
  decision: (id) => `/decisions/${id}`,
  document: (id) => `/documents/${id}`,
};

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
  marginBottom: 16,
};
const labelStyle = {
  fontSize: 11,
  color: theme.text.dim,
  marginBottom: 2,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};
const valueStyle = {
  fontSize: 14,
  color: theme.text.primary,
  marginBottom: 12,
};

function Badge({ bg, text, label }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4,
      fontSize: 10, fontWeight: 600, background: bg, color: text,
      textTransform: "uppercase", letterSpacing: "0.04em",
    }}>{label}</span>
  );
}

function formatLabel(s) {
  return (s || "").replace(/_/g, " ");
}

export default function ContextNoteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToastContext();
  const [showDelete, setShowDelete] = useState(false);
  const { data: note, loading, error } = useApi(() => getContextNote(id), [id]);

  React.useEffect(() => {
    if (note?.title) document.title = note.title + " | Command Center";
  }, [note?.title]);

  if (loading) {
    return (
      <div style={{ padding: 32, color: theme.text.muted }}>Loading...</div>
    );
  }

  if (error || !note) {
    return (
      <div style={{ padding: 32, color: theme.accent.red }}>
        {error?.message || "Context note not found."}
      </div>
    );
  }

  const catColor = CATEGORY_COLORS[note.category] || CATEGORY_COLORS.institutional_knowledge;
  const posColor = POSTURE_COLORS[note.posture] || POSTURE_COLORS.factual;
  const isStale = note.stale_after && new Date(note.stale_after) <= new Date();

  return (
    <div style={{ padding: "24px 32px", maxWidth: 900 }}>
      <Breadcrumb items={[
        { label: "Context Notes", to: "/context-notes" },
        { label: note.title || "Detail" },
      ]} />

      {/* Header card */}
      <div style={cardStyle}>
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
          <Badge bg={catColor.bg} text={catColor.text} label={formatLabel(note.category)} />
          <Badge bg={posColor.bg} text={posColor.text} label={formatLabel(note.posture)} />
          {note.sensitivity !== "low" && (
            <Badge bg="#7f1d1d" text="#fca5a5" label={note.sensitivity} />
          )}
          {isStale && (
            <Badge bg="#78350f" text="#fbbf24" label="stale" />
          )}
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: theme.text.dim }}>{timeAgo(note.created_at)}</span>
        </div>
        <h1 style={{
          fontSize: 20, fontWeight: 700, color: theme.text.primary,
          margin: 0, lineHeight: 1.4,
        }}>
          {note.title}
        </h1>
        {note.speaker_attribution && (
          <div style={{
            fontSize: 13, color: theme.text.muted, fontStyle: "italic", marginTop: 8,
          }}>
            Attributed to {note.speaker_attribution}
          </div>
        )}
      </div>

      {/* Body card */}
      <div style={cardStyle}>
        <div style={{ fontSize: 14, color: theme.text.secondary, lineHeight: 1.7 }}>
          {note.body}
        </div>
        {note.source_excerpt && (
          <div style={{
            borderLeft: `3px solid ${theme.accent.blue}`,
            paddingLeft: 16, marginTop: 16,
            fontStyle: "italic", fontSize: 13, color: theme.text.muted, lineHeight: 1.6,
          }}>
            {"\u201c"}{note.source_excerpt}{"\u201d"}
          </div>
        )}
      </div>

      {/* Metadata card */}
      <div style={cardStyle}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div>
            <div style={labelStyle}>Category</div>
            <div style={valueStyle}>{formatLabel(note.category)}</div>
          </div>
          <div>
            <div style={labelStyle}>Posture</div>
            <div style={valueStyle}>{formatLabel(note.posture)}</div>
          </div>
          <div>
            <div style={labelStyle}>Durability</div>
            <div style={valueStyle}>{formatLabel(note.durability)}</div>
          </div>
          <div>
            <div style={labelStyle}>Sensitivity</div>
            <div style={valueStyle}>{note.sensitivity}</div>
          </div>
          {note.ai_confidence != null && (
            <div>
              <div style={labelStyle}>AI Confidence</div>
              <div style={valueStyle}>{(note.ai_confidence * 100).toFixed(0)}%</div>
            </div>
          )}
          <div>
            <div style={labelStyle}>Source</div>
            <div style={valueStyle}>{note.source || "unknown"}</div>
          </div>
          {note.effective_date && (
            <div>
              <div style={labelStyle}>Effective Date</div>
              <div style={valueStyle}>{formatDate(note.effective_date)}</div>
            </div>
          )}
          {note.stale_after && (
            <div>
              <div style={labelStyle}>Stale After</div>
              <div style={valueStyle}>{formatDate(note.stale_after)}</div>
            </div>
          )}
          <div>
            <div style={labelStyle}>Created</div>
            <div style={valueStyle}>{formatDate(note.created_at)}</div>
          </div>
          {note.updated_at && note.updated_at !== note.created_at && (
            <div>
              <div style={labelStyle}>Updated</div>
              <div style={valueStyle}>{formatDate(note.updated_at)}</div>
            </div>
          )}
        </div>
      </div>

      {/* Linked Entities card */}
      {note.links && note.links.length > 0 && (
        <div style={cardStyle}>
          <div style={labelStyle}>Linked Entities</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
            {note.links.map((link, i) => {
              const isNavigable = !!ENTITY_ROUTES[link.entity_type];
              return (
                <span
                  key={i}
                  onClick={() => isNavigable && navigate(ENTITY_ROUTES[link.entity_type](link.entity_id))}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 4,
                    padding: "4px 10px", borderRadius: 6, fontSize: 11,
                    background: "rgba(59,130,246,0.1)", color: theme.accent.blueLight,
                    border: "1px solid rgba(59,130,246,0.2)",
                    cursor: isNavigable ? "pointer" : "default",
                  }}
                >
                  <span style={{ textTransform: "capitalize" }}>{link.entity_type}</span>
                  {link.entity_name && <span>{"\u00b7"} {link.entity_name}</span>}
                  <span style={{ color: theme.text.faint }}>({link.relationship_role})</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Delete button */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
        <button
          onClick={() => setShowDelete(true)}
          style={{
            padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
            background: theme.accent.red, color: "#fff", border: "none", cursor: "pointer",
          }}
        >
          Delete Note
        </button>
      </div>

      <ConfirmDialog
        isOpen={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={async () => {
          try {
            await deleteContextNote(note.id);
            toast.success("Context note deleted");
            navigate("/context-notes");
          } catch (e) {
            toast.error(e.message);
          }
        }}
        title="Delete Context Note"
        message={`Delete "${note.title}"? This cannot be undone.`}
        confirmLabel="Delete"
        danger
      />
    </div>
  );
}
