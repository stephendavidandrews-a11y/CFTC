import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import {
  getPolicyDirective, updatePolicyDirective, deletePolicyDirective,
  listMatterDirectives, createDirectiveMatter, deleteDirectiveMatter,
  listMatters, getEnums,
} from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import { useDrawer } from "../../contexts/DrawerContext";
import { useToastContext } from "../../contexts/ToastContext";

const STATUS_COLORS = {
  not_started: { bg: theme.bg.input, text: theme.text.dim },
  scoping: { bg: "#1a3a5c", text: "#60a5fa" },
  in_progress: { bg: "#3b2a1a", text: "#fbbf24" },
  partially_implemented: { bg: "#2a3b1a", text: "#86efac" },
  implemented: { bg: "#1a3b2a", text: "#34d399" },
  deferred: { bg: theme.bg.input, text: theme.text.dim },
  not_applicable: { bg: theme.bg.input, text: theme.text.dim },
};

function fmt(val) { return val ? val.replace(/_/g, " ") : ""; }
function formatDate(d) { return d ? new Date(d).toLocaleDateString() : "--"; }

const cardStyle = {
  background: theme.bg.card, borderRadius: 10,
  border: `1px solid ${theme.border.default}`, padding: 24, marginBottom: 16,
};
const labelStyle = { fontSize: 11, color: theme.text.dim, marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.05em" };
const valueStyle = { fontSize: 14, color: theme.text.primary, marginBottom: 12 };
const btnPrimary = {
  padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};
const btnDanger = { ...btnPrimary, background: theme.accent.red };

export default function DirectiveDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const toast = useToastContext();
  const [showDelete, setShowDelete] = useState(false);
  const [showLinkMatter, setShowLinkMatter] = useState(false);
  const [selectedMatterId, setSelectedMatterId] = useState("");

  const { data: directive, loading, error, refetch } = useApi(() => getPolicyDirective(id), [id]);
  const { data: mattersData } = useApi(() => listMatters({ limit: 500 }), []);
  const { data: enumsData } = useApi(() => getEnums(), []);

  const d = directive || {};
  const matters = mattersData?.items || [];
  const linkedMatters = d.linked_matters || [];

  const handleDelete = async () => {
    try {
      await deletePolicyDirective(id, d._etag);
      toast?.success?.("Directive deleted");
      navigate("/directives");
    } catch (err) {
      toast?.error?.("Delete failed: " + (err.detail || err.message));
    }
  };

  const handleLinkMatter = async () => {
    if (!selectedMatterId) return;
    try {
      await createDirectiveMatter({ directive_id: id, matter_id: selectedMatterId });
      setShowLinkMatter(false);
      setSelectedMatterId("");
      refetch();
    } catch (err) {
      toast?.error?.(err.detail || "Failed to link matter");
    }
  };

  const handleUnlink = async (linkId) => {
    try {
      await deleteDirectiveMatter(linkId);
      refetch();
    } catch (err) {
      toast?.error?.("Failed to unlink: " + (err.detail || err.message));
    }
  };

  if (loading) return <div style={{ padding: 40, color: theme.text.dim }}>Loading...</div>;
  if (error) return <div style={{ padding: 40, color: theme.accent.red }}>Error: {error.message}</div>;
  if (!directive) return <div style={{ padding: 40, color: theme.text.dim }}>Directive not found</div>;

  const matterColumns = [
    { key: "matter_title", label: "Matter", flex: 1, render: (_, r) => <span style={{ fontWeight: 600 }}>{r.matter_title}</span> },
    { key: "matter_number", label: "Number", width: 120 },
    { key: "matter_status", label: "Status", width: 120 },
    { key: "relationship_type", label: "Relationship", width: 120,
      render: (_, r) => <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(r.relationship_type)} /> },
    { key: "actions", label: "", width: 60,
      render: (_, r) => <button onClick={(e) => { e.stopPropagation(); handleUnlink(r.id); }}
        style={{ background: "none", border: "none", color: theme.accent.red, cursor: "pointer", fontSize: 12 }}>Unlink</button> },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <button onClick={() => navigate("/directives")}
          style={{ background: "none", border: "none", color: theme.text.dim, cursor: "pointer", fontSize: 13, marginBottom: 8, padding: 0 }}>
          &larr; Back to Directives
        </button>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary }}>{d.directive_label}</div>
            <div style={{ fontSize: 13, color: theme.text.dim, marginTop: 4 }}>{d.source_document}</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button style={btnPrimary} onClick={() => openDrawer("directive", d, refetch)}>Edit</button>
            <button style={btnDanger} onClick={() => setShowDelete(true)}>Delete</button>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <Badge {...(STATUS_COLORS[d.implementation_status] || {})} label={fmt(d.implementation_status)} />
          {d.priority_tier && <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(d.priority_tier)} />}
          {d.responsible_entity && <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(d.responsible_entity)} />}
        </div>
      </div>

      {/* Detail card */}
      <div style={cardStyle}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div><div style={labelStyle}>Source Document Type</div><div style={valueStyle}>{fmt(d.source_document_type)}</div></div>
          <div><div style={labelStyle}>Source Date</div><div style={valueStyle}>{formatDate(d.source_date)}</div></div>
          <div><div style={labelStyle}>Section Reference</div><div style={valueStyle}>{d.section_reference || "--"}</div></div>
          <div><div style={labelStyle}>Chapter</div><div style={valueStyle}>{d.chapter || "--"}</div></div>
          <div><div style={labelStyle}>OGC Role</div><div style={valueStyle}>{fmt(d.ogc_role) || "--"}</div></div>
          <div><div style={labelStyle}>Assigned To</div><div style={valueStyle}>{d.assigned_to_name || "--"}</div></div>
          <div><div style={labelStyle}>Target Date</div><div style={valueStyle}>{formatDate(d.target_date)}</div></div>
          <div><div style={labelStyle}>Completed Date</div><div style={valueStyle}>{formatDate(d.completed_date)}</div></div>
        </div>
        {d.source_document_url && (
          <div style={{ marginTop: 8 }}><div style={labelStyle}>Source URL</div>
            <a href={d.source_document_url} target="_blank" rel="noopener noreferrer"
              style={{ color: theme.accent.blue, fontSize: 13 }}>{d.source_document_url}</a></div>
        )}
      </div>

      {/* Directive text */}
      {d.directive_text && (
        <div style={cardStyle}>
          <div style={labelStyle}>Directive Text</div>
          <div style={{ fontSize: 14, color: theme.text.primary, whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{d.directive_text}</div>
        </div>
      )}

      {/* Implementation notes */}
      {d.implementation_notes && (
        <div style={cardStyle}>
          <div style={labelStyle}>Implementation Notes</div>
          <div style={{ fontSize: 14, color: theme.text.secondary, whiteSpace: "pre-wrap" }}>{d.implementation_notes}</div>
        </div>
      )}

      {/* Linked matters */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>Linked Matters</div>
          <button style={btnPrimary} onClick={() => setShowLinkMatter(true)}>+ Link Matter</button>
        </div>
        {linkedMatters.length === 0
          ? <EmptyState icon="\ud83d\udd17" title="No linked matters" subtitle="Link regulatory actions that implement this directive" />
          : <DataTable columns={matterColumns} data={linkedMatters}
              onRowClick={(r) => navigate(`/matters/${r.matter_id}`)} />
        }
      </div>

      {/* Link matter modal */}
      {showLinkMatter && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: theme.bg.card, borderRadius: 10, padding: 24, minWidth: 400,
            border: `1px solid ${theme.border.default}` }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary, marginBottom: 12 }}>Link Matter</div>
            <select value={selectedMatterId} onChange={(e) => setSelectedMatterId(e.target.value)}
              style={{ width: "100%", padding: "8px 12px", fontSize: 14, background: theme.bg.input,
                border: `1px solid ${theme.border.default}`, borderRadius: 6, color: theme.text.primary, marginBottom: 12 }}>
              <option value="">Select a matter...</option>
              {matters.filter((m) => !linkedMatters.some((lm) => lm.matter_id === m.id))
                .map((m) => <option key={m.id} value={m.id}>{m.matter_number ? `${m.matter_number} — ` : ""}{m.title}</option>)}
            </select>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setShowLinkMatter(false)}
                style={{ ...btnPrimary, background: theme.bg.input, color: theme.text.secondary }}>Cancel</button>
              <button onClick={handleLinkMatter} style={btnPrimary} disabled={!selectedMatterId}>Link</button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog isOpen={showDelete} onClose={() => setShowDelete(false)} onConfirm={handleDelete}
        title="Delete Directive?" message="This will permanently delete the directive and all matter links." />
    </div>
  );
}
