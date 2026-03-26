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
  status: "active",
  priority: "",
  sensitivity: "",
  assigned_to_person_id: "",
  client_organization_id: "",
  work_deadline: "",
  external_deadline: "",
  opened_date: "",
  next_step: "",
  blocker: "",
  outcome_summary: "",
  closed_at: "",
  cfr_citation: "",
  extension: {},
};

const RULEMAKING_EXT = {
  rin: "", regulatory_stage: "", workflow_status: "concept",
  cfr_citation: "", docket_number: "", fr_doc_number: "",
  federal_register_citation: "", unified_agenda_priority: "",
  interagency_role: "", is_petition: 0, petition_disposition: "", review_trigger: "",
};
const GUIDANCE_EXT = {
  instrument_type: "", workflow_status: "request_received", published_in_fr: 0,
  cftc_letter_number: "", request_date: "", requestor_name: "",
  requestor_organization_id: "", requestor_counsel: "", issuing_office_id: "",
  signatory_person_id: "", staff_contact_person_id: "", cea_provisions: "",
  cfr_provisions: "", legal_question: "", conditions_summary: "",
  amends_matter_id: "", prior_letter_number: "", issuance_date: "", expiration_date: "",
};
const ENFORCEMENT_EXT = {
  workflow_status: "intake", requesting_division_id: "", enforcement_reference: "",
  legal_issue_type: "", support_type: "", litigation_stage: "", court_or_forum: "",
  deadline_source: "", privilege_flags: "", is_confidential: 1,
};
const EXT_DEFAULTS = { rulemaking: RULEMAKING_EXT, guidance: GUIDANCE_EXT, enforcement: ENFORCEMENT_EXT };

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
      getEnum("rulemaking_workflow_status").catch(() => []),
      getEnum("guidance_workflow_status").catch(() => []),
      getEnum("enforcement_workflow_status").catch(() => []),
      getEnum("instrument_type").catch(() => []),
      getEnum("enforcement_legal_issue_type").catch(() => []),
      getEnum("enforcement_support_type").catch(() => []),
      getEnum("enforcement_litigation_stage").catch(() => []),
      getEnum("interagency_role").catch(() => []),
      getEnum("petition_disposition").catch(() => []),
      getEnum("review_trigger").catch(() => []),
      getEnum("unified_agenda_priority").catch(() => []),
      getEnum("regulatory_stage").catch(() => []),
      listPeople({ limit: 100 }).catch(() => ({ items: [] })),
      listOrganizations({ limit: 100 }).catch(() => ({ items: [] })),
    ]).then(([matterType, status, priority, sensitivity,
      rmWorkflow, gdWorkflow, enWorkflow, instrumentType,
      enLegalIssue, enSupportType, enLitStage, interagencyRole,
      petitionDisp, reviewTrigger, uaPriority, regStage,
      ppl, orgList]) => {
      setEnums({
        matter_type: matterType,
        status,
        priority,
        sensitivity,
        rulemaking_workflow_status: rmWorkflow,
        guidance_workflow_status: gdWorkflow,
        enforcement_workflow_status: enWorkflow,
        instrument_type: instrumentType,
        enforcement_legal_issue_type: enLegalIssue,
        enforcement_support_type: enSupportType,
        enforcement_litigation_stage: enLitStage,
        interagency_role: interagencyRole,
        petition_disposition: petitionDisp,
        review_trigger: reviewTrigger,
        unified_agenda_priority: uaPriority,
        regulatory_stage: regStage,
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
        status: matter.status || "",
        priority: matter.priority || "",
        sensitivity: matter.sensitivity || "",
        assigned_to_person_id: matter.assigned_to_person_id || "",
        client_organization_id: matter.client_organization_id || "",
        work_deadline: (matter.work_deadline || "").slice(0, 10),
        external_deadline: (matter.external_deadline || "").slice(0, 10),
        opened_date: (matter.opened_date || "").slice(0, 10),
        next_step: matter.next_step || "",
        blocker: matter.blocker || "",
        outcome_summary: matter.outcome_summary || "",
        closed_at: (matter.closed_at || "").slice(0, 10),
        cfr_citation: matter.cfr_citation || "",
        extension: matter.extension || {},
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

  const [extCollapsed, setExtCollapsed] = React.useState(!!matter);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const setExt = (field) => (e) => setForm((f) => ({ ...f, extension: { ...f.extension, [field]: e.target.value } }));
  const setExtCheck = (field) => (e) => setForm((f) => ({ ...f, extension: { ...f.extension, [field]: e.target.checked ? 1 : 0 } }));

  const handleTypeChange = (e) => {
    const newType = e.target.value;
    if (matter?.id) {
      if (!window.confirm("Changing matter type will remove current type-specific details. Continue?")) return;
    }
    setForm((f) => ({
      ...f,
      matter_type: newType,
      extension: !matter?.id ? (EXT_DEFAULTS[newType] ? { ...EXT_DEFAULTS[newType] } : {}) : f.extension,
    }));
  };

  const handleSave = async () => {
    setError(null);
    setFieldErrors({});
    setSaving(true);
    try {
      const { extension, ...baseFields } = form;
      const payload = { ...baseFields };
      // Convert empty strings to null for optional fields
      Object.keys(payload).forEach((k) => {
        if (payload[k] === "") payload[k] = null;
      });
      if (!matter?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }
      // Nest extension fields
      if (extension && Object.keys(extension).length > 0) {
        payload.extension = { ...extension };
      }

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

  const orgOpts = orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));
  const personOpts = people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` }));

  const extSelect = (label, field, options) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <select style={INPUT_STYLE} value={form.extension[field] || ""} onChange={setExt(field)}>
        <option value="">--</option>
        {(Array.isArray(options) ? options : []).map((v) => (
          <option key={typeof v === "object" ? v.value : v} value={typeof v === "object" ? v.value : v}>
            {typeof v === "object" ? v.label || v.value : v}
          </option>
        ))}
      </select>
    </div>
  );

  const extInput = (label, field, type = "text", extra = {}) => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <input style={INPUT_STYLE} type={type} value={form.extension[field] || ""} onChange={setExt(field)} {...extra} />
    </div>
  );

  const extTextarea = (label, field, placeholder = "") => (
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.extension[field] || ""} onChange={setExt(field)} placeholder={placeholder} />
    </div>
  );

  const extCheckbox = (label, field) => (
    <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
      <input type="checkbox" checked={!!form.extension[field]} onChange={setExtCheck(field)} />
      <label style={{ ...LABEL_STYLE, marginBottom: 0 }}>{label}</label>
    </div>
  );

  const renderExtensionFields = () => {
    if (form.matter_type === "rulemaking") {
      return (
        <>
          {extSelect("Workflow Status", "workflow_status", enums.rulemaking_workflow_status)}
          {extInput("RIN", "rin")}
          {extSelect("Regulatory Stage", "regulatory_stage", enums.regulatory_stage)}
          {extInput("CFR Citation", "cfr_citation")}
          {extInput("Docket Number", "docket_number")}
          {extInput("FR Document Number", "fr_doc_number")}
          {extInput("FR Citation", "federal_register_citation")}
          {extSelect("Unified Agenda Priority", "unified_agenda_priority", enums.unified_agenda_priority)}
          {extSelect("Interagency Role", "interagency_role", enums.interagency_role)}
          {extCheckbox("Is Petition", "is_petition")}
          {extSelect("Petition Disposition", "petition_disposition", enums.petition_disposition)}
          {extSelect("Review Trigger", "review_trigger", enums.review_trigger)}
        </>
      );
    }
    if (form.matter_type === "guidance") {
      return (
        <>
          {extSelect("Workflow Status", "workflow_status", enums.guidance_workflow_status)}
          {extSelect("Instrument Type", "instrument_type", enums.instrument_type)}
          {extCheckbox("Published in FR", "published_in_fr")}
          {extInput("CFTC Letter Number", "cftc_letter_number")}
          {extInput("Request Date", "request_date", "date")}
          {extInput("Requestor Name", "requestor_name")}
          {extSelect("Requestor Organization", "requestor_organization_id", orgOpts)}
          {extInput("Requestor Counsel", "requestor_counsel")}
          {extSelect("Issuing Office", "issuing_office_id", orgOpts)}
          {extSelect("Signatory", "signatory_person_id", personOpts)}
          {extSelect("Staff Contact", "staff_contact_person_id", personOpts)}
          {extInput("CEA Provisions", "cea_provisions")}
          {extInput("CFR Provisions", "cfr_provisions")}
          {extTextarea("Legal Question", "legal_question", "What legal question does this guidance address?")}
          {extTextarea("Conditions Summary", "conditions_summary", "Summary of conditions or limitations")}
          {extInput("Amends Matter ID", "amends_matter_id")}
          {extInput("Prior Letter Number", "prior_letter_number")}
          {extInput("Issuance Date", "issuance_date", "date")}
          {extInput("Expiration Date", "expiration_date", "date")}
        </>
      );
    }
    if (form.matter_type === "enforcement") {
      return (
        <>
          {extSelect("Workflow Status", "workflow_status", enums.enforcement_workflow_status)}
          {extSelect("Requesting Division", "requesting_division_id", orgOpts)}
          {extInput("Enforcement Reference", "enforcement_reference")}
          {extSelect("Legal Issue Type", "legal_issue_type", enums.enforcement_legal_issue_type)}
          {extSelect("Support Type", "support_type", enums.enforcement_support_type)}
          {extSelect("Litigation Stage", "litigation_stage", enums.enforcement_litigation_stage)}
          {extInput("Court or Forum", "court_or_forum")}
          {extInput("Deadline Source", "deadline_source")}
          {extInput("Privilege Flags", "privilege_flags")}
          {extCheckbox("Is Confidential", "is_confidential")}
        </>
      );
    }
    return null;
  };

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={matter ? "Edit Matter" : "New Matter"}>
      {/* Core — always visible, no section wrapper */}
      {renderInput("Title *", "title", "text", { required: true })}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Matter Type *</label>
        <select style={INPUT_STYLE} value={form.matter_type} onChange={handleTypeChange}>
          <option value="">--</option>
          {(Array.isArray(enums.matter_type) ? enums.matter_type : []).map((v) => (
            <option key={typeof v === "object" ? v.value : v} value={typeof v === "object" ? v.value : v}>
              {typeof v === "object" ? v.label || v.value : v}
            </option>
          ))}
        </select>
      </div>
      {renderSelect("Status", "status", enums.status)}
      {renderSelect("Priority", "priority", enums.priority)}
      {renderSelect("Owner", "assigned_to_person_id", personOpts)}

      {/* Workflow section */}
      <FieldSection title="Workflow" defaultOpen={true}>
        {renderInput("Next Step", "next_step")}
        <div style={{ marginBottom: 14 }}>
          <label style={LABEL_STYLE}>Blocker</label>
          <input style={INPUT_STYLE} value={form.blocker || ""} onChange={set("blocker")}
            placeholder="What's blocking progress? (leave empty if unblocked)" />
        </div>
        {renderInput("Work Deadline", "work_deadline", "date")}
        {renderInput("External Deadline", "external_deadline", "date")}
        {renderInput("Opened Date", "opened_date", "date")}
      </FieldSection>

      {/* Context section */}
      <FieldSection title="Context" defaultOpen={true}>
        <div style={{ marginBottom: 14 }}>
          <label style={LABEL_STYLE}>Description</label>
          <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.description} onChange={set("description")} />
        </div>
        {renderSelect("Sensitivity", "sensitivity", enums.sensitivity)}
      </FieldSection>

      {/* Organizations section */}
      <FieldSection title="Organizations" defaultOpen={false}>
        {renderSelect("Client Organization", "client_organization_id", orgOpts)}
      </FieldSection>

      {/* Type-specific extension section */}
      {["rulemaking", "guidance", "enforcement"].includes(form.matter_type) && (
        <div style={{ marginTop: 16, borderLeft: `3px solid ${
          form.matter_type === "rulemaking" ? "#ce93d8" :
          form.matter_type === "guidance" ? "#64b5f6" : "#ef5350"
        }`, paddingLeft: 16 }}>
          <div onClick={() => setExtCollapsed(!extCollapsed)}
            style={{ cursor: "pointer", fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
            <span>{extCollapsed ? "\u25b8" : "\u25be"}</span>
            <span>{form.matter_type === "rulemaking" ? "Rulemaking" : form.matter_type === "guidance" ? "Guidance" : "Enforcement"} Details</span>
          </div>
          {!extCollapsed && renderExtensionFields()}
        </div>
      )}

      {/* Closed fields */}
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
