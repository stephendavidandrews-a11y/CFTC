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
  description: "",
  status: "",
  task_mode: "",
  task_type: "",
  priority: "",
  assigned_to_person_id: "",
  due_date: "",
  deadline_type: "",
  matter_id: "",
  waiting_on_person_id: "",
  waiting_on_org_id: "",
};

export default function TaskDrawer({ isOpen, onClose, task, matterId, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [orgs, setOrgs] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/task_status").catch(() => []),
      fetchJSON("/tracker/lookups/enums/task_mode").catch(() => []),
      fetchJSON("/tracker/lookups/enums/task_type").catch(() => []),
      fetchJSON("/tracker/lookups/enums/priority").catch(() => []),
      fetchJSON("/tracker/lookups/enums/deadline_type").catch(() => []),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/organizations?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/matters?limit=200").catch(() => ({ items: [] })),
    ]).then(([status, mode, type, priority, deadlineType, ppl, orgList, matterList]) => {
      setEnums({ status, task_mode: mode, task_type: type, priority, deadline_type: deadlineType });
      setPeople(ppl.items || ppl || []);
      setOrgs(orgList.items || orgList || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (task) {
      setForm({
        title: task.title || "",
        description: task.description || "",
        status: task.status || "",
        task_mode: task.task_mode || "",
        task_type: task.task_type || "",
        priority: task.priority || "",
        assigned_to_person_id: task.assigned_to_person_id || "",
        due_date: task.due_date || "",
        deadline_type: task.deadline_type || "",
        matter_id: task.matter_id || "",
        waiting_on_person_id: task.waiting_on_person_id || "",
        waiting_on_org_id: task.waiting_on_org_id || "",
      });
    } else {
      setForm({ ...EMPTY, matter_id: matterId || "" });
    }
    setError(null);
  }, [task, matterId, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (!payload.title) { setError("Title is required"); setSaving(false); return; }

      if (task?.id) {
        await fetchJSON(`/tracker/tasks/${task.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await fetchJSON("/tracker/tasks", { method: "POST", body: JSON.stringify(payload) });
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

  const personOpts = people.map((p) => ({ value: p.id, label: `${p.first_name || ""} ${p.last_name || ""}`.trim() || `Person #${p.id}` }));
  const orgOpts = orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));
  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || `Matter #${m.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={task ? "Edit Task" : "New Task"}>
      {renderInput("Title", "title", "text", { required: true })}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Description</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.description} onChange={set("description")} />
      </div>
      {renderSelect("Status", "status", enums.status)}
      {renderSelect("Task Mode", "task_mode", enums.task_mode)}
      {renderSelect("Task Type", "task_type", enums.task_type)}
      {renderSelect("Priority", "priority", enums.priority)}
      {renderSelect("Assigned To", "assigned_to_person_id", personOpts)}
      {renderInput("Due Date", "due_date", "date")}
      {renderSelect("Deadline Type", "deadline_type", enums.deadline_type)}
      {renderSelect("Matter", "matter_id", matterOpts)}
      {renderSelect("Waiting On Person", "waiting_on_person_id", personOpts)}
      {renderSelect("Waiting On Org", "waiting_on_org_id", orgOpts)}

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
