import React from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../../styles/theme";
import { listMeetings, listDocuments, listDecisions, listContextNotes } from "../../../api/tracker";
import { useDrawer } from "../../../contexts/DrawerContext";
import Badge from "../../../components/shared/Badge";
import DataTable from "../../../components/shared/DataTable";
import EmptyState from "../../../components/shared/EmptyState";
import { formatDate } from "../../../utils/dateUtils";
import useLazyTab from "../../../hooks/useLazyTab";

const btnPrimary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};

const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

function SubSection({ title, count, defaultOpen = true, children }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div style={{ marginBottom: 20 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          width: "100%", padding: "8px 0", background: "none", border: "none",
          cursor: "pointer", color: theme.text.primary, fontSize: 14,
          fontWeight: 700, borderBottom: `1px solid ${theme.border.default}`,
          marginBottom: 12,
        }}
      >
        <span>{title} {count != null && <span style={{ color: theme.text.dim, fontWeight: 500 }}>({count})</span>}</span>
        <span style={{ fontSize: 11, color: theme.text.dim }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && children}
    </div>
  );
}

export default function IntelligenceTab({ matterId, activeTab }) {
  const { openDrawer } = useDrawer();
  const navigate = useNavigate();

  const { data: meetingsData, refetch: refetchMeetings } = useLazyTab(
    "Intelligence", activeTab, () => listMeetings({ matter_id: matterId }), [matterId]
  );
  const { data: docsData, refetch: refetchDocs } = useLazyTab(
    "Intelligence", activeTab, () => listDocuments({ matter_id: matterId }), [matterId]
  );
  const { data: decisionsData, refetch: refetchDecisions } = useLazyTab(
    "Intelligence", activeTab, () => listDecisions({ matter_id: matterId }), [matterId]
  );
  const { data: ctxData } = useLazyTab(
    "Intelligence", activeTab, () => listContextNotes({ matter_id: matterId }), [matterId]
  );

  const meetings = meetingsData?.items || meetingsData || [];
  const docs = docsData?.items || docsData || [];
  const decisions = decisionsData?.items || decisionsData || [];
  const ctxNotes = ctxData?.items || ctxData || [];

  return (
    <div>
      {/* Meetings */}
      <SubSection title="Meetings" count={meetings.length}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={sectionTitle}>Meetings</div>
          <button style={btnPrimary} onClick={() => openDrawer("meeting", { matter_id: matterId }, refetchMeetings)}>
            + Add Meeting
          </button>
        </div>
        {meetings.length === 0 ? (
          <EmptyState title="No meetings" message="No meetings linked to this matter yet." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              { key: "date_time_start", label: "Date", width: 140, render: (v) => formatDate(v) },
              { key: "meeting_type", label: "Type", width: 120 },
            ]}
            data={meetings}
            onRowClick={(row) => navigate(`/meetings/${row.id}`)}
          />
        )}
      </SubSection>

      {/* Documents */}
      <SubSection title="Documents" count={docs.length}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={sectionTitle}>Documents</div>
          <button style={btnPrimary} onClick={() => openDrawer("document", { matter_id: matterId }, refetchDocs)}>
            + Add Document
          </button>
        </div>
        {docs.length === 0 ? (
          <EmptyState title="No documents" message="No documents attached to this matter." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              { key: "document_type", label: "Type", width: 130 },
              { key: "status", label: "Status", width: 110 },
              { key: "version_label", label: "Version", width: 80 },
              { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
            ]}
            data={docs}
            onRowClick={(row) => openDrawer("document", row, refetchDocs)}
          />
        )}
      </SubSection>

      {/* Decisions */}
      <SubSection title="Decisions" count={decisions.length}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={sectionTitle}>Decisions</div>
          <button style={btnPrimary} onClick={() => openDrawer("decision", { matter_id: matterId }, refetchDecisions)}>
            + Add Decision
          </button>
        </div>
        {decisions.length === 0 ? (
          <EmptyState title="No decisions" message="No decisions recorded for this matter." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              {
                key: "status", label: "Status", width: 120,
                render: (val) => {
                  const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                  return <Badge bg={s.bg} text={s.text} label={s.label || val || "—"} />;
                },
              },
              { key: "made_at", label: "Decided", width: 130, render: (v) => formatDate(v) },
              { key: "decision_due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
            ]}
            data={decisions}
            onRowClick={(row) => openDrawer("decision", row, refetchDecisions)}
          />
        )}
      </SubSection>

      {/* Context Notes */}
      <SubSection title="Context Notes" count={ctxNotes.length}>
        {ctxNotes.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>
            No context notes linked to this matter.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {ctxNotes.map((note) => {
              const CAT_C = { people_insight: { bg: "#312e81", text: "#c4b5fd" }, institutional_knowledge: { bg: "#1e3a5f", text: "#60a5fa" }, process_note: { bg: "#0c4a6e", text: "#67e8f9" }, policy_operating_rule: { bg: "#14532d", text: "#4ade80" }, strategic_context: { bg: "#422006", text: "#fbbf24" }, culture_climate: { bg: "#431407", text: "#fb923c" }, relationship_dynamic: { bg: "#1e1b4b", text: "#a78bfa" } };
              const POS_C = { factual: { bg: "#1e3a5f", text: "#60a5fa" }, attributed_view: { bg: "#78350f", text: "#fbbf24" }, tentative: { bg: "#1f2937", text: "#9ca3af" }, interpretive: { bg: "#1e1b4b", text: "#a78bfa" }, sensitive: { bg: "#7f1d1d", text: "#fca5a5" } };
              const cc = CAT_C[note.category] || { bg: "#1f2937", text: "#9ca3af" };
              const pc = POS_C[note.posture] || { bg: "#1f2937", text: "#9ca3af" };
              return (
                <div key={note.id} style={{ background: theme.bg.input, borderRadius: 8, border: `1px solid ${theme.border.subtle}`, padding: "12px 16px" }}>
                  <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <span style={{ background: cc.bg, color: cc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                      {(note.category || "").replace(/_/g, " ")}
                    </span>
                    <span style={{ background: pc.bg, color: pc.text, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                      {(note.posture || "").replace(/_/g, " ")}
                    </span>
                    {note.sensitivity && note.sensitivity !== "low" && (
                      <span style={{ background: "#7f1d1d", color: "#fca5a5", fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase" }}>
                        {note.sensitivity}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    <span style={{ fontSize: 10, color: theme.text.faint }}>{note.created_at?.slice(0, 10)}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>{note.title}</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {note.body}
                  </div>
                  {note.speaker_attribution && (
                    <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 6, fontStyle: "italic" }}>
                      — {note.speaker_attribution}
                    </div>
                  )}
                  {note.links && note.links.length > 0 && (
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                      {note.links.map((lnk, i) => (
                        <span key={i} style={{ background: "rgba(59,130,246,0.1)", color: "#93c5fd", fontSize: 10, padding: "2px 6px", borderRadius: 4, border: "1px solid rgba(59,130,246,0.2)" }}>
                          {lnk.entity_name || lnk.entity_type} ({lnk.relationship_role})
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </SubSection>
    </div>
  );
}
