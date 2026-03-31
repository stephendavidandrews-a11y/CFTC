/**
 * Bundle review sub-components extracted from BundleReviewDetailPage.
 *
 * Contains: FIELD_SCHEMAS, SchemaField, useReviewLookups,
 * EditItemModal, AddItemModal, CreateBundleModal, MergeBundlesModal,
 * CountBox, CollapsiblePanel, SuppressionSection, MetaField
 */

import React, { useState, useEffect } from "react";
import theme from "../../styles/theme";
import Modal from "../shared/Modal";
import { listPeople, listOrganizations, listMatters } from "../../api/tracker";

function formatLabel(str) {
  if (!str) return "";
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export const FIELD_SCHEMAS = {
  task: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "status", label: "Status", type: "select", required: true, options: ["not started", "in progress", "waiting on others", "needs review", "done", "deferred"], defaultValue: "not started" },
    { key: "task_mode", label: "Task Mode", type: "select", required: true, options: ["action", "follow_up", "monitoring"] },
    { key: "task_type", label: "Task Type", type: "select", options: ["research issue", "draft memo", "review markup", "prepare talking points", "schedule meeting", "get clearance", "follow up with client", "redline document", "produce options memo", "send readout", "coordinate with agency partner", "other"] },
    { key: "priority", label: "Priority", type: "select", options: ["critical", "high", "normal", "low"], defaultValue: "normal" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "delegated_by_person_id", label: "Delegated By", type: "person_picker" },
    { key: "supervising_person_id", label: "Supervisor", type: "person_picker" },
    { key: "waiting_on_person_id", label: "Waiting On (Person)", type: "person_picker" },
    { key: "waiting_on_org_id", label: "Waiting On (Org)", type: "org_picker" },
    { key: "waiting_on_description", label: "Waiting On Description", type: "text" },
    { key: "trigger_description", label: "Trigger Description", type: "text" },
    { key: "expected_output", label: "Expected Output", type: "text" },
    { key: "due_date", label: "Due Date", type: "date" },
    { key: "deadline_type", label: "Deadline Type", type: "select", options: ["hard", "soft", "internal"] },
    { key: "next_follow_up_date", label: "Next Follow-up Date", type: "date" },
    { key: "description", label: "Description", type: "textarea" },
  ],
  task_update: [
    { key: "existing_task_id", label: "Task ID", type: "text", required: true },
    { key: "existing_task_title", label: "Task Title", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  decision: [
    { key: "title", label: "Title (framed as question/choice)", type: "text", required: true },
    { key: "status", label: "Status", type: "select", required: true, options: ["pending", "under consideration", "made", "deferred", "no longer needed"] },
    { key: "decision_type", label: "Decision Type", type: "select", options: ["policy", "legal", "resource", "timing", "personnel", "procedural"] },
    { key: "decision_assigned_to_person_id", label: "Decision Maker", type: "person_picker" },
    { key: "decision_due_date", label: "Decision Due Date", type: "date" },
    { key: "options_summary", label: "Options Summary", type: "textarea" },
    { key: "recommended_option", label: "Recommended Option", type: "text" },
    { key: "decision_result", label: "Decision Result", type: "text" },
    { key: "made_at", label: "Made At", type: "date" },
    { key: "notes", label: "Notes", type: "textarea" },
  ],
  decision_update: [
    { key: "existing_decision_id", label: "Decision ID", type: "text", required: true },
    { key: "existing_decision_title", label: "Decision Title", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  meeting_record: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "date_time_start", label: "Start Time", type: "date", required: true },
    { key: "date_time_end", label: "End Time", type: "date" },
    { key: "meeting_type", label: "Meeting Type", type: "select", options: ["internal working meeting", "leadership meeting", "client meeting", "interagency meeting", "industry meeting", "Hill meeting", "briefing", "check-in", "commissioner office", "other"] },
    { key: "purpose", label: "Purpose", type: "text" },
    { key: "readout_summary", label: "Readout Summary", type: "textarea" },
    { key: "boss_attends", label: "Boss Attends", type: "boolean" },
    { key: "external_parties_attend", label: "External Parties Attend", type: "boolean" },
    { key: "participants", label: "Participants", type: "participants" },
    { key: "matter_links", label: "Matter Links (JSON)", type: "json" },
  ],
  matter_update: [
    { key: "summary", label: "Summary", type: "textarea", required: true },
    { key: "update_type", label: "Update Type", type: "select", required: true, options: ["status update", "meeting readout", "document milestone", "decision made", "blocker identified", "deadline changed", "escalation", "closure note"] },
  ],
  status_change: [
    { key: "field", label: "Field to Change", type: "select", required: true, options: ["status", "priority", "sensitivity", "next_step", "blocker"] },
    { key: "old_value", label: "Old Value", type: "text" },
    { key: "new_value", label: "New Value", type: "text", required: true },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  stakeholder_addition: [
    { key: "person_id", label: "Person", type: "person_picker" },
    { key: "organization_id", label: "Organization", type: "org_picker" },
    { key: "role", label: "Role", type: "select", required: true, options: ["lead attorney", "supervisor", "requesting stakeholder", "substantive client", "reviewing stakeholder", "leadership stakeholder", "external partner", "Hill stakeholder", "outside party", "subject matter contributor", "FYI only", "requesting office", "client office", "reviewing office", "lead office", "partner agency", "counterparty", "Hill office", "affected office"] },
    { key: "engagement_level", label: "Engagement Level", type: "select", options: ["lead", "core", "consulted", "informed", "escalation only"] },
    { key: "rationale_detail", label: "Rationale", type: "text" },
  ],
  document: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "document_type", label: "Document Type", type: "select", required: true, options: ["rulemaking_text", "legal_memo", "options_memo", "comment_letter", "testimony", "talking_points", "briefing_paper", "correspondence", "report", "no_action_letter", "other"] },
    { key: "status", label: "Status", type: "select", options: ["not started", "drafting", "internal_review", "client_review", "leadership_review", "clearance", "final", "sent", "archived"], defaultValue: "not started" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "due_date", label: "Due Date", type: "date" },
    { key: "summary", label: "Summary", type: "textarea" },
  ],
  context_note: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "category", label: "Category", type: "select", required: true, options: ["people_insight", "institutional_knowledge", "process_note", "policy_operating_rule", "strategic_context", "culture_climate", "relationship_dynamic"] },
    { key: "body", label: "Body", type: "textarea", required: true },
    { key: "posture", label: "Posture", type: "select", required: true, options: ["factual", "attributed_view", "tentative", "interpretive", "sensitive"] },
    { key: "speaker_attribution", label: "Speaker Attribution", type: "text" },
    { key: "durability", label: "Durability", type: "select", options: ["ephemeral", "medium_term", "durable"], defaultValue: "durable" },
    { key: "sensitivity", label: "Sensitivity", type: "select", options: ["low", "moderate", "high"], defaultValue: "low" },
    { key: "effective_date", label: "Effective Date", type: "date" },
    { key: "stale_after", label: "Stale After", type: "date" },
    { key: "linked_entities", label: "Linked Entities (JSON)", type: "json" },
  ],
  person_detail_update: [
    { key: "person_id", label: "Person", type: "person_picker", required: true },
    { key: "person_name", label: "Person Name", type: "text", required: true },
    { key: "fields", label: "Profile Fields (JSON)", type: "json", required: true, hint: '{"education_summary":"...","prior_roles_summary":"...","email":"..."}' },
  ],
  new_person: [
    { key: "full_name", label: "Full Name", type: "text", required: true },
    { key: "title", label: "Title / Role", type: "text" },
    { key: "organization_name", label: "Organization", type: "text" },
    { key: "relationship_category", label: "Relationship Category", type: "select", options: ["Boss", "Leadership", "Direct report", "Indirect report", "OGC peer", "Internal client", "Commissioner office", "Partner agency", "Hill", "Outside party"] },
    { key: "substantive_areas", label: "Substantive Areas", type: "text" },
    { key: "context", label: "Context", type: "textarea" },
  ],
  new_organization: [
    { key: "name", label: "Name", type: "text", required: true },
    { key: "organization_type", label: "Organization Type", type: "select", options: ["CFTC office", "CFTC division", "Commissioner office", "Federal agency", "White House / OMB", "Congressional office", "Regulated entity", "Exchange", "Clearinghouse", "Trade association", "Outside counsel", "Inspector General / auditor", "Other"] },
    { key: "parent_name", label: "Parent Organization", type: "text" },
    { key: "jurisdiction", label: "Jurisdiction", type: "text" },
    { key: "context", label: "Context", type: "textarea" },
  ],
  org_detail_update: [
    { key: "existing_org_id", label: "Organization", type: "org_picker", required: true },
    { key: "existing_org_name", label: "Organization Name", type: "text", required: true },
    { key: "changes", label: "Changes (JSON)", type: "json", required: true, hint: '{"jurisdiction":"..."}' },
    { key: "change_summary", label: "Change Summary", type: "textarea", required: true },
  ],
  directive_update: [
    { key: "directive_id", label: "Directive ID", type: "text", required: true },
    { key: "directive_label", label: "Directive", type: "text", required: true },
    { key: "changes", label: "Proposed Changes (JSON)", type: "json", required: true },
    { key: "add_matter_links", label: "New Matter Links (JSON)", type: "json" },
    { key: "rationale", label: "Rationale", type: "textarea" },
  ],
  new_matter: [
    { key: "title", label: "Title", type: "text", required: true },
    { key: "matter_type", label: "Matter Type", type: "select", required: true, options: ["rulemaking", "guidance", "enforcement", "congressional", "policy", "briefing", "administrative", "inquiry", "other"] },
    { key: "status", label: "Status", type: "select", options: ["active", "paused", "closed"], defaultValue: "active" },
    { key: "priority", label: "Priority", type: "select", required: true, options: ["critical this week", "important this month", "strategic / slow burn", "monitoring only"] },
    { key: "sensitivity", label: "Sensitivity", type: "select", required: true, options: ["routine", "internal only", "leadership-sensitive", "deliberative / predecisional", "enforcement-sensitive", "congressional-sensitive"] },
    { key: "next_step", label: "Next Step", type: "text", required: true },
    { key: "description", label: "Description", type: "textarea" },
    { key: "assigned_to_person_id", label: "Assigned To", type: "person_picker" },
    { key: "requesting_organization_id", label: "Requesting Organization", type: "org_picker" },
    { key: "regulatory_stage", label: "Regulatory Stage", type: "select", options: ["concept", "drafting", "proposed", "comment_period", "final_review", "published", "effective", "withdrawn", "long_term", "petition_received", "interpretive_release"] },
    { key: "rin", label: "RIN", type: "text" },
    { key: "docket_number", label: "Docket Number", type: "text" },
    { key: "cfr_citation", label: "CFR Citation", type: "text" },
  ],
};

export const ITEM_TYPES = Object.keys(FIELD_SCHEMAS);

export const INPUT_STYLE = {
  width: "100%", background: theme.bg.input, color: theme.text.secondary,
  border: `1px solid ${theme.border.default}`, borderRadius: 6,
  padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
};

// ── Schema Field Renderer ──────────────────────────────────────────────────

export function SchemaField({ field, value, onChange, people, orgs, matters }) {
  const label = (
    <label style={{
      display: "block", fontSize: 11, fontWeight: 600,
      color: theme.text.faint, marginBottom: 4,
    }}>
      {field.label}{field.required ? <span style={{ color: theme.accent.red }}> *</span> : ""}
    </label>
  );

  const wrap = (input) => (
    <div style={{ marginBottom: 14 }}>
      {label}
      {input}
      {field.hint && <div style={{ fontSize: 10, color: theme.text.dim, marginTop: 2 }}>e.g. {field.hint}</div>}
    </div>
  );

  switch (field.type) {
    case "select":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">--</option>
          {(field.options || []).map((o) => (
            <option key={o} value={o}>{formatLabel(o)}</option>
          ))}
        </select>
      );

    case "person_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select person --</option>
          {(people || []).map((p) => (
            <option key={p.id} value={p.id}>{p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.id}</option>
          ))}
        </select>
      );

    case "org_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select organization --</option>
          {(orgs || []).map((o) => (
            <option key={o.id} value={o.id}>{o.name || o.id}</option>
          ))}
        </select>
      );

    case "matter_picker":
      return wrap(
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} style={INPUT_STYLE}>
          <option value="">-- Select matter --</option>
          {(matters || []).map((m) => (
            <option key={m.id} value={m.id}>{m.title || m.id}</option>
          ))}
        </select>
      );

    case "date":
      return wrap(
        <input type="date" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE} />
      );

    case "boolean":
      return (
        <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={!!value}
            onChange={(e) => onChange(e.target.checked ? 1 : 0)}
            style={{ width: 16, height: 16, accentColor: theme.accent.blue }} />
          <label style={{ fontSize: 12, color: theme.text.secondary }}>{field.label}</label>
        </div>
      );

    case "textarea":
      return wrap(
        <textarea value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          rows={3} style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.family, resize: "vertical" }} />
      );

    case "participants": {
      const MEETING_ROLES = ["chair", "presenter", "attendee", "decision-maker", "note-taker", "guest"];
      const parts = Array.isArray(value) ? value : [];
      const updatePart = (idx, key, val) => {
        const updated = parts.map((p, i) => i === idx ? { ...p, [key]: val } : p);
        onChange(updated);
      };
      const addPart = () => onChange([...parts, { person_id: "", meeting_role: "attendee", attended: true, key_contribution_summary: "", stance_summary: "", follow_up_expected: false }]);
      const removePart = (idx) => onChange(parts.filter((_, i) => i !== idx));
      const personName = (pid) => {
        const p = (people || []).find((x) => x.id === pid);
        return p ? (p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || pid) : pid;
      };

      return (
        <div style={{ marginBottom: 14 }}>
          {label}
          {parts.map((p, idx) => (
            <div key={idx} style={{
              background: theme.bg.input, border: `1px solid ${theme.border.subtle}`,
              borderRadius: 6, padding: "10px 12px", marginBottom: 6,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint }}>Participant {idx + 1}</span>
                <button onClick={() => removePart(idx)} style={{ ...btnBase, padding: "2px 8px", fontSize: 10, background: "transparent", color: theme.accent.red, border: `1px solid ${theme.accent.red}` }}>Remove</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Person</div>
                  <select value={p.person_id || ""} onChange={(e) => updatePart(idx, "person_id", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }}>
                    <option value="">--</option>
                    {(people || []).map((pp) => <option key={pp.id} value={pp.id}>{pp.full_name || `${pp.first_name || ""} ${pp.last_name || ""}`.trim() || pp.id}</option>)}
                  </select>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Role</div>
                  <select value={p.meeting_role || ""} onChange={(e) => updatePart(idx, "meeting_role", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }}>
                    <option value="">--</option>
                    {MEETING_ROLES.map((r) => <option key={r} value={r}>{formatLabel(r)}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={!!p.attended} onChange={(e) => updatePart(idx, "attended", e.target.checked)} style={{ width: 14, height: 14 }} />
                  <span style={{ fontSize: 11, color: theme.text.secondary }}>Attended</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={!!p.follow_up_expected} onChange={(e) => updatePart(idx, "follow_up_expected", e.target.checked)} style={{ width: 14, height: 14 }} />
                  <span style={{ fontSize: 11, color: theme.text.secondary }}>Follow-up expected</span>
                </div>
              </div>
              <div style={{ marginBottom: 4 }}>
                <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Key Contribution</div>
                <input type="text" value={p.key_contribution_summary || ""} onChange={(e) => updatePart(idx, "key_contribution_summary", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: theme.text.dim, marginBottom: 2 }}>Stance</div>
                <input type="text" value={p.stance_summary || ""} onChange={(e) => updatePart(idx, "stance_summary", e.target.value)} style={{ ...INPUT_STYLE, fontSize: 12, padding: "6px 8px" }} />
              </div>
            </div>
          ))}
          <button onClick={addPart} style={{ ...btnBase, background: "transparent", color: theme.text.dim, border: `1px dashed ${theme.border.default}`, width: "100%", padding: "8px" }}>
            + Add Participant
          </button>
        </div>
      );
    }

    case "json":
      return wrap(
        <textarea
          value={typeof value === "object" && value !== null ? JSON.stringify(value, null, 2) : (value ?? "")}
          onChange={(e) => {
            try { onChange(JSON.parse(e.target.value)); }
            catch { onChange(e.target.value); }
          }}
          rows={4}
          style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.mono, resize: "vertical" }}
        />
      );

    default: // text
      return wrap(
        <input type="text" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
          style={INPUT_STYLE} />
      );
  }
}

// ── Lookup data hook ───────────────────────────────────────────────────────

export function useReviewLookups(isOpen) {
  const [people, setPeople] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [matters, setMatters] = useState([]);

  useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      listPeople({ limit: 200 }).catch(() => ({ items: [] })),
      listOrganizations({ limit: 200 }).catch(() => ({ items: [] })),
      listMatters({ limit: 200 }).catch(() => ({ items: [] })),
    ]).then(([ppl, orgList, matterList]) => {
      setPeople(ppl.items || ppl || []);
      setOrgs(orgList.items || orgList || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  return { people, orgs, matters };
}

// ── Edit Item Modal ─────────────────────────────────────────────────────────

export function EditItemModal({ isOpen, onClose, item, busy, onSave }) {
  const [fields, setFields] = useState({});
  const { people, orgs, matters } = useReviewLookups(isOpen);

  useEffect(() => {
    if (item?.proposed_data) {
      setFields({ ...item.proposed_data });
    }
  }, [item]);

  if (!isOpen || !item) return null;

  const schema = FIELD_SCHEMAS[item.item_type] || [];
  const schemaKeys = new Set(schema.map((f) => f.key));

  const handleFieldChange = (key, val) => {
    setFields((f) => ({ ...f, [key]: val }));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit ${formatLabel(item.item_type)}`} width={560}>
      <div style={{ maxHeight: "60vh", overflowY: "auto", paddingRight: 8 }}>
        {/* Schema-defined fields first */}
        {schema.map((field) => (
          <SchemaField
            key={field.key}
            field={field}
            value={fields[field.key]}
            onChange={(val) => handleFieldChange(field.key, val)}
            people={people} orgs={orgs} matters={matters}
          />
        ))}

        {/* Extra fields in proposed_data not in schema (backward compat) */}
        {Object.entries(fields)
          .filter(([key]) => !schemaKeys.has(key))
          .map(([key, val]) => (
            <div key={key} style={{ marginBottom: 14 }}>
              <label style={{
                display: "block", fontSize: 11, fontWeight: 600,
                color: theme.text.dim, marginBottom: 4, fontStyle: "italic",
              }}>
                {key.replace(/_/g, " ")} (extra)
              </label>
              {typeof val === "object" && val !== null ? (
                <textarea
                  value={JSON.stringify(val, null, 2)}
                  onChange={(e) => {
                    try { handleFieldChange(key, JSON.parse(e.target.value)); }
                    catch { handleFieldChange(key, e.target.value); }
                  }}
                  rows={3}
                  style={{ ...INPUT_STYLE, fontSize: 12, fontFamily: theme.font.mono, resize: "vertical" }}
                />
              ) : (
                <input type="text" value={val ?? ""}
                  onChange={(e) => handleFieldChange(key, e.target.value)}
                  style={INPUT_STYLE} />
              )}
            </div>
          ))}
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
        <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
          Cancel
        </button>
        <button
          disabled={busy}
          onClick={() => onSave(fields)}
          style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
        >
          {busy ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </Modal>
  );
}

// ── Add Item Modal ──────────────────────────────────────────────────────────

export function AddItemModal({ isOpen, onClose, busy, onSave }) {
  const [itemType, setItemType] = useState("task");
  const [fields, setFields] = useState({});
  const { people, orgs, matters } = useReviewLookups(isOpen);

  useEffect(() => {
    // Build initial values from schema
    const schema = FIELD_SCHEMAS[itemType] || [];
    const initial = {};
    schema.forEach((f) => {
      if (f.defaultValue !== undefined) initial[f.key] = f.defaultValue;
      else if (f.type === "json") initial[f.key] = {};
      else if (f.type === "boolean") initial[f.key] = 0;
      else initial[f.key] = "";
    });
    setFields(initial);
  }, [itemType]);

  if (!isOpen) return null;

  const schema = FIELD_SCHEMAS[itemType] || [];

  const handleFieldChange = (key, val) => {
    setFields((f) => ({ ...f, [key]: val }));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Item" width={560}>
      <div>
        <div style={{ marginBottom: 14 }}>
          <label style={{
            display: "block", fontSize: 11, fontWeight: 600,
            color: theme.text.faint, marginBottom: 4,
          }}>
            Item Type
          </label>
          <select
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
            style={INPUT_STYLE}
          >
            {ITEM_TYPES.map((t) => (
              <option key={t} value={t}>{formatLabel(t)}</option>
            ))}
          </select>
        </div>

        <div style={{ maxHeight: "60vh", overflowY: "auto", paddingRight: 8 }}>
          {schema.map((field) => (
            <SchemaField
              key={field.key}
              field={field}
              value={fields[field.key]}
              onChange={(val) => handleFieldChange(field.key, val)}
              people={people} orgs={orgs} matters={matters}
            />
          ))}
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={busy}
            onClick={() => onSave(itemType, fields)}
            style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
          >
            {busy ? "Adding..." : "Add Item"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Create Bundle Modal ─────────────────────────────────────────────────────

export function CreateBundleModal({ isOpen, onClose, busy, onSave }) {
  const [bundleType, setBundleType] = useState("standalone");
  const [matterTitle, setMatterTitle] = useState("");
  const [rationale, setRationale] = useState("");
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Bundle" width={480}>
      <div>
        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Bundle Type
          </label>
          <select
            value={bundleType}
            onChange={(e) => setBundleType(e.target.value)}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          >
            <option value="standalone">Standalone</option>
            <option value="existing_matter">Existing Matter</option>
            <option value="new_matter">New Matter</option>
          </select>
        </div>

        {(bundleType === "existing_matter" || bundleType === "new_matter") && (
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
              Matter Title
            </label>
            <input
              type="text"
              value={matterTitle}
              onChange={(e) => setMatterTitle(e.target.value)}
              placeholder="Enter matter title..."
              style={{
                width: "100%", background: theme.bg.input, color: theme.text.secondary,
                border: `1px solid ${theme.border.default}`, borderRadius: 6,
                padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              }}
            />
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Rationale
          </label>
          <input
            type="text"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            placeholder="Why create this bundle?"
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Intelligence Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              resize: "vertical",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={busy}
            onClick={() => onSave({
              bundleType,
              targetMatterTitle: matterTitle || null,
              rationale: rationale || "Reviewer-created bundle",
              intelligenceNotes: notes || null,
            })}
            style={{ ...btnBase, background: "#1e40af", color: "#fff", opacity: busy ? 0.5 : 1 }}
          >
            {busy ? "Creating..." : "Create Bundle"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Merge Bundles Modal ─────────────────────────────────────────────────────

export function MergeBundlesModal({ isOpen, onClose, bundles, sourceId, busy, onMerge }) {
  const [source, setSource] = useState(sourceId || "");
  const [target, setTarget] = useState("");

  useEffect(() => {
    if (sourceId) setSource(sourceId);
  }, [sourceId]);

  if (!isOpen) return null;

  const availableTargets = bundles.filter((b) => b.id !== source);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Merge Bundles" width={480}>
      <div>
        <p style={{ fontSize: 13, color: theme.text.muted, margin: "0 0 16px", lineHeight: 1.5 }}>
          All items from the source bundle will be moved into the target bundle. The source bundle will be removed.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Source Bundle (will be removed)
          </label>
          <select
            value={source}
            onChange={(e) => { setSource(e.target.value); setTarget(""); }}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
            }}
          >
            <option value="">Select source...</option>
            {bundles.map((b) => (
              <option key={b.id} value={b.id}>
                {b.target_matter_title || formatLabel(b.bundle_type)} ({b.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: theme.text.faint, marginBottom: 4 }}>
            Target Bundle (will receive items)
          </label>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={!source}
            style={{
              width: "100%", background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, borderRadius: 6,
              padding: "8px 10px", fontSize: 13, fontFamily: theme.font.family,
              opacity: source ? 1 : 0.5,
            }}
          >
            <option value="">Select target...</option>
            {availableTargets.map((b) => (
              <option key={b.id} value={b.id}>
                {b.target_matter_title || formatLabel(b.bundle_type)} ({b.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: theme.bg.input, color: theme.text.muted, border: `1px solid ${theme.border.default}` }}>
            Cancel
          </button>
          <button
            disabled={!source || !target || busy}
            onClick={() => onMerge(source, target)}
            style={{
              ...btnBase, background: "#1e40af", color: "#fff",
              opacity: (!source || !target || busy) ? 0.5 : 1,
              cursor: (!source || !target) ? "not-allowed" : "pointer",
            }}
          >
            {busy ? "Merging..." : "Merge Bundles"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Shared sub-components ───────────────────────────────────────────────────

export function CountBox({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || theme.text.primary, fontFamily: theme.font.mono }}>
        {value}
      </div>
    </div>
  );
}

export function CollapsiblePanel({ title, open, onToggle, children }) {
  return (
    <div style={{
      background: theme.bg.card, borderRadius: theme.card.radius,
      border: `1px solid ${theme.border.default}`, marginTop: 12,
      overflow: "hidden",
    }}>
      <button
        onClick={onToggle}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          width: "100%", padding: "12px 20px", background: "transparent",
          border: "none", cursor: "pointer", color: theme.text.muted,
          fontSize: 13, fontWeight: 600, fontFamily: theme.font.family,
          borderBottom: open ? `1px solid ${theme.border.subtle}` : "none",
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: 10, color: theme.text.faint }}>{open ? "\u25b2" : "\u25bc"}</span>
      </button>
      {open && (
        <div style={{ padding: "14px 20px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

export function SuppressionSection({ title, items }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: theme.text.faint,
        textTransform: "uppercase", marginBottom: 6,
      }}>
        {title} ({items.length})
      </div>
      {items.map((item, i) => (
        <div key={i} style={{
          fontSize: 12, color: theme.text.dim, padding: "5px 0",
          borderBottom: i < items.length - 1 ? `1px solid ${theme.border.subtle}` : "none",
          lineHeight: 1.4,
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

export function MetaField({ label, value, mono }) {
  return (
    <div>
      <div style={{
        fontSize: 10, fontWeight: 700, color: theme.text.faint,
        textTransform: "uppercase", marginBottom: 2,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 12, color: theme.text.secondary,
        fontFamily: mono ? theme.font.mono : theme.font.family,
        wordBreak: "break-all",
      }}>
        {value || "\u2014"}
      </div>
    </div>
  );
}
