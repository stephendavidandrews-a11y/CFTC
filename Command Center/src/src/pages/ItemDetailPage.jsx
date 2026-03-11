import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Badge from "../components/shared/Badge";
import PriorityBadge from "../components/shared/PriorityBadge";
import StatusSelect from "../components/shared/StatusSelect";
import Modal from "../components/shared/Modal";
import ConfirmDialog from "../components/shared/ConfirmDialog";
import EmptyState from "../components/shared/EmptyState";
import theme from "../styles/theme";
import { useToastContext } from "../contexts/ToastContext";
import { useApi } from "../hooks/useApi";
import {
  getItem, updateItem, advanceStage, addDecisionLog,
  listDeadlines, createDeadline, updateDeadline, extendDeadline, backwardCalculate,
  listDocuments, uploadDocument,
  listTeam, listMeetings, createMeeting, listStakeholders,
} from "../api/pipeline";

const inputStyle = {
  width: "100%", padding: "9px 12px", borderRadius: 8, fontSize: 13,
  background: theme.bg.input, color: theme.text.primary,
  border: `1px solid ${theme.border.default}`, outline: "none",
  fontFamily: theme.font.family,
};
const labelStyle = { display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 };
const DEADLINE_TYPES = ["statutory", "eo", "pwg", "internal", "cra", "pra", "ofr", "comment_period", "oira_review", "chairman_imposed"];
const DECISION_TYPES = ["stage_change", "priority_change", "assignment_change", "deadline_change", "status_change", "decision", "note", "chairman_direction", "commission_vote"];
const DOC_TYPES = ["rule_text", "preamble", "cba", "rfa", "public_comment", "memo", "briefing", "correspondence", "supporting", "other"];

export default function ItemDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToastContext();
  const [activeTab, setActiveTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Modals
  const [showAdvanceConfirm, setShowAdvanceConfirm] = useState(false);
  const [showAddDeadline, setShowAddDeadline] = useState(false);
  const [showExtend, setShowExtend] = useState(null);
  const [showBackwardCalc, setShowBackwardCalc] = useState(false);
  const [showAddLog, setShowAddLog] = useState(false);
  const [showUploadDoc, setShowUploadDoc] = useState(false);
  const [showAddMeeting, setShowAddMeeting] = useState(false);

  // Data
  const { data: item, loading, refetch } = useApi(() => getItem(id), [id]);
  const { data: deadlineData, refetch: refetchDl } = useApi(() => listDeadlines({ item_id: id }), [id]);
  const { data: docs, refetch: refetchDocs } = useApi(() => listDocuments(id), [id]);
  const { data: team } = useApi(listTeam, []);
  const { data: meetings, refetch: refetchMeetings } = useApi(() => listMeetings({ item_id: id }), [id]);

  // Forms
  const [dlForm, setDlForm] = useState({ deadline_type: "internal", title: "", due_date: "", source: "", is_hard_deadline: false, owner_id: "" });
  const [extForm, setExtForm] = useState({ new_due_date: "", reason: "" });
  const [bcForm, setBcForm] = useState({ final_deadline_date: "" });
  const [logForm, setLogForm] = useState({ action_type: "note", description: "", rationale: "" });
  const [docFile, setDocFile] = useState(null);
  const [docForm, setDocForm] = useState({ document_type: "other", title: "", change_summary: "" });
  const [mtForm, setMtForm] = useState({ meeting_type: "interagency", title: "", date: "", attendees: "", summary: "", is_ex_parte: false });

  useEffect(() => {
    if (item) setEditForm({
      title: item.title || "", short_title: item.short_title || "",
      description: item.description || "", docket_number: item.docket_number || "",
      rin: item.rin || "", fr_citation: item.fr_citation || "",
      status: item.status || "active", priority_override: item.priority_override ?? "",
      chairman_priority: item.chairman_priority || false,
      lead_attorney_id: item.lead_attorney_id || "", backup_attorney_id: item.backup_attorney_id || "",
    });
  }, [item]);

  if (loading) return <div style={{ padding: 40, color: theme.text.dim }}>Loading...</div>;
  if (!item) return <div style={{ padding: 40, color: theme.text.dim }}>Item not found</div>;

  const deadlines = deadlineData?.deadlines || item.deadlines || [];
  const stages = item.stages || [];
  const priorityStyle = theme.priority[item.priority_label] || theme.priority.medium;
  const statusStyle = theme.status[item.status] || theme.status.active;
  const teamMembers = team || [];

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "deadlines", label: `Deadlines (${deadlines.length})` },
    { key: "documents", label: `Documents (${docs?.length || 0})` },
    { key: "log", label: `Decision Log (${(item.recent_decisions || []).length})` },
    { key: "stages", label: "Stages" },
    { key: "meetings", label: `Meetings (${meetings?.length || 0})` },
  ];

  // Handlers
  const handleSave = async () => {
    setSaving(true);
    try {
      const updates = {};
      Object.keys(editForm).forEach((k) => {
        const orig = item[k];
        const cur = editForm[k];
        if (cur !== (orig ?? "") && cur !== orig) {
          if (k === "priority_override" && cur === "") updates[k] = null;
          else if (k === "lead_attorney_id" || k === "backup_attorney_id") updates[k] = cur ? Number(cur) : null;
          else updates[k] = cur;
        }
      });
      if (Object.keys(updates).length === 0) { toast.info("No changes to save"); setEditing(false); setSaving(false); return; }
      await updateItem(id, updates);
      toast.success("Item updated");
      setEditing(false);
      refetch();
    } catch (e) { toast.error(e.message); }
    setSaving(false);
  };

  const handleAdvance = async () => {
    try {
      await advanceStage(id, { rationale: "Advanced from Command Center" });
      toast.success("Stage advanced");
      refetch();
    } catch (e) { toast.error(e.message); }
  };

  const handleCreateDeadline = async () => {
    try {
      await createDeadline({ ...dlForm, item_id: Number(id), owner_id: dlForm.owner_id ? Number(dlForm.owner_id) : null });
      toast.success("Deadline created");
      setShowAddDeadline(false);
      setDlForm({ deadline_type: "internal", title: "", due_date: "", source: "", is_hard_deadline: false, owner_id: "" });
      refetchDl();
    } catch (e) { toast.error(e.message); }
  };

  const handleExtend = async () => {
    try {
      await extendDeadline(showExtend, extForm);
      toast.success("Deadline extended");
      setShowExtend(null);
      setExtForm({ new_due_date: "", reason: "" });
      refetchDl();
    } catch (e) { toast.error(e.message); }
  };

  const handleBackwardCalc = async () => {
    try {
      await backwardCalculate({ item_id: Number(id), final_deadline_date: bcForm.final_deadline_date, item_type: item.item_type });
      toast.success("Deadlines generated from backward calculation");
      setShowBackwardCalc(false);
      setBcForm({ final_deadline_date: "" });
      refetchDl();
    } catch (e) { toast.error(e.message); }
  };

  const handleAddLog = async () => {
    try {
      await addDecisionLog(id, logForm);
      toast.success("Decision log entry added");
      setShowAddLog(false);
      setLogForm({ action_type: "note", description: "", rationale: "" });
      refetch();
    } catch (e) { toast.error(e.message); }
  };

  const handleUploadDoc = async () => {
    if (!docFile) return;
    try {
      const fd = new FormData();
      fd.append("file", docFile);
      fd.append("item_id", id);
      fd.append("document_type", docForm.document_type);
      fd.append("title", docForm.title || docFile.name);
      fd.append("change_summary", docForm.change_summary);
      fd.append("uploaded_by", "Command Center");
      await uploadDocument(fd);
      toast.success("Document uploaded");
      setShowUploadDoc(false);
      setDocFile(null);
      setDocForm({ document_type: "other", title: "", change_summary: "" });
      refetchDocs();
    } catch (e) { toast.error(e.message); }
  };

  const handleCreateMeeting = async () => {
    try {
      await createMeeting({
        ...mtForm, item_id: Number(id),
        attendees: mtForm.attendees ? mtForm.attendees.split(",").map(s => s.trim()).filter(Boolean) : [],
      });
      toast.success("Meeting logged");
      setShowAddMeeting(false);
      setMtForm({ meeting_type: "interagency", title: "", date: "", attendees: "", summary: "", is_ex_parte: false });
      refetchMeetings();
    } catch (e) { toast.error(e.message); }
  };

  const severityColor = (sev) => ({ overdue: "#ef4444", critical: "#ef4444", warning: "#f59e0b", ok: "#22c55e" }[sev] || theme.text.dim);

  return (
    <div>
      {/* Back button */}
      <button onClick={() => navigate(-1)} style={{ background: "transparent", border: "none", color: theme.text.dim, fontSize: 13, cursor: "pointer", marginBottom: 16, padding: 0 }}>← Back</button>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>{item.title}</h2>
          <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <Badge bg={statusStyle.bg} text={statusStyle.text} label={statusStyle.label} />
            <PriorityBadge label={item.priority_label || "low"} score={item.priority_composite} />
            <span style={{ fontSize: 11, color: theme.text.dim }}>{item.module} · {item.item_type}</span>
            {item.docket_number && <span style={{ fontSize: 11, color: theme.text.faint, fontFamily: theme.font.mono }}>{item.docket_number}</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {!editing && <button onClick={() => setEditing(true)} style={actionBtn("#334155")}>✎ Edit</button>}
          {editing && <button onClick={handleSave} disabled={saving} style={actionBtn("#1e40af")}>{saving ? "Saving..." : "Save"}</button>}
          {editing && <button onClick={() => { setEditing(false); setEditForm({ title: item.title || "", short_title: item.short_title || "", description: item.description || "", docket_number: item.docket_number || "", rin: item.rin || "", fr_citation: item.fr_citation || "", status: item.status || "active", priority_override: item.priority_override ?? "", chairman_priority: item.chairman_priority || false, lead_attorney_id: item.lead_attorney_id || "", backup_attorney_id: item.backup_attorney_id || "" }); }} style={actionBtn("#334155")}>Cancel</button>}
          <button onClick={() => setShowAdvanceConfirm(true)} style={actionBtn(theme.accent.blue)}>Advance Stage →</button>
        </div>
      </div>

      {/* Stage bar */}
      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "16px 20px", marginBottom: 20, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <InfoBlock label="Current Stage" value={item.stage_label} color={item.stage_color || theme.accent.blue} />
        <Divider />
        <InfoBlock label="Days in Stage" value={item.days_in_stage} />
        <Divider />
        <InfoBlock label="Lead Attorney" value={item.lead_attorney_name || "Unassigned"} small />
        {item.chairman_priority && <><Divider /><Badge bg="#422006" text="#fbbf24" label="CHAIRMAN PRIORITY" /></>}
        {item.next_deadline && <><Divider /><InfoBlock label="Next Deadline" value={item.next_deadline.title} small /><span style={{ fontSize: 11, color: severityColor(item.next_deadline.severity), fontWeight: 600 }}>{item.next_deadline.due_date}</span></>}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, marginBottom: 20, borderBottom: `1px solid ${theme.border.default}`, flexWrap: "wrap" }}>
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
            padding: "10px 16px", background: "transparent", border: "none",
            borderBottom: activeTab === tab.key ? `2px solid ${theme.accent.blue}` : "2px solid transparent",
            color: activeTab === tab.key ? theme.accent.blueLight : theme.text.dim,
            fontSize: 13, fontWeight: activeTab === tab.key ? 600 : 500, cursor: "pointer",
          }}>{tab.label}</button>
        ))}
      </div>

      {/* ════ OVERVIEW TAB ══════════════════════════════════════════════ */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div style={cardStyle}>
            <h4 style={sectionTitle}>Details</h4>
            {editing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div><label style={labelStyle}>Title</label><input style={inputStyle} value={editForm.title} onChange={e => setEditForm({...editForm, title: e.target.value})} /></div>
                <div><label style={labelStyle}>Short Title</label><input style={inputStyle} value={editForm.short_title} onChange={e => setEditForm({...editForm, short_title: e.target.value})} /></div>
                <div><label style={labelStyle}>Description</label><textarea style={{...inputStyle, minHeight: 80, resize: "vertical"}} value={editForm.description} onChange={e => setEditForm({...editForm, description: e.target.value})} /></div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div><label style={labelStyle}>Docket Number</label><input style={inputStyle} value={editForm.docket_number} onChange={e => setEditForm({...editForm, docket_number: e.target.value})} /></div>
                  <div><label style={labelStyle}>RIN</label><input style={inputStyle} value={editForm.rin} onChange={e => setEditForm({...editForm, rin: e.target.value})} /></div>
                </div>
                <div><label style={labelStyle}>FR Citation</label><input style={inputStyle} value={editForm.fr_citation} onChange={e => setEditForm({...editForm, fr_citation: e.target.value})} /></div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div><label style={labelStyle}>Status</label><StatusSelect value={editForm.status} onChange={v => setEditForm({...editForm, status: v})} /></div>
                  <div><label style={labelStyle}>Priority Override (0-100)</label><input style={inputStyle} type="number" min="0" max="100" value={editForm.priority_override} onChange={e => setEditForm({...editForm, priority_override: e.target.value})} placeholder="Leave empty for auto" /></div>
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: theme.text.muted, cursor: "pointer" }}>
                  <input type="checkbox" checked={editForm.chairman_priority} onChange={e => setEditForm({...editForm, chairman_priority: e.target.checked})} />
                  Chairman Priority
                </label>
              </div>
            ) : (
              <>
                {item.description && <p style={{ fontSize: 13, color: theme.text.secondary, lineHeight: 1.6, marginBottom: 16 }}>{item.description}</p>}
                {[
                  ["Docket", item.docket_number], ["RIN", item.rin], ["FR Citation", item.fr_citation, item.fr_url],
                  ["Priority Score", item.priority_composite != null ? `${Math.round(item.priority_composite)}/100` : null],
                  ["Status", item.status], ["Created", item.created_at?.slice(0, 10)],
                ].filter(([, v]) => v != null).map(([label, val, url]) => (
                  <div key={label} style={{ display: "flex", padding: "6px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
                    <span style={{ width: 120, fontSize: 11, color: theme.text.dim }}>{label}</span>
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: 12, color: theme.accent.blueLight,
                          textDecoration: "none", fontFamily: theme.font.mono,
                        }}
                        onMouseEnter={(e) => (e.target.style.textDecoration = "underline")}
                        onMouseLeave={(e) => (e.target.style.textDecoration = "none")}
                      >{val} ↗</a>
                    ) : (
                      <span style={{ fontSize: 12, color: theme.text.secondary }}>{val}</span>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>

          <div style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h4 style={{ ...sectionTitle, margin: 0 }}>Assignments</h4>
            </div>
            {editing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div><label style={labelStyle}>Lead Attorney</label>
                  <select style={inputStyle} value={editForm.lead_attorney_id} onChange={e => setEditForm({...editForm, lead_attorney_id: e.target.value})}>
                    <option value="">Unassigned</option>
                    {teamMembers.map(m => <option key={m.id} value={m.id}>{m.name} — {m.role}</option>)}
                  </select>
                </div>
                <div><label style={labelStyle}>Backup Attorney</label>
                  <select style={inputStyle} value={editForm.backup_attorney_id} onChange={e => setEditForm({...editForm, backup_attorney_id: e.target.value})}>
                    <option value="">Unassigned</option>
                    {teamMembers.map(m => <option key={m.id} value={m.id}>{m.name} — {m.role}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              (item.assignments || []).length === 0 ? (
                <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic" }}>No assignments — click Edit to assign</div>
              ) : item.assignments.map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, padding: "8px 0", borderBottom: `1px solid ${theme.border.subtle}`, alignItems: "center" }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: "linear-gradient(135deg, #1e3a5f, #2563eb)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                    {a.name?.split(" ").map(n => n[0]).join("")}
                  </div>
                  <span style={{ fontSize: 12, color: theme.text.secondary, fontWeight: 600, flex: 1 }}>{a.name}</span>
                  <Badge bg="#172554" text="#60a5fa" label={a.role} />
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ══════ DEADLINES TAB ══════════════════════════════════════════ */}
      {activeTab === "deadlines" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <button onClick={() => setShowAddDeadline(true)} style={actionBtn("#1e40af")}>+ Add Deadline</button>
            <button onClick={() => setShowBackwardCalc(true)} style={actionBtn("#334155")}>↻ Backward Calculate</button>
          </div>
          <div style={cardStyle}>
            {deadlines.length ? (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>{["Title", "Type", "Due Date", "Days Left", "Status", "Owner", ""].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontWeight: 600, color: theme.text.faint, fontSize: 10, textTransform: "uppercase", borderBottom: `1px solid ${theme.border.default}` }}>{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {deadlines.map((d) => (
                    <tr key={d.id} style={{ borderBottom: `1px solid ${theme.border.subtle}` }}>
                      <td style={tdStyle}><span style={{ fontWeight: 500 }}>{d.title}</span>{d.is_hard_deadline && <span style={{ marginLeft: 6, fontSize: 9, color: theme.accent.red }}>HARD</span>}</td>
                      <td style={tdStyle}><Badge bg="#172554" text="#60a5fa" label={d.deadline_type} /></td>
                      <td style={{...tdStyle, fontFamily: theme.font.mono, fontSize: 12}}>{d.due_date}</td>
                      <td style={tdStyle}><span style={{ fontWeight: 700, color: severityColor(d.severity) }}>{d.days_remaining ?? "—"}</span></td>
                      <td style={tdStyle}><Badge bg={d.status === "pending" ? "#1e3a5f" : "#14532d"} text={d.status === "pending" ? "#60a5fa" : "#4ade80"} label={d.status} /></td>
                      <td style={{...tdStyle, fontSize: 12}}>{d.owner_name || "—"}</td>
                      <td style={tdStyle}>
                        {d.status === "pending" && (
                          <button onClick={() => { setShowExtend(d.id); setExtForm({ new_due_date: "", reason: "" }); }} style={{ background: "transparent", border: "none", color: theme.accent.yellow, fontSize: 11, cursor: "pointer", fontWeight: 600 }}>Extend</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <EmptyState icon="⏰" title="No Deadlines" message="Add deadlines to track due dates for this item." actionLabel="Add Deadline" onAction={() => setShowAddDeadline(true)} />}
          </div>
        </div>
      )}

      {/* ══════ DOCUMENTS TAB ═════════════════════════════════════════ */}
      {activeTab === "documents" && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <button onClick={() => setShowUploadDoc(true)} style={actionBtn("#1e40af")}>+ Upload Document</button>
          </div>
          <div style={cardStyle}>
            {docs?.length ? docs.map((d) => (
              <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: theme.bg.input, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: theme.text.faint }}>📄</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>{d.title}</div>
                  <div style={{ fontSize: 11, color: theme.text.faint }}>v{d.version} · {d.document_type} · {d.file_size ? `${(d.file_size / 1024).toFixed(0)} KB` : ""} · {d.created_at?.slice(0, 10)}</div>
                  {d.change_summary && <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>{d.change_summary}</div>}
                </div>
                <Badge bg={d.is_current ? "#14532d" : "#1f2937"} text={d.is_current ? "#4ade80" : "#6b7280"} label={d.is_current ? "Current" : `v${d.version}`} />
              </div>
            )) : <EmptyState icon="📄" title="No Documents" message="Upload rule text, preambles, CBA analyses, and other documents." actionLabel="Upload Document" onAction={() => setShowUploadDoc(true)} />}
          </div>
        </div>
      )}

      {/* ══════ DECISION LOG TAB ══════════════════════════════════════ */}
      {activeTab === "log" && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <button onClick={() => setShowAddLog(true)} style={actionBtn("#1e40af")}>+ Add Entry</button>
          </div>
          <div style={cardStyle}>
            {(item.recent_decisions || []).map((d, i) => (
              <div key={i} style={{ padding: "12px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, alignItems: "center" }}>
                  <Badge bg="#172554" text="#60a5fa" label={d.action_type} />
                  <span style={{ fontSize: 10, color: theme.text.faint, fontFamily: theme.font.mono }}>{d.created_at}</span>
                </div>
                <div style={{ fontSize: 13, color: theme.text.secondary, marginTop: 4 }}>{d.description}</div>
                {d.rationale && <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 4, fontStyle: "italic" }}>Rationale: {d.rationale}</div>}
                {d.decided_by && <div style={{ fontSize: 10, color: theme.text.ghost, marginTop: 2 }}>By: {d.decided_by}</div>}
              </div>
            ))}
            {(item.recent_decisions || []).length === 0 && <EmptyState icon="📋" title="No Decision Log Entries" message="Stage changes and updates are automatically logged here." />}
          </div>
        </div>
      )}

      {/* ══════ STAGES TAB ════════════════════════════════════════════ */}
      {activeTab === "stages" && (
        <div style={cardStyle}>
          {stages.map((s, i) => {
            const isCurrent = s.stage_key === item.current_stage;
            const currentOrder = stages.find(st => st.stage_key === item.current_stage)?.stage_order || 0;
            const isPast = s.stage_order < currentOrder;
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: `1px solid ${theme.border.subtle}`, opacity: isPast ? 0.5 : 1 }}>
                <div style={{ width: 24, height: 24, borderRadius: "50%", background: isCurrent ? (s.stage_color || theme.accent.blue) : isPast ? "#14532d" : theme.border.default, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, color: "#fff" }}>
                  {isPast ? "✓" : s.stage_order}
                </div>
                <span style={{ fontSize: 13, fontWeight: isCurrent ? 700 : 500, color: isCurrent ? theme.text.primary : theme.text.dim, flex: 1 }}>{s.stage_label}</span>
                {s.sla_days && <span style={{ fontSize: 10, color: theme.text.faint }}>{s.sla_days}d SLA</span>}
                {isCurrent && <Badge bg="#1e3a5f" text="#60a5fa" label="CURRENT" />}
              </div>
            );
          })}
        </div>
      )}

      {/* ══════ MEETINGS TAB ══════════════════════════════════════════ */}
      {activeTab === "meetings" && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <button onClick={() => setShowAddMeeting(true)} style={actionBtn("#1e40af")}>+ Log Meeting</button>
          </div>
          <div style={cardStyle}>
            {meetings?.length ? meetings.map((m) => (
              <div key={m.id} style={{ padding: "12px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>{m.title}</span>
                    <Badge bg={m.meeting_type === "ex_parte" ? "#422006" : "#172554"} text={m.meeting_type === "ex_parte" ? "#fbbf24" : "#60a5fa"} label={m.meeting_type?.replace(/_/g, " ")} />
                    {m.is_ex_parte && <Badge bg="#450a0a" text="#f87171" label="EX PARTE" />}
                  </div>
                  <span style={{ fontSize: 11, color: theme.text.faint }}>{m.date}</span>
                </div>
                {m.summary && <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 4 }}>{m.summary}</div>}
                {m.attendees?.length > 0 && <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 4 }}>Attendees: {m.attendees.join(", ")}</div>}
              </div>
            )) : <EmptyState icon="📋" title="No Meetings" message="Log meetings related to this item." actionLabel="Log Meeting" onAction={() => setShowAddMeeting(true)} />}
          </div>
        </div>
      )}

      {/* ══════ MODALS ════════════════════════════════════════════════ */}
      <ConfirmDialog isOpen={showAdvanceConfirm} onClose={() => setShowAdvanceConfirm(false)} onConfirm={handleAdvance}
        title="Advance Stage" message={`Move "${item.title}" from "${item.stage_label}" to the next stage?`} confirmLabel="Advance" />

      {/* Add Deadline */}
      <Modal isOpen={showAddDeadline} onClose={() => setShowAddDeadline(false)} title="Add Deadline" width={500}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div><label style={labelStyle}>Type</label><select style={inputStyle} value={dlForm.deadline_type} onChange={e => setDlForm({...dlForm, deadline_type: e.target.value})}>{DEADLINE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></div>
            <div><label style={labelStyle}>Due Date *</label><input style={inputStyle} type="date" value={dlForm.due_date} onChange={e => setDlForm({...dlForm, due_date: e.target.value})} /></div>
          </div>
          <div><label style={labelStyle}>Title *</label><input style={inputStyle} value={dlForm.title} onChange={e => setDlForm({...dlForm, title: e.target.value})} placeholder="Deadline title" /></div>
          <div><label style={labelStyle}>Source</label><input style={inputStyle} value={dlForm.source} onChange={e => setDlForm({...dlForm, source: e.target.value})} placeholder="e.g., CEA Section 4c" /></div>
          <div><label style={labelStyle}>Owner</label><select style={inputStyle} value={dlForm.owner_id} onChange={e => setDlForm({...dlForm, owner_id: e.target.value})}><option value="">Unassigned</option>{teamMembers.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: theme.text.muted, cursor: "pointer" }}>
            <input type="checkbox" checked={dlForm.is_hard_deadline} onChange={e => setDlForm({...dlForm, is_hard_deadline: e.target.checked})} />
            Hard deadline (statutory or regulatory requirement)
          </label>
          <button onClick={handleCreateDeadline} disabled={!dlForm.title.trim() || !dlForm.due_date} style={{...actionBtn("#1e40af"), width: "100%", opacity: (!dlForm.title.trim() || !dlForm.due_date) ? 0.4 : 1}}>Create Deadline</button>
        </div>
      </Modal>

      {/* Extend Deadline */}
      <Modal isOpen={!!showExtend} onClose={() => setShowExtend(null)} title="Extend Deadline" width={440}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div><label style={labelStyle}>New Due Date *</label><input style={inputStyle} type="date" value={extForm.new_due_date} onChange={e => setExtForm({...extForm, new_due_date: e.target.value})} /></div>
          <div><label style={labelStyle}>Reason *</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={extForm.reason} onChange={e => setExtForm({...extForm, reason: e.target.value})} placeholder="Reason for extension" /></div>
          <button onClick={handleExtend} disabled={!extForm.new_due_date || !extForm.reason.trim()} style={{...actionBtn("#1e40af"), width: "100%", opacity: (!extForm.new_due_date || !extForm.reason.trim()) ? 0.4 : 1}}>Extend Deadline</button>
        </div>
      </Modal>

      {/* Backward Calculate */}
      <Modal isOpen={showBackwardCalc} onClose={() => setShowBackwardCalc(false)} title="Backward Calculate Deadlines" width={440}>
        <p style={{ color: theme.text.muted, fontSize: 13, lineHeight: 1.6, marginBottom: 16 }}>
          Enter the final deadline date. The system will auto-generate predecessor deadlines based on the SLA days for each stage of a {item.item_type?.replace(/_/g, " ")}.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div><label style={labelStyle}>Final Deadline Date *</label><input style={inputStyle} type="date" value={bcForm.final_deadline_date} onChange={e => setBcForm({...bcForm, final_deadline_date: e.target.value})} /></div>
          <button onClick={handleBackwardCalc} disabled={!bcForm.final_deadline_date} style={{...actionBtn("#1e40af"), width: "100%", opacity: !bcForm.final_deadline_date ? 0.4 : 1}}>Generate Deadlines</button>
        </div>
      </Modal>

      {/* Add Decision Log Entry */}
      <Modal isOpen={showAddLog} onClose={() => setShowAddLog(false)} title="Add Decision Log Entry" width={500}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div><label style={labelStyle}>Action Type</label><select style={inputStyle} value={logForm.action_type} onChange={e => setLogForm({...logForm, action_type: e.target.value})}>{DECISION_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></div>
          <div><label style={labelStyle}>Description *</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={logForm.description} onChange={e => setLogForm({...logForm, description: e.target.value})} placeholder="What was decided?" /></div>
          <div><label style={labelStyle}>Rationale</label><textarea style={{...inputStyle, minHeight: 40, resize: "vertical"}} value={logForm.rationale} onChange={e => setLogForm({...logForm, rationale: e.target.value})} placeholder="Why?" /></div>
          <button onClick={handleAddLog} disabled={!logForm.description.trim()} style={{...actionBtn("#1e40af"), width: "100%", opacity: !logForm.description.trim() ? 0.4 : 1}}>Add Entry</button>
        </div>
      </Modal>

      {/* Upload Document */}
      <Modal isOpen={showUploadDoc} onClose={() => setShowUploadDoc(false)} title="Upload Document" width={500}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div><label style={labelStyle}>File *</label><input type="file" onChange={e => setDocFile(e.target.files[0])} style={{ fontSize: 13, color: theme.text.muted }} /></div>
          <div><label style={labelStyle}>Document Type</label><select style={inputStyle} value={docForm.document_type} onChange={e => setDocForm({...docForm, document_type: e.target.value})}>{DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></div>
          <div><label style={labelStyle}>Title</label><input style={inputStyle} value={docForm.title} onChange={e => setDocForm({...docForm, title: e.target.value})} placeholder="Defaults to filename" /></div>
          <div><label style={labelStyle}>Change Summary</label><input style={inputStyle} value={docForm.change_summary} onChange={e => setDocForm({...docForm, change_summary: e.target.value})} placeholder="What changed in this version?" /></div>
          <button onClick={handleUploadDoc} disabled={!docFile} style={{...actionBtn("#1e40af"), width: "100%", opacity: !docFile ? 0.4 : 1}}>Upload</button>
        </div>
      </Modal>

      {/* Log Meeting */}
      <Modal isOpen={showAddMeeting} onClose={() => setShowAddMeeting(false)} title="Log Meeting" width={520}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div><label style={labelStyle}>Type</label><select style={inputStyle} value={mtForm.meeting_type} onChange={e => setMtForm({...mtForm, meeting_type: e.target.value})}>{["ex_parte","interagency","hill_briefing","public_roundtable","staff_conference","phone_call"].map(t => <option key={t} value={t}>{t.replace(/_/g," ")}</option>)}</select></div>
            <div><label style={labelStyle}>Date *</label><input style={inputStyle} type="date" value={mtForm.date} onChange={e => setMtForm({...mtForm, date: e.target.value})} /></div>
          </div>
          <div><label style={labelStyle}>Title *</label><input style={inputStyle} value={mtForm.title} onChange={e => setMtForm({...mtForm, title: e.target.value})} /></div>
          <div><label style={labelStyle}>Attendees</label><input style={inputStyle} value={mtForm.attendees} onChange={e => setMtForm({...mtForm, attendees: e.target.value})} placeholder="Comma-separated" /></div>
          <div><label style={labelStyle}>Summary</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={mtForm.summary} onChange={e => setMtForm({...mtForm, summary: e.target.value})} /></div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: theme.text.muted, cursor: "pointer" }}>
            <input type="checkbox" checked={mtForm.is_ex_parte} onChange={e => setMtForm({...mtForm, is_ex_parte: e.target.checked})} /> Ex parte communication
          </label>
          <button onClick={handleCreateMeeting} disabled={!mtForm.title.trim() || !mtForm.date} style={{...actionBtn("#1e40af"), width: "100%", opacity: (!mtForm.title.trim() || !mtForm.date) ? 0.4 : 1}}>Log Meeting</button>
        </div>
      </Modal>
    </div>
  );
}

// Helper components
function InfoBlock({ label, value, color, small }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: theme.text.faint, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: small ? 13 : 15, fontWeight: 700, color: color || theme.text.primary }}>{value}</div>
    </div>
  );
}

function Divider() {
  return <div style={{ width: 1, height: 30, background: theme.border.default }} />;
}

// Shared styles
const cardStyle = { background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 };
const sectionTitle = { fontSize: 12, fontWeight: 700, color: theme.text.muted, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" };
const tdStyle = { padding: "11px 14px", color: theme.text.secondary };

function actionBtn(bg) {
  return {
    padding: "8px 16px", borderRadius: 6, border: "none",
    background: bg, color: "#fff",
    fontSize: 13, fontWeight: 600, cursor: "pointer",
  };
}
