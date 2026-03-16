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
  name: "",
  short_name: "",
  organization_type: "",
  parent_organization_id: "",
  jurisdiction: "",
  notes: "",
};

export default function OrganizationDrawer({ isOpen, onClose, organization, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [orgs, setOrgs] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/organization_type").catch(() => []),
      fetchJSON("/tracker/organizations?limit=200").catch(() => ({ items: [] })),
    ]).then(([orgType, orgList]) => {
      setEnums({ organization_type: orgType });
      setOrgs(orgList.items || orgList || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (organization) {
      setForm({
        name: organization.name || "",
        short_name: organization.short_name || "",
        organization_type: organization.organization_type || "",
        parent_organization_id: organization.parent_organization_id || "",
        jurisdiction: organization.jurisdiction || "",
        notes: organization.notes || "",
      });
    } else {
      setForm({ ...EMPTY });
    }
    setError(null);
  }, [organization, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (!payload.name) { setError("Name is required"); setSaving(false); return; }

      if (organization?.id) {
        await fetchJSON(`/tracker/organizations/${organization.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await fetchJSON("/tracker/organizations", { method: "POST", body: JSON.stringify(payload) });
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

  const orgOpts = orgs
    .filter((o) => !organization || o.id !== organization.id)
    .map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={organization ? "Edit Organization" : "New Organization"}>
      {renderInput("Name", "name", "text", { required: true })}
      {renderInput("Short Name", "short_name")}
      {renderSelect("Organization Type", "organization_type", enums.organization_type)}
      {renderSelect("Parent Organization", "parent_organization_id", orgOpts)}
      {renderInput("Jurisdiction", "jurisdiction")}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Notes</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.notes} onChange={set("notes")} />
      </div>

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
