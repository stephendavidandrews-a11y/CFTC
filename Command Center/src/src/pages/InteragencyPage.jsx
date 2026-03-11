import React, { useState } from "react";
import theme from "../styles/theme";
import Modal from "../components/shared/Modal";
import DataTable from "../components/shared/DataTable";
import EmptyState from "../components/shared/EmptyState";
import Badge from "../components/shared/Badge";
import { useToastContext } from "../contexts/ToastContext";
import useApi from "../hooks/useApi";
import { listStakeholders, createStakeholder, listMeetings, createMeeting } from "../api/pipeline";

const STAKEHOLDER_TYPES = ["industry", "congressional", "interagency", "academic", "public_interest", "international"];
const MEETING_TYPES = ["ex_parte", "interagency", "hill_briefing", "public_roundtable", "staff_conference", "phone_call"];

const inputStyle = {
  width: "100%", padding: "9px 12px", borderRadius: 8, fontSize: 13,
  background: theme.bg.input, color: theme.text.primary,
  border: `1px solid ${theme.border.default}`, outline: "none",
  fontFamily: theme.font.family,
};

const labelStyle = { display: "block", fontSize: 12, fontWeight: 600, color: theme.text.muted, marginBottom: 6 };

export default function InteragencyPage() {
  const toast = useToastContext();
  const [tab, setTab] = useState("stakeholders");
  const [showAddStakeholder, setShowAddStakeholder] = useState(false);
  const [showAddMeeting, setShowAddMeeting] = useState(false);
  const [shForm, setShForm] = useState({ name: "", organization: "", stakeholder_type: "interagency", title: "", email: "", phone: "", notes: "" });
  const [mtForm, setMtForm] = useState({ meeting_type: "interagency", title: "", date: "", attendees: "", summary: "", is_ex_parte: false });

  const { data: stakeholders, refetch: refetchSh } = useApi(listStakeholders, []);
  const { data: meetings, refetch: refetchMt } = useApi(listMeetings, []);

  const stakeholderColumns = [
    { key: "name", label: "Name", width: "18%" },
    { key: "organization", label: "Organization", width: "18%" },
    { key: "stakeholder_type", label: "Type", width: "12%", render: (v) => (
      <Badge bg="#172554" text="#60a5fa" label={v ? v.replace(/_/g, " ") : "—"} />
    )},
    { key: "title", label: "Title", width: "18%" },
    { key: "email", label: "Email", width: "18%" },
    { key: "phone", label: "Phone", width: "14%" },
  ];

  const meetingColumns = [
    { key: "title", label: "Title", width: "22%" },
    { key: "meeting_type", label: "Type", width: "12%", render: (v) => (
      <Badge bg={v === "ex_parte" ? "#422006" : "#172554"} text={v === "ex_parte" ? "#fbbf24" : "#60a5fa"} label={v ? v.replace(/_/g, " ") : "—"} />
    )},
    { key: "date", label: "Date", width: "12%" },
    { key: "summary", label: "Summary", width: "36%", render: (v) => (
      <span style={{ display: "block", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v || "—"}</span>
    )},
    { key: "is_ex_parte", label: "Ex Parte", width: "8%", render: (v) => v ? (
      <Badge bg="#422006" text="#fbbf24" label="Yes" />
    ) : "—" },
    { key: "ex_parte_filed", label: "Filed", width: "8%", render: (v) => v ? "✓" : "" },
  ];

  const handleCreateStakeholder = async () => {
    try {
      await createStakeholder(shForm);
      toast.success("Stakeholder created");
      setShowAddStakeholder(false);
      setShForm({ name: "", organization: "", stakeholder_type: "interagency", title: "", email: "", phone: "", notes: "" });
      refetchSh();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleCreateMeeting = async () => {
    try {
      const payload = {
        ...mtForm,
        attendees: mtForm.attendees ? mtForm.attendees.split(",").map(s => s.trim()).filter(Boolean) : [],
      };
      await createMeeting(payload);
      toast.success("Meeting logged");
      setShowAddMeeting(false);
      setMtForm({ meeting_type: "interagency", title: "", date: "", attendees: "", summary: "", is_ex_parte: false });
      refetchMt();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const tabStyle = (active) => ({
    padding: "8px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
    background: active ? "rgba(59,130,246,0.12)" : "transparent",
    color: active ? theme.accent.blueLight : theme.text.dim,
    border: active ? "1px solid rgba(59,130,246,0.2)" : "1px solid transparent",
    cursor: "pointer",
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Interagency & Stakeholders</h1>
          <p style={{ color: theme.text.faint, fontSize: 13, margin: "4px 0 0" }}>Stakeholder directory, meeting log, and ex parte tracking</p>
        </div>
        <button
          onClick={() => tab === "stakeholders" ? setShowAddStakeholder(true) : setShowAddMeeting(true)}
          style={{
            padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "#1e40af", color: "#fff", border: "none", cursor: "pointer",
          }}
        >
          + {tab === "stakeholders" ? "Add Stakeholder" : "Log Meeting"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        <button style={tabStyle(tab === "stakeholders")} onClick={() => setTab("stakeholders")}>
          Stakeholders {stakeholders?.length ? `(${stakeholders.length})` : ""}
        </button>
        <button style={tabStyle(tab === "meetings")} onClick={() => setTab("meetings")}>
          Meetings {meetings?.length ? `(${meetings.length})` : ""}
        </button>
      </div>

      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "4px 16px" }}>
        {tab === "stakeholders" ? (
          stakeholders?.length ? (
            <DataTable columns={stakeholderColumns} data={stakeholders} pageSize={20} />
          ) : (
            <EmptyState icon="⬡" title="No Stakeholders" message="Add your first stakeholder to build the directory." actionLabel="Add Stakeholder" onAction={() => setShowAddStakeholder(true)} />
          )
        ) : (
          meetings?.length ? (
            <DataTable columns={meetingColumns} data={meetings} pageSize={20} />
          ) : (
            <EmptyState icon="📋" title="No Meetings" message="Log meetings to track interagency coordination and ex parte contacts." actionLabel="Log Meeting" onAction={() => setShowAddMeeting(true)} />
          )
        )}
      </div>

      {/* Add Stakeholder Modal */}
      <Modal isOpen={showAddStakeholder} onClose={() => setShowAddStakeholder(false)} title="Add Stakeholder" width={520}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div><label style={labelStyle}>Name *</label><input style={inputStyle} value={shForm.name} onChange={e => setShForm({...shForm, name: e.target.value})} placeholder="Full name" /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Organization</label><input style={inputStyle} value={shForm.organization} onChange={e => setShForm({...shForm, organization: e.target.value})} /></div>
            <div><label style={labelStyle}>Type</label><select style={inputStyle} value={shForm.stakeholder_type} onChange={e => setShForm({...shForm, stakeholder_type: e.target.value})}>{STAKEHOLDER_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></div>
          </div>
          <div><label style={labelStyle}>Title</label><input style={inputStyle} value={shForm.title} onChange={e => setShForm({...shForm, title: e.target.value})} placeholder="Job title" /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Email</label><input style={inputStyle} type="email" value={shForm.email} onChange={e => setShForm({...shForm, email: e.target.value})} /></div>
            <div><label style={labelStyle}>Phone</label><input style={inputStyle} value={shForm.phone} onChange={e => setShForm({...shForm, phone: e.target.value})} /></div>
          </div>
          <div><label style={labelStyle}>Notes</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={shForm.notes} onChange={e => setShForm({...shForm, notes: e.target.value})} /></div>
          <button onClick={handleCreateStakeholder} disabled={!shForm.name.trim()} style={{
            padding: "10px 0", borderRadius: 8, fontSize: 14, fontWeight: 600,
            background: shForm.name.trim() ? "#1e40af" : theme.bg.input, color: shForm.name.trim() ? "#fff" : theme.text.ghost,
            border: "none", cursor: shForm.name.trim() ? "pointer" : "default", marginTop: 4,
          }}>Create Stakeholder</button>
        </div>
      </Modal>

      {/* Log Meeting Modal */}
      <Modal isOpen={showAddMeeting} onClose={() => setShowAddMeeting(false)} title="Log Meeting" width={520}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Meeting Type</label><select style={inputStyle} value={mtForm.meeting_type} onChange={e => setMtForm({...mtForm, meeting_type: e.target.value})}>{MEETING_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></div>
            <div><label style={labelStyle}>Date *</label><input style={inputStyle} type="date" value={mtForm.date} onChange={e => setMtForm({...mtForm, date: e.target.value})} /></div>
          </div>
          <div><label style={labelStyle}>Title *</label><input style={inputStyle} value={mtForm.title} onChange={e => setMtForm({...mtForm, title: e.target.value})} placeholder="Meeting title" /></div>
          <div><label style={labelStyle}>Attendees</label><input style={inputStyle} value={mtForm.attendees} onChange={e => setMtForm({...mtForm, attendees: e.target.value})} placeholder="Comma-separated names" /></div>
          <div><label style={labelStyle}>Summary</label><textarea style={{...inputStyle, minHeight: 80, resize: "vertical"}} value={mtForm.summary} onChange={e => setMtForm({...mtForm, summary: e.target.value})} /></div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: theme.text.muted, cursor: "pointer" }}>
            <input type="checkbox" checked={mtForm.is_ex_parte} onChange={e => setMtForm({...mtForm, is_ex_parte: e.target.checked})} />
            Ex parte communication (requires filing)
          </label>
          <button onClick={handleCreateMeeting} disabled={!mtForm.title.trim() || !mtForm.date} style={{
            padding: "10px 0", borderRadius: 8, fontSize: 14, fontWeight: 600,
            background: (mtForm.title.trim() && mtForm.date) ? "#1e40af" : theme.bg.input,
            color: (mtForm.title.trim() && mtForm.date) ? "#fff" : theme.text.ghost,
            border: "none", cursor: (mtForm.title.trim() && mtForm.date) ? "pointer" : "default", marginTop: 4,
          }}>Log Meeting</button>
        </div>
      </Modal>
    </div>
  );
}
