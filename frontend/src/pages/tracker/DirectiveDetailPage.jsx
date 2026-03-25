import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import {
  getPolicyDirective, updatePolicyDirective, deletePolicyDirective,
  listMatterDirectives, createDirectiveMatter, deleteDirectiveMatter,
  createDirectiveDocument, deleteDirectiveDocument,
  listMatters, listDocuments, getEnums,
} from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import ConfirmDialog from "../../components/shared/ConfirmDialog";
import { useDrawer } from "../../contexts/DrawerContext";
import { useToastContext } from "../../contexts/ToastContext";
import Breadcrumb from "../../components/shared/Breadcrumb";
import { formatDate } from "../../utils/dateUtils";

const STATUS_COLORS = {
  not_started: { bg: theme.bg.input, text: theme.text.dim },
  scoping: { bg: "#1a3a5c", text: "#60a5fa" },
  in_progress: { bg: "#3b2a1a", text: "#fbbf24" },
  partially_implemented: { bg: "#2a3b1a", text: "#86efac" },
  implemented: { bg: "#1a3b2a", text: "#34d399" },
  deferred: { bg: theme.bg.input, text: theme.text.dim },
  not_applicable: { bg: theme.bg.input, text: theme.text.dim },
};

const DOC_TYPE_COLORS = {
  no_action_letter: { bg: "#1a3a5c", text: "#60a5fa" },
  federal_register: { bg: "#3b2a1a", text: "#fbbf24" },
  legal_memo: { bg: "#2a1a3b", text: "#c084fc" },
  report: { bg: "#1a3b2a", text: "#34d399" },
  correspondence: { bg: theme.bg.input, text: theme.text.dim },
  other: { bg: theme.bg.input, text: theme.text.dim },
};

const REL_COLORS = {
  references: { bg: theme.bg.input, text: theme.text.dim },
  implements: { bg: "#1a3a5c", text: "#60a5fa" },
  supersedes: { bg: "#3b2a1a", text: "#fbbf24" },
  withdraws: { bg: "#3b1a1a", text: "#f87171" },
  amends: { bg: "#2a1a3b", text: "#c084fc" },
};

function fmt(val) { return val ? val.replace(/_/g, " ") : ""; }

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
const selectStyle = {
  width: "100%", padding: "8px 12px", fontSize: 14, background: theme.bg.input,
  border: `1px solid ${theme.border.default}`, borderRadius: 6, color: theme.text.primary, marginBottom: 12,
};

export default function DirectiveDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const toast = useToastContext();
  const [showDelete, setShowDelete] = useState(false);
  const [showLinkMatter, setShowLinkMatter] = useState(false);
  const [selectedMatterId, setSelectedMatterId] = useState("");
  const [showLinkDoc, setShowLinkDoc] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [selectedDocRelType, setSelectedDocRelType] = useState("references");

  const { data: directive, loading, error, refetch } = useApi(() => getPolicyDirective(id), [id]);
  const { data: mattersData } = useApi(() => listMatters({ limit: 500 }), []);
  const { data: docsData } = useApi(() => listDocuments({ limit: 500 }), []);
  const { data: enumsData } = useApi(() => getEnums(), []);

  React.useEffect(() => { if (directive?.title) document.title = directive?.title + " | Command Center"; }, [directive?.title]);

  const d = directive || {};
  const matters = mattersData?.items || [];
  const allDocs = docsData?.items || [];
  const linkedMatters = d.linked_matters || [];
  const linkedDocs = d.linked_documents || [];

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

  const handleUnlinkMatter = async (linkId) => {
    try {
      await deleteDirectiveMatter(linkId);
      refetch();
    } catch (err) {
      toast?.error?.("Failed to unlink: " + (err.detail || err.message));
    }
  };

  const handleLinkDoc = async () => {
    if (!selectedDocId) return;
    try {
      await createDirectiveDocument({
        directive_id: id,
        document_id: selectedDocId,
        relationship_type: selectedDocRelType,
      });
      setShowLinkDoc(false);
      setSelectedDocId("");
      setSelectedDocRelType("references");
      refetch();
    } catch (err) {
      toast?.error?.(err.detail || "Failed to link document");
    }
  };

  const handleUnlinkDoc = async (linkId) => {
    try {
      await deleteDirectiveDocument(linkId);
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
      render: (_, r) => <button onClick={(e) => { e.stopPropagation(); handleUnlinkMatter(r.id); }}
        style={{ background: "none", border: "none", color: theme.accent.red, cursor: "pointer", fontSize: 12 }}>Unlink</button> },
  ];

  const docColumns = [
    { key: "title", label: "Document", flex: 1,
      render: (_, r) => (
        <span style={{ fontWeight: 600, fontSize: 13 }} title={r.title}>
          {r.title?.length > 55 ? r.title.slice(0, 55) + "\u2026" : r.title}
        </span>
      ) },
    { key: "document_type", label: "Type", width: 140,
      render: (_, r) => <Badge {...(DOC_TYPE_COLORS[r.document_type] || DOC_TYPE_COLORS.other)} label={fmt(r.document_type)} /> },
    { key: "relationship_type", label: "Relationship", width: 120,
      render: (_, r) => <Badge {...(REL_COLORS[r.relationship_type] || REL_COLORS.references)} label={fmt(r.relationship_type)} /> },
    { key: "file", label: "File", width: 60,
      render: (_, r) => r.current_file_id
        ? <a href={`/tracker/documents/${r.document_id}/files/${r.current_file_id}/download`}
            onClick={(e) => e.stopPropagation()}
            style={{ color: theme.accent.blue, fontSize: 12, textDecoration: "none" }}
            title="Download file">PDF</a>
        : <span style={{ color: theme.text.dim, fontSize: 12 }}>&mdash;</span> },
    { key: "link_notes", label: "Notes", width: 180,
      render: (_, r) => <span style={{ fontSize: 11, color: theme.text.dim }} title={r.link_notes}>
        {r.link_notes?.length > 35 ? r.link_notes.slice(0, 35) + "\u2026" : (r.link_notes || "")}
      </span> },
    { key: "actions", label: "", width: 50,
      render: (_, r) => <button onClick={(e) => { e.stopPropagation(); handleUnlinkDoc(r.link_id); }}
        style={{ background: "none", border: "none", color: theme.accent.red, cursor: "pointer", fontSize: 12 }}>Unlink</button> },
  ];

  const relTypeOptions = enumsData?.directive_document_relationship_type || ["references", "implements", "supersedes", "withdraws", "amends"];

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

      {/* Referenced Documents */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>Referenced Documents</div>
            {linkedDocs.length > 0 && (
              <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 2 }}>
                {linkedDocs.length} document{linkedDocs.length !== 1 ? "s" : ""}
                {linkedDocs.filter(doc => doc.current_file_id).length > 0 &&
                  ` \u00b7 ${linkedDocs.filter(doc => doc.current_file_id).length} with files`}
              </div>
            )}
          </div>
          <button style={btnPrimary} onClick={() => setShowLinkDoc(true)}>+ Link Document</button>
        </div>
        {linkedDocs.length === 0
          ? <EmptyState icon="&#128196;" title="No linked documents" subtitle="Link legal instruments, no-action letters, or other referenced documents" />
          : <DataTable columns={docColumns} data={linkedDocs}
              onRowClick={(r) => navigate(`/documents/${r.document_id}`)} />
        }
      </div>

      {/* Regulation Analysis (research notes) */}
      {(d.research_notes || []).length > 0 && (
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>Regulation Analysis</div>
              <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 2 }}>
                {d.research_notes.length} implicated rules
                {d.research_notes.filter(n => n.needs_reg_reading && !n.reg_reading_done).length > 0 &&
                  ` \u00b7 ${d.research_notes.filter(n => n.needs_reg_reading && !n.reg_reading_done).length} need reading`}
              </div>
            </div>
          </div>
          <DataTable
            columns={[
              { key: "fr_citation", label: "FR Citation", width: 120,
                render: (_, r) => <span style={{ fontSize: 12, fontFamily: "monospace" }}>{r.fr_citation}</span> },
              { key: "rule_title", label: "Rule", flex: 1,
                render: (_, r) => <span style={{ fontSize: 13 }} title={r.rule_title}>
                  {r.rule_title?.length > 60 ? r.rule_title.slice(0, 60) + "\u2026" : r.rule_title}
                </span> },
              { key: "action_category", label: "Action", width: 100,
                render: (_, r) => {
                  const colors = {
                    Amend: { bg: "#3b2a1a", text: "#fbbf24" },
                    Defend: { bg: "#1a3b2a", text: "#34d399" },
                    Reinterpret: { bg: "#1a3a5c", text: "#60a5fa" },
                    "Manual review": { bg: theme.bg.input, text: theme.text.dim },
                    Deprioritize: { bg: theme.bg.input, text: theme.text.dim },
                  };
                  return r.action_category ? <Badge {...(colors[r.action_category] || {})} label={r.action_category} /> : null;
                }},
              { key: "composite_score", label: "Score", width: 60,
                render: (_, r) => <span style={{ fontSize: 12, color: theme.text.secondary }}>
                  {r.composite_score ? r.composite_score.toFixed(1) : "--"}
                </span> },
              { key: "relationship_basis", label: "Basis", width: 200,
                render: (_, r) => <span style={{ fontSize: 11, color: theme.text.dim }} title={r.relationship_basis}>
                  {r.relationship_basis?.length > 50 ? r.relationship_basis.slice(0, 50) + "\u2026" : r.relationship_basis}
                </span> },
              { key: "needs_reg_reading", label: "Reading", width: 70,
                render: (_, r) => r.reg_reading_done
                  ? <span style={{ color: "#34d399", fontSize: 12 }}>Done</span>
                  : r.needs_reg_reading
                    ? <span style={{ color: "#fbbf24", fontSize: 12 }}>Needed</span>
                    : <span style={{ color: theme.text.dim, fontSize: 12 }}>--</span> },
            ]}
            data={d.research_notes}
          />
        </div>
      )}

      {/* Linked matters */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary }}>Linked Matters</div>
          <button style={btnPrimary} onClick={() => setShowLinkMatter(true)}>+ Link Matter</button>
        </div>
        {linkedMatters.length === 0
          ? <EmptyState icon="&#128279;" title="No linked matters" subtitle="Link regulatory actions that implement this directive" />
          : <DataTable columns={matterColumns} data={linkedMatters}
              onRowClick={(r) => navigate(`/matters/${r.matter_id}`)} />
        }
      </div>

      {/* Link document modal */}
      {showLinkDoc && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: theme.bg.card, borderRadius: 10, padding: 24, minWidth: 450,
            border: `1px solid ${theme.border.default}` }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary, marginBottom: 12 }}>Link Document</div>
            <div style={{ marginBottom: 8 }}>
              <div style={{ ...labelStyle, marginBottom: 4 }}>Document</div>
              <select value={selectedDocId} onChange={(e) => setSelectedDocId(e.target.value)} style={selectStyle}>
                <option value="">Select a document...</option>
                {allDocs.filter((doc) => !linkedDocs.some((ld) => ld.document_id === doc.id))
                  .map((doc) => <option key={doc.id} value={doc.id}>{doc.title}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 8 }}>
              <div style={{ ...labelStyle, marginBottom: 4 }}>Relationship</div>
              <select value={selectedDocRelType} onChange={(e) => setSelectedDocRelType(e.target.value)} style={selectStyle}>
                {relTypeOptions.map((t) => <option key={t} value={t}>{fmt(t)}</option>)}
              </select>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => { setShowLinkDoc(false); setSelectedDocId(""); setSelectedDocRelType("references"); }}
                style={{ ...btnPrimary, background: theme.bg.input, color: theme.text.secondary }}>Cancel</button>
              <button onClick={handleLinkDoc} style={btnPrimary} disabled={!selectedDocId}>Link</button>
            </div>
          </div>
        </div>
      )}

      {/* Link matter modal */}
      {showLinkMatter && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: theme.bg.card, borderRadius: 10, padding: 24, minWidth: 400,
            border: `1px solid ${theme.border.default}` }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text.primary, marginBottom: 12 }}>Link Matter</div>
            <select value={selectedMatterId} onChange={(e) => setSelectedMatterId(e.target.value)} style={selectStyle}>
              <option value="">Select a matter...</option>
              {matters.filter((m) => !linkedMatters.some((lm) => lm.matter_id === m.id))
                .map((m) => <option key={m.id} value={m.id}>{m.matter_number ? `${m.matter_number} \u2014 ` : ""}{m.title}</option>)}
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
