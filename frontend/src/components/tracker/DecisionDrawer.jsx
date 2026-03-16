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
  matter_id: "",
  decision_type: "",
  status: "",
  decision_assigned_to_person_id: "",
  decision_due_date: "",
  options_summary: "",
  recommended_option: "",
  decision_result: "",
  notes: "",
  made_at: "",
};

export default function DecisionDrawer({ isOpen, onClose, decision, matterId, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/decision_type").catch(() => []),
      fetchJSON("/tracker/lookups/enums/decision_status").catch(() => []),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/matters?limit=200").catch(() => ({ items: [] })),
    ]).then(([decisionType, decisionStatus, ppl, matterList]) => {
      setEnums({ decision_type: decisionType, decision_status: decisionStatus });
      setPeople(ppl.items || ppl || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (decision) {
      setForm({
        title: decision.title || "",
        matter_id: decision.matter_id || "",
        decision_type: decision.decision_type || "",
        status: decision.status || "",
        decision_assigned_to_person_id: decision.decision_assigned_to_person_id || "",
        decision_due_date: decision.decision_due_date || "",
        options_summary: decision.options_summary || "",
        recommended_option: decision.recommended_option || "",
        decision_result: decision.decision_result || "",
        notes: decision.notes || "",
        made_at: decision.made_at ? decision.made_at.slice(0, 16) : "",
      });
    } else {
      setForm({ ...EMPTY, matter_id: matterId || "" });
    }
    setError(null);
  }, [decision, matterId, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (!decision?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const missing = [];
      if (!payload.title) missing.push("Title");
      if (!payload.matter_id) missing.push("Matter");
      if (missing.length > 0) { setError("Required fields missing: " + missing.join(", ")); setSaving(false); return; }

      if (decision?.id) {
        const { matter_id, ...updatePayload } = payload;
        await fetchJSON(`/tracker/decisions/${decision.id}`, { method: "PUT", body: JSON.stringify(updatePayload) });
      } else {
        await fetchJSON("/tracker/decisions", { method: "POST", body: JSON.stringify(payload) });
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
  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || `Matter #${m.id}` }));

  const isEdit = !!decision?.id;

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={isEdit ? "Edit Decision" : "New Decision"}>
      {renderInput("Title *", "title", "text", { required: true })}
      {renderSelect("Matter *", "matter_id", matterOpts)}
      {renderSelect("Decision Type", "decision_type", enums.decision_type)}
      {renderSelect("Status", "status", enums.decision_status)}
      {renderSelect("Assigned To", "decision_assigned_to_person_id", personOpts)}
      {renderInput("Due Date", "decision_due_date", "date")}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Options Summary</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.options_summary} onChange={set("options_summary")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Recommended Option</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.recommended_option} onChange={set("recommended_option")} />
      </div>
      {isEdit && (
        <div style={{ marginBottom: 14 }}>
          <label style={LABEL_STYLE}>Decision Result</label>
          <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.decision_result} onChange={set("decision_result")} />
        </div>
      )}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Notes</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.notes} onChange={set("notes")} />
      </div>

      {form.status === "made" && renderInput("Decision Made At", "made_at", "datetime-local")}

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
