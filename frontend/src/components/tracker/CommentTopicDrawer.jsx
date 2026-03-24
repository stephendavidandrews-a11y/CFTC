import React, { useState, useEffect } from "react";
import DrawerShell from "./DrawerShell";
import theme from "../../styles/theme";
import { createCommentTopic, updateCommentTopic, getCommentTopic, getEnums, listPeople } from "../../api/tracker";

const inputStyle = {
  width: "100%", padding: "8px 12px", fontSize: 14, background: theme.bg.input,
  border: `1px solid ${theme.border.default}`, borderRadius: 6, color: theme.text.primary,
  outline: "none",
};
const labelStyle = { fontSize: 12, color: theme.text.dim, marginBottom: 4, display: "block" };
const fieldGroup = { marginBottom: 14 };

const EMPTY = {
  topic_label: "", topic_area: "", assigned_to_person_id: "",
  secondary_assignee_person_id: "", position_status: "open",
  position_summary: "", priority: "", due_date: "",
  deadline_type: "", source_fr_doc_number: "", source_document_type: "",
  notes: "",
};

export default function CommentTopicDrawer({ isOpen, onClose, topic, matterId, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY });
  const [enums, setEnums] = useState({});
  const [people, setPeople] = useState([]);
  const [etag, setEtag] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const isEdit = !!topic?.id;
  const resolvedMatterId = topic?.matter_id || matterId;

  useEffect(() => {
    if (!isOpen) return;
    getEnums().then(setEnums).catch(() => {});
    listPeople({ limit: 500 }).then((r) => setPeople(r.items || [])).catch(() => {});
    if (topic?.id) {
      getCommentTopic(topic.id).then((d) => {
        setForm({ ...EMPTY, ...d }); setEtag(d._etag);
      }).catch(() => {});
    } else {
      setForm({ ...EMPTY }); setEtag(null);
    }
    setError(null);
  }, [isOpen, topic?.id]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSave = async () => {
    if (!form.topic_label) { setError("Topic label is required"); return; }
    setSaving(true); setError(null);
    try {
      const payload = {};
      for (const [k, v] of Object.entries(form)) {
        if (k.startsWith("_") || k === "id" || k === "created_at" || k === "updated_at"
            || k === "assigned_to_name" || k === "secondary_assignee_name"
            || k === "matter_title" || k === "matter_number" || k === "questions") continue;
        payload[k] = v === "" ? null : v;
      }
      if (isEdit) {
        delete payload.matter_id;
        await updateCommentTopic(topic.id, payload, etag);
      } else {
        payload.matter_id = resolvedMatterId;
        await createCommentTopic(resolvedMatterId, payload);
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
    <DrawerShell isOpen={isOpen} onClose={onClose} title={isEdit ? "Edit Comment Topic" : "New Comment Topic"}>
      <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
        {error && <div style={{ color: theme.accent.red, fontSize: 13, marginBottom: 12, padding: "8px 12px",
          background: "#3b1a1a", borderRadius: 6 }}>{error}</div>}

        <div style={fieldGroup}><label style={labelStyle}>Topic Label *</label>
          <input style={inputStyle} value={form.topic_label} onChange={set("topic_label")} /></div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Topic Area</label>
            <select style={inputStyle} value={form.topic_area || ""} onChange={set("topic_area")}>
              <option value="">Select...</option>
              {(enums.comment_topic_area || []).map((v) =>
                <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Position Status</label>
            <select style={inputStyle} value={form.position_status || "open"} onChange={set("position_status")}>
              {(enums.comment_topic_position_status || ["open"]).map((v) =>
                <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Priority</label>
            <select style={inputStyle} value={form.priority || ""} onChange={set("priority")}>
              <option value="">None</option>
              {(enums.task_priority || []).map((v) =>
                <option key={v} value={v}>{v}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Due Date</label>
            <input style={inputStyle} type="date" value={form.due_date || ""} onChange={set("due_date")} /></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Assigned To</label>
            <select style={inputStyle} value={form.assigned_to_person_id || ""} onChange={set("assigned_to_person_id")}>
              <option value="">None</option>
              {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select></div>
          <div style={fieldGroup}><label style={labelStyle}>Secondary Assignee</label>
            <select style={inputStyle} value={form.secondary_assignee_person_id || ""} onChange={set("secondary_assignee_person_id")}>
              <option value="">None</option>
              {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
            </select></div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div style={fieldGroup}><label style={labelStyle}>Source FR Doc #</label>
            <input style={inputStyle} value={form.source_fr_doc_number || ""} onChange={set("source_fr_doc_number")} placeholder="e.g. 2026-05105" /></div>
          <div style={fieldGroup}><label style={labelStyle}>Source Document Type</label>
            <select style={inputStyle} value={form.source_document_type || ""} onChange={set("source_document_type")}>
              <option value="">Select...</option>
              {(enums.comment_topic_source_document_type || []).map((v) =>
                <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
            </select></div>
        </div>

        <div style={fieldGroup}><label style={labelStyle}>Position Summary</label>
          <textarea style={{ ...inputStyle, minHeight: 80 }} value={form.position_summary || ""} onChange={set("position_summary")}
            placeholder="Developing or final position text..." /></div>

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
            opacity: saving ? 0.6 : 1 }}>{saving ? "Saving..." : (topic ? "Save Changes" : "Create Topic")}</button>
      </div>
    </DrawerShell>
  );
}
