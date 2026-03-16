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
  first_name: "",
  last_name: "",
  title: "",
  organization_id: "",
  email: "",
  phone: "",
  assistant_name: "",
  assistant_contact: "",
  relationship_category: "",
  relationship_lane: "",
  working_style_notes: "",
  substantive_areas: "",
  include_in_team_workload: false,
  is_active: true,
  manager_person_id: "",
  last_interaction_date: "",
  next_interaction_needed_date: "",
  next_interaction_type: "",
  next_interaction_purpose: "",
};

export default function PersonDrawer({ isOpen, onClose, person, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [orgs, setOrgs] = React.useState([]);
  const [people, setPeople] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/relationship_category").catch(() => []),
      fetchJSON("/tracker/lookups/enums/relationship_lane").catch(() => []),
      fetchJSON("/tracker/lookups/enums/next_interaction_type").catch(() => []),
      fetchJSON("/tracker/organizations?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
    ]).then(([relCat, relLane, nextIntType, orgList, ppl]) => {
      setEnums({ relationship_category: relCat, relationship_lane: relLane, next_interaction_type: nextIntType });
      setOrgs(orgList.items || orgList || []);
      setPeople(ppl.items || ppl || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (person) {
      setForm({
        first_name: person.first_name || "",
        last_name: person.last_name || "",
        title: person.title || "",
        organization_id: person.organization_id || "",
        email: person.email || "",
        phone: person.phone || "",
        assistant_name: person.assistant_name || "",
        assistant_contact: person.assistant_contact || "",
        relationship_category: person.relationship_category || "",
        relationship_lane: person.relationship_lane || "",
        working_style_notes: person.working_style_notes || "",
        substantive_areas: person.substantive_areas || "",
        include_in_team_workload: !!person.include_in_team_workload,
        is_active: person.is_active !== undefined ? !!person.is_active : true,
        manager_person_id: person.manager_person_id || "",
        last_interaction_date: person.last_interaction_date || "",
        next_interaction_needed_date: person.next_interaction_needed_date || "",
        next_interaction_type: person.next_interaction_type || "",
        next_interaction_purpose: person.next_interaction_purpose || "",
      });
    } else {
      setForm({ ...EMPTY });
    }
    setError(null);
  }, [person, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const setCheck = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.checked }));

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => {
        if (k === "include_in_team_workload" || k === "is_active") return;
        if (payload[k] === "") payload[k] = null;
      });

      // Build full_name for the backend
      const first = payload.first_name || "";
      const last = payload.last_name || "";
      payload.full_name = `${first} ${last}`.trim() || null;

      if (!payload.full_name) { setError("Name is required"); setSaving(false); return; }

      if (person?.id) {
        await fetchJSON(`/tracker/people/${person.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await fetchJSON("/tracker/people", { method: "POST", body: JSON.stringify(payload) });
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

  const personOpts = people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}` }));
  const orgOpts = orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={person ? "Edit Person" : "New Person"}>
      {renderInput("First Name", "first_name")}
      {renderInput("Last Name", "last_name")}
      {renderInput("Title", "title")}
      {renderSelect("Organization", "organization_id", orgOpts)}
      {renderInput("Email", "email", "email")}
      {renderInput("Phone", "phone", "tel")}
      {renderInput("Assistant Name", "assistant_name")}
      {renderInput("Assistant Contact", "assistant_contact")}
      {renderSelect("Relationship Category", "relationship_category", enums.relationship_category)}
      {renderSelect("Relationship Lane", "relationship_lane", enums.relationship_lane)}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Working Style Notes</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.working_style_notes} onChange={set("working_style_notes")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Substantive Areas</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.substantive_areas} onChange={set("substantive_areas")} />
      </div>

      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={form.include_in_team_workload}
          onChange={setCheck("include_in_team_workload")}
          id="team-workload-chk"
          style={{ accentColor: "#1e40af" }}
        />
        <label htmlFor="team-workload-chk" style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", cursor: "pointer" }}>
          Include in Team Workload
        </label>
      </div>

      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={setCheck("is_active")}
          id="is-active-chk"
          style={{ accentColor: "#1e40af" }}
        />
        <label htmlFor="is-active-chk" style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", cursor: "pointer" }}>
          Active
        </label>
      </div>

      {renderSelect("Manager", "manager_person_id", personOpts)}
      {renderInput("Last Interaction", "last_interaction_date", "date")}
      {renderInput("Next Interaction Needed", "next_interaction_needed_date", "date")}
      {renderSelect("Next Interaction Type", "next_interaction_type", enums.next_interaction_type)}
      {renderInput("Next Interaction Purpose", "next_interaction_purpose")}

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
