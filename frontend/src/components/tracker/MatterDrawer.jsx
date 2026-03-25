import React from "react";
import DrawerShell from "./DrawerShell";
import {
  createMatter,
  updateMatter,
  getEnum,
  listPeople,
  listOrganizations,
  getMatter,
} from "../../api/tracker";
import { validate } from "../../utils/validation";
import theme from "../../styles/theme";

const INPUT_STYLE = {
  width: "100%", padding: "8px 12px", borderRadius: 6,
  border: `1px solid ${theme.border.default}`, background: theme.bg.input,
  color: theme.text.primary, fontSize: 13, boxSizing: "border-box",
};
const LABEL_STYLE = { display: "block", fontSize: 12, fontWeight: 600, color: theme.text.muted, marginBottom: 4 };
const SAVE_BTN = { background: theme.accent.blue, color: "#fff", padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600, border: "none", cursor: "pointer" };
const CANCEL_BTN = { background: "transparent", color: theme.text.dim, padding: "8px 20px", borderRadius: 8, fontSize: 13, border: `1px solid ${theme.border.default}`, cursor: "pointer" };

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
  cfr_citation: "",
  fr_doc_number: "",
  lead_external_org_id: "",
};

function FieldSection({ title, defaultOpen = true, children, visible = true }) {
  const [open, setOpen] = React.useState(defaultOpen);
  if (!visible) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          width: "100%", padding: "8px 0", background: "none", border: "none",
          cursor: "pointer", color: theme.text.primary, fontSize: 13,
          fontWeight: 700, letterSpacing: "0.02em", textTransform: "uppercase",
          borderBottom: `1px solid ${theme.border.default}`, marginBottom: 8,
        }}
      >
        {title}
        <span style={{ fontSize: 11, color: theme.text.dim, transition: "transform 0.15s" }}>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && <div style={{ paddingTop: 4 }}>{children}</div>}
    </div>
  );
}

export default function MatterDrawer({ isOpen, onClose, matter, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [orgs, setOrgs] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [etag, setEtag] = React.useState(null);

  // Load lookups
  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      getEnum("matter_type").catch(() => []),
      getEnum("matter_status").catch(() => []),
      getEnum("matter_priority").catch(() => []),
      getEnum("matter_sensitivity").catch(() => []),
      getEnum("boss_involvement_level").catch(() => []),
      getEnum("regulatory_stage").catch(() => []),
      getEnum("risk_level").catch(() => []),
      getEnum("unified_agenda_priority").catch(() => []),
      listPeople({ limit: 100 }).catch(() => ({ items: [] })),
      listOrganizations({ limit: 100 }).catch(() => ({ items: [] })),
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
        work_deadline: (matter.work_deadline || "").slice(0, 10),
        external_deadline: (matter.external_deadline || "").slice(0, 10),
        decision_deadline: (matter.decision_deadline || "").slice(0, 10),
        opened_date: (matter.opened_date || "").slice(0, 10),
        next_step: matter.next_step || "",
        next_step_assigned_to_person_id: matter.next_step_assigned_to_person_id || "",
        pending_decision: matter.pending_decision || "",
        revisit_date: (matter.revisit_date || "").slice(0, 10),
        outcome_summary: matter.outcome_summary || "",
        closed_at: (matter.closed_at || "").slice(0, 10),
        rin: matter.rin || "",
        regulatory_stage: matter.regulatory_stage || "",
        federal_register_citation: matter.federal_register_citation || "",
        unified_agenda_priority: matter.unified_agenda_priority || "",
        docket_number: matter.docket_number || "",
        cfr_citation: matter.cfr_citation || "",
        fr_doc_number: matter.fr_doc_number || "",
        lead_external_org_id: matter.lead_external_org_id || "",
      });
    } else {
      setEtag(null);
      setForm({ ...EMPTY });
    }
    setError(null);
    setFieldErrors({});
  }, [matter, isOpen]);

  // Fetch detail on edit to capture ETag for concurrency control
  React.useEffect(() => {
    if (matter && matter.id) {
      getMatter(matter.id).then(d => setEtag(d._etag || null)).catch(() => {});
    }
  }, [matter, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setFieldErrors({});
    setSaving(true);
    try {
      const payload = { ...form };
      // Convert empty strings to null for optional fields
      Object.keys(payload).forEach((k) => {
        if (payload[k] === "") payload[k] = null;
      });
      if (!matter?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const v = validate("matter", payload);
      if (!v.valid) { setFieldErrors(v.errors); setError(Object.values(v.errors).join(", ")); setSaving(false); return; }

      if (matter?.id) {
        await updateMatter(matter.id, payload, etag);
      } else {
        await createMatter(payload);
      }
      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      if (err.status === 409 && !err.fieldErrors) {
        setError("This record was modified by someone else. Please close, reopen to load the latest version, and review before saving again.");
        setSaving(false);
        return;
      }
      if (err.fieldErrors && Object.keys(err.fieldErrors).length) {
        setFieldErrors(err.fieldErrors);
        setError(Object.entries(err.fieldErrors).map(([k, v]) => `${k}: ${v}`).join("; "));
      } else {
        setFieldErrors({});
        setError(err.message);
      }
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
      {renderSelect("Lead External Organization", "lead_external_org_id", orgOpts)}
      {renderInput("Work Deadline", "work_deadline", "date")}
      {renderInput("External Deadline", "external_deadline", "date")}
      {renderInput("Revisit Date", "revisit_date", "date")}
      {renderInput("Decision Deadline", "decision_deadline", "date")}
      {renderInput("Opened Date", "opened_date", "date")}
      {renderInput("Next Step", "next_step")}
      {renderSelect("Next Step Owner", "next_step_assigned_to_person_id", personOpts)}
      {form.status && form.status !== "closed" && !form.next_step_assigned_to_person_id && (
        <div style={{ color: theme.accent.yellow, fontSize: 11, marginTop: -10, marginBottom: 10 }}>Consider assigning a next step owner</div>
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
      {isRulemaking && renderInput("CFR Citation", "cfr_citation")}
      {isRulemaking && renderInput("FR Document Number", "fr_doc_number")}

      {form.status === "parked / monitoring" && !form.revisit_date && (
        <div style={{ color: theme.accent.yellow, fontSize: 12, marginBottom: 10, padding: "6px 10px", background: "#422006", borderRadius: 6, border: "1px solid #854d0e" }}>Revisit date is recommended for parked/monitoring matters</div>
      )}
      {form.status === "closed" && (
        <>
          <div style={{ marginBottom: 14 }}>
            <label style={{ ...LABEL_STYLE, color: form.status === "closed" && !form.outcome_summary ? theme.accent.yellow : theme.text.muted }}>Outcome Summary *</label>
            <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical", borderColor: form.status === "closed" && !form.outcome_summary ? "#854d0e" : theme.border.default }} value={form.outcome_summary} onChange={set("outcome_summary")} placeholder="Summarize the outcome of this matter" />
          </div>
          {renderInput("Closed At", "closed_at", "date")}
        </>
      )}

      {error && <div style={{ color: theme.accent.red, fontSize: 12, marginBottom: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 16, borderTop: `1px solid ${theme.border.default}`, marginTop: 10 }}>
        <button style={CANCEL_BTN} onClick={onClose}>Cancel</button>
        <button style={{ ...SAVE_BTN, opacity: saving ? 0.6 : 1 }} onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : (matter ? "Save Changes" : "Create Matter")}
        </button>
      </div>
    </DrawerShell>
  );
}
