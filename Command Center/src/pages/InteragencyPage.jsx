import React, { useState } from "react";
import theme from "../styles/theme";
import Modal from "../components/shared/Modal";
import DataTable from "../components/shared/DataTable";
import EmptyState from "../components/shared/EmptyState";
import Badge from "../components/shared/Badge";
import { useToastContext } from "../contexts/ToastContext";
import useApi from "../hooks/useApi";
import {
  listStakeholders, createStakeholder, listMeetings, createMeeting,
  listContacts, createContact, getDormantContacts,
  listInteragencyRules, createInteragencyRule,
} from "../api/pipeline";

const STAKEHOLDER_TYPES = ["industry", "congressional", "interagency", "academic", "public_interest", "international"];
const MEETING_TYPES = ["ex_parte", "interagency", "hill_briefing", "public_roundtable", "staff_conference", "phone_call"];
const AGENCIES = ["SEC", "Treasury", "Fed Reserve", "OCC", "FDIC", "FSOC", "OMB", "DOJ", "FTC", "CFPB", "FHFA", "NCUA", "OFR", "State Regulators", "Other"];
const RELATIONSHIP_STATUSES = ["close_ally", "regular_contact", "acquaintance", "new", "dormant"];
const IA_RULE_TYPES = ["NPRM", "Final Rule", "Request for Comment", "Guidance", "Report", "Joint Statement", "Advisory", "Other"];
const IA_RULE_STATUSES = ["active", "comment_period_open", "comment_period_closed", "final_pending", "effective", "withdrawn"];

const inputStyle = {
  width: "100%", padding: "9px 12px", borderRadius: 8, fontSize: 13,
  background: theme.bg.input, color: theme.text.primary,
  border: `1px solid ${theme.border.default}`, outline: "none",
  fontFamily: theme.font.family,
};

const labelStyle = { display: "block", fontSize: 12, fontWeight: 600, color: theme.text.muted, marginBottom: 6 };

const REL_COLORS = {
  close_ally: { bg: "#052e16", text: "#4ade80" },
  regular_contact: { bg: "#172554", text: "#60a5fa" },
  acquaintance: { bg: "#1f2937", text: "#9ca3af" },
  new: { bg: "#1e1b4b", text: "#a78bfa" },
  dormant: { bg: "#450a0a", text: "#f87171" },
};

export default function InteragencyPage() {
  const toast = useToastContext();
  const [tab, setTab] = useState("stakeholders");
  const [showAddStakeholder, setShowAddStakeholder] = useState(false);
  const [showAddMeeting, setShowAddMeeting] = useState(false);
  const [showAddContact, setShowAddContact] = useState(false);
  const [showAddRule, setShowAddRule] = useState(false);
  const [shForm, setShForm] = useState({ name: "", organization: "", stakeholder_type: "interagency", title: "", email: "", phone: "", notes: "" });
  const [mtForm, setMtForm] = useState({ meeting_type: "interagency", title: "", date: "", attendees: "", summary: "", is_ex_parte: false });
  const [ctForm, setCtForm] = useState({ name: "", title: "", agency: "SEC", email: "", phone: "", areas_of_focus: "", relationship_status: "new", notes: "" });
  const [ruleForm, setRuleForm] = useState({ title: "", agency: "SEC", rule_type: "NPRM", topics: "", status: "active", url: "", summary: "", cftc_position: "", impact_on_cftc_work: "" });

  const { data: stakeholders, refetch: refetchSh } = useApi(listStakeholders, []);
  const { data: meetings, refetch: refetchMt } = useApi(listMeetings, []);
  const { data: contacts, refetch: refetchCt } = useApi(listContacts, []);
  const { data: dormant } = useApi(() => getDormantContacts(90), []);
  const { data: iaRules, refetch: refetchRules } = useApi(listInteragencyRules, []);

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

  const contactColumns = [
    { key: "name", label: "Name", width: "16%" },
    { key: "agency", label: "Agency", width: "10%", render: (v) => (
      <Badge bg="#172554" text="#60a5fa" label={v || "—"} />
    )},
    { key: "title", label: "Title", width: "18%" },
    { key: "email", label: "Email", width: "16%" },
    { key: "relationship_status", label: "Relationship", width: "12%", render: (v) => {
      const c = REL_COLORS[v] || REL_COLORS.new;
      return <Badge bg={c.bg} text={c.text} label={v ? v.replace(/_/g, " ") : "—"} />;
    }},
    { key: "last_contact_date", label: "Last Contact", width: "12%" },
    { key: "areas_of_focus", label: "Focus Areas", width: "16%", render: (v) => {
      const arr = Array.isArray(v) ? v : [];
      return arr.length > 0
        ? <span style={{ fontSize: 11 }}>{arr.slice(0, 2).join(", ")}{arr.length > 2 ? ` +${arr.length - 2}` : ""}</span>
        : "—";
    }},
  ];

  const ruleColumns = [
    { key: "title", label: "Title", width: "24%" },
    { key: "agency", label: "Agency", width: "10%", render: (v) => (
      <Badge bg="#172554" text="#60a5fa" label={v || "—"} />
    )},
    { key: "rule_type", label: "Type", width: "10%", render: (v) => (
      <Badge bg="#1e1b4b" text="#a78bfa" label={v || "—"} />
    )},
    { key: "status", label: "Status", width: "12%", render: (v) => (
      <span style={{ fontSize: 11, color: theme.text.dim }}>{v ? v.replace(/_/g, " ") : "—"}</span>
    )},
    { key: "cftc_position", label: "CFTC Position", width: "20%", render: (v) => (
      <span style={{ display: "block", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v || "—"}</span>
    )},
    { key: "impact_on_cftc_work", label: "Impact", width: "24%", render: (v) => (
      <span style={{ display: "block", maxWidth: 250, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v || "—"}</span>
    )},
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

  const handleCreateContact = async () => {
    try {
      const payload = {
        ...ctForm,
        areas_of_focus: ctForm.areas_of_focus ? ctForm.areas_of_focus.split(",").map(s => s.trim()).filter(Boolean) : [],
      };
      await createContact(payload);
      toast.success("Contact added");
      setShowAddContact(false);
      setCtForm({ name: "", title: "", agency: "SEC", email: "", phone: "", areas_of_focus: "", relationship_status: "new", notes: "" });
      refetchCt();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleCreateRule = async () => {
    try {
      const payload = {
        ...ruleForm,
        topics: ruleForm.topics ? ruleForm.topics.split(",").map(s => s.trim()).filter(Boolean) : [],
      };
      await createInteragencyRule(payload);
      toast.success("Rulemaking added");
      setShowAddRule(false);
      setRuleForm({ title: "", agency: "SEC", rule_type: "NPRM", topics: "", status: "active", url: "", summary: "", cftc_position: "", impact_on_cftc_work: "" });
      refetchRules();
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

  const addButtonLabel = {
    stakeholders: "Add Stakeholder",
    meetings: "Log Meeting",
    contacts: "Add Contact",
    rulemakings: "Add Rulemaking",
  };

  const addButtonHandler = {
    stakeholders: () => setShowAddStakeholder(true),
    meetings: () => setShowAddMeeting(true),
    contacts: () => setShowAddContact(true),
    rulemakings: () => setShowAddRule(true),
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Interagency & Stakeholders</h1>
          <p style={{ color: theme.text.faint, fontSize: 13, margin: "4px 0 0" }}>
            Stakeholder directory, meeting log, contacts, and interagency rulemakings
            {dormant?.length > 0 && (
              <span style={{ color: theme.accent.yellow, marginLeft: 8 }}>
                {dormant.length} dormant contact{dormant.length !== 1 ? "s" : ""}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={addButtonHandler[tab]}
          style={{
            padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "#1e40af", color: "#fff", border: "none", cursor: "pointer",
          }}
        >
          + {addButtonLabel[tab]}
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        <button style={tabStyle(tab === "stakeholders")} onClick={() => setTab("stakeholders")}>
          Stakeholders {stakeholders?.length ? `(${stakeholders.length})` : ""}
        </button>
        <button style={tabStyle(tab === "meetings")} onClick={() => setTab("meetings")}>
          Meetings {meetings?.length ? `(${meetings.length})` : ""}
        </button>
        <button style={tabStyle(tab === "contacts")} onClick={() => setTab("contacts")}>
          Contacts {contacts?.length ? `(${contacts.length})` : ""}
        </button>
        <button style={tabStyle(tab === "rulemakings")} onClick={() => setTab("rulemakings")}>
          Rulemakings {iaRules?.length ? `(${iaRules.length})` : ""}
        </button>
      </div>

      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "4px 16px" }}>
        {tab === "stakeholders" ? (
          stakeholders?.length ? (
            <DataTable columns={stakeholderColumns} data={stakeholders} pageSize={20} />
          ) : (
            <EmptyState icon="⬡" title="No Stakeholders" message="Add your first stakeholder to build the directory." actionLabel="Add Stakeholder" onAction={() => setShowAddStakeholder(true)} />
          )
        ) : tab === "meetings" ? (
          meetings?.length ? (
            <DataTable columns={meetingColumns} data={meetings} pageSize={20} />
          ) : (
            <EmptyState icon="📋" title="No Meetings" message="Log meetings to track interagency coordination and ex parte contacts." actionLabel="Log Meeting" onAction={() => setShowAddMeeting(true)} />
          )
        ) : tab === "contacts" ? (
          contacts?.length ? (
            <DataTable columns={contactColumns} data={contacts} pageSize={20} />
          ) : (
            <EmptyState icon="📇" title="No Contacts" message="Add interagency contacts to track relationships." actionLabel="Add Contact" onAction={() => setShowAddContact(true)} />
          )
        ) : (
          iaRules?.length ? (
            <DataTable columns={ruleColumns} data={iaRules} pageSize={20} />
          ) : (
            <EmptyState icon="📑" title="No Rulemakings" message="Track other agencies' rulemakings that affect CFTC work." actionLabel="Add Rulemaking" onAction={() => setShowAddRule(true)} />
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

      {/* Add Contact Modal */}
      <Modal isOpen={showAddContact} onClose={() => setShowAddContact(false)} title="Add Interagency Contact" width={520}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div><label style={labelStyle}>Name *</label><input style={inputStyle} value={ctForm.name} onChange={e => setCtForm({...ctForm, name: e.target.value})} placeholder="Full name" /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Agency *</label><select style={inputStyle} value={ctForm.agency} onChange={e => setCtForm({...ctForm, agency: e.target.value})}>{AGENCIES.map(a => <option key={a} value={a}>{a}</option>)}</select></div>
            <div><label style={labelStyle}>Relationship</label><select style={inputStyle} value={ctForm.relationship_status} onChange={e => setCtForm({...ctForm, relationship_status: e.target.value})}>{RELATIONSHIP_STATUSES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}</select></div>
          </div>
          <div><label style={labelStyle}>Title</label><input style={inputStyle} value={ctForm.title} onChange={e => setCtForm({...ctForm, title: e.target.value})} placeholder="Job title" /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Email</label><input style={inputStyle} type="email" value={ctForm.email} onChange={e => setCtForm({...ctForm, email: e.target.value})} /></div>
            <div><label style={labelStyle}>Phone</label><input style={inputStyle} value={ctForm.phone} onChange={e => setCtForm({...ctForm, phone: e.target.value})} /></div>
          </div>
          <div><label style={labelStyle}>Areas of Focus</label><input style={inputStyle} value={ctForm.areas_of_focus} onChange={e => setCtForm({...ctForm, areas_of_focus: e.target.value})} placeholder="Comma-separated, e.g., derivatives, clearing, crypto" /></div>
          <div><label style={labelStyle}>Notes</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={ctForm.notes} onChange={e => setCtForm({...ctForm, notes: e.target.value})} /></div>
          <button onClick={handleCreateContact} disabled={!ctForm.name.trim()} style={{
            padding: "10px 0", borderRadius: 8, fontSize: 14, fontWeight: 600,
            background: ctForm.name.trim() ? "#1e40af" : theme.bg.input, color: ctForm.name.trim() ? "#fff" : theme.text.ghost,
            border: "none", cursor: ctForm.name.trim() ? "pointer" : "default", marginTop: 4,
          }}>Add Contact</button>
        </div>
      </Modal>

      {/* Add Rulemaking Modal */}
      <Modal isOpen={showAddRule} onClose={() => setShowAddRule(false)} title="Add Interagency Rulemaking" width={560}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div><label style={labelStyle}>Title *</label><input style={inputStyle} value={ruleForm.title} onChange={e => setRuleForm({...ruleForm, title: e.target.value})} placeholder="Rulemaking title" /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Agency *</label><select style={inputStyle} value={ruleForm.agency} onChange={e => setRuleForm({...ruleForm, agency: e.target.value})}>{AGENCIES.map(a => <option key={a} value={a}>{a}</option>)}</select></div>
            <div><label style={labelStyle}>Type</label><select style={inputStyle} value={ruleForm.rule_type} onChange={e => setRuleForm({...ruleForm, rule_type: e.target.value})}>{IA_RULE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select></div>
            <div><label style={labelStyle}>Status</label><select style={inputStyle} value={ruleForm.status} onChange={e => setRuleForm({...ruleForm, status: e.target.value})}>{IA_RULE_STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select></div>
          </div>
          <div><label style={labelStyle}>Topics</label><input style={inputStyle} value={ruleForm.topics} onChange={e => setRuleForm({...ruleForm, topics: e.target.value})} placeholder="Comma-separated topics" /></div>
          <div><label style={labelStyle}>URL</label><input style={inputStyle} value={ruleForm.url} onChange={e => setRuleForm({...ruleForm, url: e.target.value})} placeholder="https://..." /></div>
          <div><label style={labelStyle}>Summary</label><textarea style={{...inputStyle, minHeight: 60, resize: "vertical"}} value={ruleForm.summary} onChange={e => setRuleForm({...ruleForm, summary: e.target.value})} /></div>
          <div><label style={labelStyle}>CFTC Position</label><input style={inputStyle} value={ruleForm.cftc_position} onChange={e => setRuleForm({...ruleForm, cftc_position: e.target.value})} placeholder="CFTC's stance on this rulemaking" /></div>
          <div><label style={labelStyle}>Impact on CFTC Work</label><textarea style={{...inputStyle, minHeight: 50, resize: "vertical"}} value={ruleForm.impact_on_cftc_work} onChange={e => setRuleForm({...ruleForm, impact_on_cftc_work: e.target.value})} placeholder="How does this affect CFTC operations?" /></div>
          <button onClick={handleCreateRule} disabled={!ruleForm.title.trim()} style={{
            padding: "10px 0", borderRadius: 8, fontSize: 14, fontWeight: 600,
            background: ruleForm.title.trim() ? "#1e40af" : theme.bg.input, color: ruleForm.title.trim() ? "#fff" : theme.text.ghost,
            border: "none", cursor: ruleForm.title.trim() ? "pointer" : "default", marginTop: 4,
          }}>Add Rulemaking</button>
        </div>
      </Modal>
    </div>
  );
}
