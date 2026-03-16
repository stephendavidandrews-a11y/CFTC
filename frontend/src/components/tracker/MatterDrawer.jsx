import React from "react";
import DrawerShell from "./DrawerShell";
import { fetchJSON } from "../../api/client";

const INPUT_STYLE = {
  width: "100%",
  padding: "8px 12px",
  borderRadius: 6,
  border: "1px solid #1f2937",
  background: "#0f172a",
  color: "#f1f5f9",
  fontSize: 13,
  boxSizing: "border-box",
};
const LABEL_STYLE = { display: "block", fontSize: 12, fontWeight: 600, color: "#94a3b8", marginBottom: 4 };
const SAVE_BTN = { background: "#1e40af", color: "#fff", padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const CANCEL_BTN = { background: "transparent", color: "#64748b", padding: "8px 20px", borderRadius: 8, fontSize: 13, border: "1px solid #1f2937", cursor: "pointer" };

const EMPTY = {
  title: "",
  matter_type: "",
  description: "",
  problem_statement: "",
  why_it_matters: "",
  status: "",
  priority: "",
  sensitivity: "",
  boss_involvement_level: "",
  risk_level: "",
  assigned_to_person_id: "",
  supervisor_person_id: "",
  client_organization_id: "",
  requesting_organization_id: "",
  reviewing_organization_id: "",
  work_deadline: "",
  external_deadline: "",
  decision_deadline: "",
  opened_date: "",
  next_step: "",
  next_step_assigned_to_person_id: "",
  pending_decision: "",
  revisit_date: "",
  outcome_summary: "",
  closed_at: "",
  rin: "",
  regulatory_stage: "",
  federal_register_citation: "",
  unified_agenda_priority: "",
  docket_number: "",
};

export default function MatterDrawer({ isOpen, onClose, matter, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [orgs, setOrgs] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  // Load lookups
  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/matter_type").catch(() => []),
      fetchJSON("/tracker/lookups/enums/matter_status").catch(() => []),
      fetchJSON("/tracker/lookups/enums/matter_priority").catch(() => []),
      fetchJSON("/tracker/lookups/enums/matter_sensitivity").catch(() => []),
      fetchJSON("/tracker/lookups/enums/boss_involvement_level").catch(() => []),
      fetchJSON("/tracker/lookups/enums/regulatory_stage").catch(() => []),
      fetchJSON("/tracker/lookups/enums/risk_level").catch(() => []),
      fetchJSON("/tracker/lookups/enums/unified_agenda_priority").catch(() => []),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/organizations?limit=100").catch(() => ({ items: [] })),
    ]).then(([matterType, status, priority, sensitivity, boss, regStage, riskLevel, uaPriority, ppl, orgList]) => {
      setEnums({
        matter_type: matterType,
        status,
        priority,
        sensitivity,
        boss_involvement: boss,
        regulatory_stage: regStage,
        risk_level: riskLevel,
        unified_agenda_priority: uaPriority,
      });
      setPeople(ppl.items || ppl || []);
      setOrgs(orgList.items || orgList || []);
    });
  }, [isOpen]);

  // Populate form when matter changes
  React.useEffect(() => {
    if (matter) {
      setForm({
        title: matter.title || "",
        matter_type: matter.matter_type || "",
        description: matter.description || "",
        problem_statement: matter.problem_statement || "",
        why_it_matters: matter.why_it_matters || "",
        status: matter.status || "",
        priority: matter.priority || "",
        sensitivity: matter.sensitivity || "",
        boss_involvement_level: matter.boss_involvement_level || "",
        risk_level: matter.risk_level || "",
        assigned_to_person_id: matter.assigned_to_person_id || "",
        supervisor_person_id: matter.supervisor_person_id || "",
        client_organization_id: matter.client_organization_id || "",
        requesting_organization_id: matter.requesting_organization_id || "",
        reviewing_organization_id: matter.reviewing_organization_id || "",
        work_deadline: matter.work_deadline || "",
        external_deadline: matter.external_deadline || "",
        decision_deadline: matter.decision_deadline || "",
        opened_date: matter.opened_date || "",
        next_step: matter.next_step || "",
        next_step_assigned_to_person_id: matter.next_step_assigned_to_person_id || "",
        pending_decision: matter.pending_decision || "",
        revisit_date: matter.revisit_date || "",
        outcome_summary: matter.outcome_summary || "",
        closed_at: matter.closed_at || "",
        rin: matter.rin || "",
        regulatory_stage: matter.regulatory_stage || "",
        federal_register_citation: matter.federal_register_citation || "",
        unified_agenda_priority: matter.unified_agenda_priority || "",
        docket_number: matter.docket_number || "",
      });
    } else {
      setForm({ ...EMPTY });
    }
    setError(null);
  }, [matter, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      // Convert empty strings to null for optional fields
      Object.keys(payload).forEach((k) => {
        if (payload[k] === "") payload[k] = null;
      });
      if (!matter?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const missing = [];
      if (!payload.title) missing.push("Title");
      if (!payload.matter_type) missing.push("Matter Type");
      if (payload.status === "closed" && !payload.outcome_summary) missing.push("Outcome Summary (required when closing)");
      if (missing.length > 0) { setError("Required fields missing: " + missing.join(", ")); setSaving(false); return; }

      if (matter?.id) {
        await fetchJSON(`/tracker/matters/${matter.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await fetchJSON("/tracker/matters", { method: "POST", body: JSON.stringify(payload) });
      }
      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const renderSelect = (label, field, options) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <select style={INPUT_STYLE} value={form[field]} onChange={set(field)}>
        <option value="">--</option>
        {(Array.isArray(options) ? options : []).map((v) => (
          <option key={typeof v === "object" ? v.value : v} value={typeof v === "object" ? v.value : v}>
            {typeof v === "object" ? v.label || v.value : v}
          </option>
        ))}
      </select>
    </div>
  );

  const renderInput = (label, field, type = "text", extra = {}) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <input style={INPUT_STYLE} type={type} value={form[field]} onChange={set(field)} {...extra} />
    </div>
  );

  const isRulemaking = form.matter_type === "rulemaking";
  const orgOpts = orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));
  const personOpts = people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={matter ? "Edit Matter" : "New Matter"}>
      {renderInput("Title *", "title", "text", { required: true })}
      {renderSelect("Matter Type *", "matter_type", enums.matter_type)}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Description</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.description} onChange={set("description")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Problem Statement</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.problem_statement} onChange={set("problem_statement")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Why It Matters</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.why_it_matters} onChange={set("why_it_matters")} />
      </div>
      {renderSelect("Status", "status", enums.status)}
      {renderSelect("Priority", "priority", enums.priority)}
      {renderSelect("Sensitivity", "sensitivity", enums.sensitivity)}
      {renderSelect("Boss Involvement", "boss_involvement_level", enums.boss_involvement)}
      {renderSelect("Risk Level", "risk_level", enums.risk_level)}
      {renderSelect("Owner", "assigned_to_person_id", personOpts)}
      {renderSelect("Supervisor", "supervisor_person_id", personOpts)}
      {renderSelect("Client Organization", "client_organization_id", orgOpts)}
      {renderSelect("Requesting Organization", "requesting_organization_id", orgOpts)}
      {renderSelect("Reviewing Organization", "reviewing_organization_id", orgOpts)}
      {renderInput("Work Deadline", "work_deadline", "date")}
      {renderInput("External Deadline", "external_deadline", "date")}
      {renderInput("Revisit Date", "revisit_date", "date")}
      {renderInput("Decision Deadline", "decision_deadline", "date")}
      {renderInput("Opened Date", "opened_date", "date")}
      {renderInput("Next Step", "next_step")}
      {renderSelect("Next Step Owner", "next_step_assigned_to_person_id", personOpts)}
      {form.status && form.status !== "closed" && !form.next_step_assigned_to_person_id && (
        <div style={{ color: "#f59e0b", fontSize: 11, marginTop: -10, marginBottom: 10 }}>Consider assigning a next step owner</div>
      )}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Pending Decision</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.pending_decision} onChange={set("pending_decision")} placeholder="What decision is pending?" />
      </div>
      {isRulemaking && renderInput("RIN", "rin")}
      {isRulemaking && renderSelect("Regulatory Stage", "regulatory_stage", enums.regulatory_stage)}
      {isRulemaking && renderInput("FR Citation", "federal_register_citation")}
      {isRulemaking && renderSelect("Unified Agenda Priority", "unified_agenda_priority", enums.unified_agenda_priority)}
      {isRulemaking && renderInput("Docket Number", "docket_number")}

      {form.status === "parked / monitoring" && !form.revisit_date && (
        <div style={{ color: "#f59e0b", fontSize: 12, marginBottom: 10, padding: "6px 10px", background: "#422006", borderRadius: 6, border: "1px solid #854d0e" }}>Revisit date is recommended for parked/monitoring matters</div>
      )}
      {form.status === "closed" && (
        <>
          <div style={{ marginBottom: 14 }}>
            <label style={{ ...LABEL_STYLE, color: form.status === "closed" && !form.outcome_summary ? "#f59e0b" : "#94a3b8" }}>Outcome Summary *</label>
            <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical", borderColor: form.status === "closed" && !form.outcome_summary ? "#854d0e" : "#1f2937" }} value={form.outcome_summary} onChange={set("outcome_summary")} placeholder="Summarize the outcome of this matter" />
          </div>
          {renderInput("Closed At", "closed_at", "date")}
        </>
      )}

      {error && <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 16, borderTop: "1px solid #1f2937", marginTop: 10 }}>
        <button style={CANCEL_BTN} onClick={onClose}>Cancel</button>
        <button style={{ ...SAVE_BTN, opacity: saving ? 0.6 : 1 }} onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </DrawerShell>
  );
}
