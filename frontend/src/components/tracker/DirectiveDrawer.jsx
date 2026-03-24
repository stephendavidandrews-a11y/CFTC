import React, { useState, useEffect } from "react";
import DrawerShell from "./DrawerShell";
import theme from "../../styles/theme";
import { createPolicyDirective, updatePolicyDirective, getPolicyDirective, getEnums, listPeople } from "../../api/tracker";

const inputStyle = {
  width: "100%", padding: "8px 12px", fontSize: 14, background: theme.bg.input,
  border: `1px solid ${theme.border.default}`, borderRadius: 6, color: theme.text.primary,
  outline: "none",
};
const labelStyle = { fontSize: 12, color: theme.text.dim, marginBottom: 4, display: "block" };
const fieldGroup = { marginBottom: 14 };

const EMPTY = {
  source_document: "", source_document_type: "", source_document_url: "",
  source_date: "", directive_label: "", directive_text: "",
  section_reference: "", chapter: "", priority_tier: "",
  responsible_entity: "", ogc_role: "", assigned_to_person_id: "",
  implementation_status: "not_started", implementation_notes: "",
  target_date: "", notes: "",
};

export default function DirectiveDrawer({ isOpen, onClose, directive, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY });
  const [enums, setEnums] = useState({});
  const [people, setPeople] = useState([]);
  const [etag, setEtag] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const isEdit = !!directive?.id;

  useEffect(() => {
    if (!isOpen) return;
    getEnums().then(setEnums).catch(() => {});
    listPeople({ limit: 500 }).then((r) => setPeople(r.items || [])).catch(() => {});
    if (directive?.id) {
      getPolicyDirective(directive.id).then((d) => {
        setForm({ ...EMPTY, ...d }); setEtag(d._etag);
      }).catch(() => {});
    } else {
      setForm({ ...EMPTY }); setEtag(null);
    }
    setError(null);
  }, [isOpen, directive?.id]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSave = async () => {
    if (!form.source_document || !form.source_document_type || !form.directive_label) {
      setError("Source document, type, and label are required"); return;
    }
    setSaving(true); setError(null);
    try {
      const payload = {};
      for (const [k, v] of Object.entries(form)) {
        if (k.startsWith("_") || k === "id" || k === "created_at" || k === "updated_at"
            || k === "assigned_to_name" || k === "linked_matters") continue;
        payload[k] = v === "" ? null : v;
      }
      if (isEdit) {
        await updatePolicyDirective(directive.id, payload, etag);
      } else {
        await createPolicyDirective(payload);
      }
      onSaved?.();
      onClose();
    } catch (err) {
      setError(err.detail || err.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={isEdit ? "Edit Directive" : "New Directive"}>
      <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
        {error && <div style={{ color: theme.accent.red, fontSize: 13, marginBottom: 12, padding: "8px 12px",
          background: "#3b1a1a", borderRadius: 6 }}>{error}</div>}

        <div style={fieldGroup}><label style={labelStyle}>Directive Label *</label>
          <input style={inputStyle} value={form.directive_label} onChange={set("directive_label")} /></div>

        <div style={fieldGroup}><label style={labelStyle}>Source Document *</label>
          <input style={inputStyle} value={form.source_document} onChange={set("source_document")} /></div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Document Type *</label>
            <select style={inputStyle} value={form.source_document_type} onChange={set("source_document_type")}>
              <option value="">Select...</option>
              {(enums.directive_source_document_type || []).map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Source Date</label>
            <input style={inputStyle} type="date" value={form.source_date || ""} onChange={set("source_date")} /></div>
        </div>

        <div style={fieldGroup}><label style={labelStyle}>Source URL</label>
          <input style={inputStyle} value={form.source_document_url || ""} onChange={set("source_document_url")} /></div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Section Reference</label>
            <input style={inputStyle} value={form.section_reference || ""} onChange={set("section_reference")} /></div>
          <div style={fieldGroup}><label style={labelStyle}>Chapter</label>
            <input style={inputStyle} value={form.chapter || ""} onChange={set("chapter")} /></div>
        </div>

        <div style={fieldGroup}><label style={labelStyle}>Directive Text</label>
          <textarea style={{ ...inputStyle, minHeight: 80 }} value={form.directive_text || ""} onChange={set("directive_text")} /></div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Priority Tier</label>
            <select style={inputStyle} value={form.priority_tier || ""} onChange={set("priority_tier")}>
              <option value="">Select...</option>
              {(enums.directive_priority_tier || []).map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Responsible Entity</label>
            <select style={inputStyle} value={form.responsible_entity || ""} onChange={set("responsible_entity")}>
              <option value="">Select...</option>
              {(enums.directive_responsible_entity || []).map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>OGC Role</label>
            <select style={inputStyle} value={form.ogc_role || ""} onChange={set("ogc_role")}>
              <option value="">Select...</option>
              {(enums.directive_ogc_role || []).map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Implementation Status</label>
            <select style={inputStyle} value={form.implementation_status || ""} onChange={set("implementation_status")}>
              {(enums.directive_implementation_status || ["not_started"]).map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
        </div>

        <div style={fieldGroup}><label style={labelStyle}>Assigned To</label>
          <select style={inputStyle} value={form.assigned_to_person_id || ""} onChange={set("assigned_to_person_id")}>
            <option value="">None</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select></div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Target Date</label>
            <input style={inputStyle} type="date" value={form.target_date || ""} onChange={set("target_date")} /></div>
          <div style={fieldGroup}><label style={labelStyle}>Completed Date</label>
            <input style={inputStyle} type="date" value={form.completed_date || ""} onChange={set("completed_date")} /></div>
        </div>

        <div style={fieldGroup}><label style={labelStyle}>Implementation Notes</label>
          <textarea style={{ ...inputStyle, minHeight: 60 }} value={form.implementation_notes || ""} onChange={set("implementation_notes")} /></div>

        <div style={fieldGroup}><label style={labelStyle}>Notes</label>
          <textarea style={{ ...inputStyle, minHeight: 40 }} value={form.notes || ""} onChange={set("notes")} /></div>
      </div>

      <div style={{ padding: "12px 20px", borderTop: `1px solid ${theme.border.default}`,
        display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button onClick={onClose} style={{ padding: "8px 18px", borderRadius: 6, fontSize: 13,
          background: theme.bg.input, color: theme.text.secondary, border: "none", cursor: "pointer" }}>Cancel</button>
        <button onClick={handleSave} disabled={saving}
          style={{ padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
            background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
            opacity: saving ? 0.6 : 1 }}>{saving ? "Saving..." : "Save"}</button>
      </div>
    </DrawerShell>
  );
}
