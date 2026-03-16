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
  status: "",
  priority: "",
  sensitivity: "",
  boss_involvement_level: "",
  assigned_to_person_id: "",
  supervisor_person_id: "",
  client_organization_id: "",
  work_deadline: "",
  external_deadline: "",
  decision_deadline: "",
  next_step: "",
  next_step_assigned_to_person_id: "",
  pending_decision: "",
  revisit_date: "",
  outcome_summary: "",
  closed_at: "",
  rin: "",
  regulatory_stage: "",
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
      fetchJSON("/tracker/lookups/enums/priority").catch(() => []),
      fetchJSON("/tracker/lookups/enums/sensitivity").catch(() => []),
      fetchJSON("/tracker/lookups/enums/boss_involvement").catch(() => []),
      fetchJSON("/tracker/lookups/enums/regulatory_stage").catch(() => []),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/organizations?limit=100").catch(() => ({ items: [] })),
    ]).then(([matterType, status, priority, sensitivity, boss, regStage, ppl, orgList]) => {
      setEnums({
        matter_type: matterType,
        status,
        priority,
        sensitivity,
        boss_involvement: boss,
        regulatory_stage: regStage,
      });
      setPeople(ppl.items || ppl || []);
      setOrgs(orgList.items || orgList || []);
    });
  }, [isOpen]);

  // Populate form when matter changes — use correct backend field names
  React.useEffect(() => {
    if (matter) {
      setForm({
        title: matter.title || "",
        matter_type: matter.matter_type || "",
        description: matter.description || "",
        status: matter.status || "",
        priority: matter.priority || "",
        sensitivity: matter.sensitivity || "",
        boss_involvement_level: matter.boss_involvement_level || "",
        assigned_to_person_id: matter.assigned_to_person_id || "",
        supervisor_person_id: matter.supervisor_person_id || "",
        client_organization_id: matter.client_organization_id || "",
        work_deadline: matter.work_deadline || "",
        external_deadline: matter.external_deadline || "",
        decision_deadline: matter.decision_deadline || "",
        next_step: matter.next_step || "",
        next_step_assigned_to_person_id: matter.next_step_assigned_to_person_id || "",
        pending_decision: matter.pending_decision || "",
        revisit_date: matter.revisit_date || "",
        outcome_summary: matter.outcome_summary || "",
        closed_at: matter.closed_at || "",
        rin: matter.rin || "",
        regulatory_stage: matter.regulatory_stage || "",
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
      if (!payload.title) { setError("Title is required"); setSaving(false); return; }
      if (payload.status === "closed" && !payload.outcome_summary) { setError("Outcome summary is required when closing a matter"); setSaving(false); return; }

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

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={matter ? "Edit Matter" : "New Matter"}>
      {renderInput("Title", "title", "text", { required: true })}
      {renderSelect("Matter Type", "matter_type", enums.matter_type)}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Description</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.description} onChange={set("description")} />
      </div>
      {renderSelect("Status", "status", enums.status)}
      {renderSelect("Priority", "priority", enums.priority)}
      {renderSelect("Sensitivity", "sensitivity", enums.sensitivity)}
      {renderSelect("Boss Involvement", "boss_involvement_level", enums.boss_involvement)}
      {renderSelect("Owner", "assigned_to_person_id", people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` })))}
      {renderSelect("Supervisor", "supervisor_person_id", people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` })))}
      {renderSelect("Client Organization", "client_organization_id", orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` })))}
      {renderInput("Work Deadline", "work_deadline", "date")}
      {renderInput("External Deadline", "external_deadline", "date")}
      {renderInput("Revisit Date", "revisit_date", "date")}
      {renderInput("Decision Deadline", "decision_deadline", "date")}
      {renderInput("Next Step", "next_step")}
      {renderSelect("Next Step Owner", "next_step_assigned_to_person_id", people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` })))}
      {form.status && form.status !== "closed" && !form.next_step_assigned_to_person_id && (
        <div style={{ color: "#f59e0b", fontSize: 11, marginTop: -10, marginBottom: 10 }}>Consider assigning a next step owner</div>
      )}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Pending Decision</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.pending_decision} onChange={set("pending_decision")} placeholder="What decision is pending?" />
      </div>
      {isRulemaking && renderInput("RIN", "rin")}
      {isRulemaking && renderSelect("Regulatory Stage", "regulatory_stage", enums.regulatory_stage)}

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
