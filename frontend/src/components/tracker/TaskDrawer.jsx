import React from "react";
import DrawerShell from "./DrawerShell";
import {
  createTask,
  updateTask,
  getEnum,
  listPeople,
  listOrganizations,
  listMatters,
  getTask,
} from "../../api/tracker";
import { validate } from "../../utils/validation";

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
  expected_output: "",
  completion_notes: "",
  next_follow_up_date: "",
  delegated_by_person_id: "",
  supervising_person_id: "",
  tracks_task_id: "",
  trigger_description: "",
};

export default function TaskDrawer({ isOpen, onClose, task, matterId, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [orgs, setOrgs] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [fieldErrors, setFieldErrors] = React.useState({});
  const [etag, setEtag] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      getEnum("task_status").catch(() => []),
      getEnum("task_mode").catch(() => []),
      getEnum("task_type").catch(() => []),
      getEnum("task_priority").catch(() => []),
      getEnum("deadline_type").catch(() => []),
      listPeople({ limit: 100 }).catch(() => ({ items: [] })),
      listOrganizations({ limit: 100 }).catch(() => ({ items: [] })),
      listMatters({ limit: 200 }).catch(() => ({ items: [] })),
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
        expected_output: task.expected_output || "",
        completion_notes: task.completion_notes || "",
        next_follow_up_date: task.next_follow_up_date || "",
        delegated_by_person_id: task.delegated_by_person_id || "",
        supervising_person_id: task.supervising_person_id || "",
        tracks_task_id: task.tracks_task_id || "",
        trigger_description: task.trigger_description || "",
      });
    } else {
      setEtag(null);
      setForm({ ...EMPTY, matter_id: matterId || "" });
    }
    setError(null);
    setFieldErrors({});
  }, [task, matterId, isOpen]);

  // Fetch full detail on edit to prevent data loss and capture ETag
  React.useEffect(() => {
    if (task && task.id) {
      getTask(task.id).then(d => {
        setEtag(d._etag || null);
        setForm({
          title: d.title || "",
          description: d.description || "",
          status: d.status || "",
          task_mode: d.task_mode || "",
          task_type: d.task_type || "",
          priority: d.priority || "",
          assigned_to_person_id: d.assigned_to_person_id || "",
          due_date: (d.due_date || "").slice(0, 10),
          deadline_type: d.deadline_type || "",
          matter_id: d.matter_id || "",
          waiting_on_person_id: d.waiting_on_person_id || "",
          waiting_on_org_id: d.waiting_on_org_id || "",
          expected_output: d.expected_output || "",
          completion_notes: d.completion_notes || "",
          next_follow_up_date: (d.next_follow_up_date || "").slice(0, 10),
          delegated_by_person_id: d.delegated_by_person_id || "",
          supervising_person_id: d.supervising_person_id || "",
          tracks_task_id: d.tracks_task_id || "",
          trigger_description: d.trigger_description || "",
        });
      }).catch(() => {});
    }
  }, [task, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSave = async () => {
    setError(null);
    setFieldErrors({});
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (!task?.id) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const v = validate("task", payload);
      if (!v.valid) { setFieldErrors(v.errors); setError(Object.values(v.errors).join(", ")); setSaving(false); return; }

      if (task?.id) {
        await updateTask(task.id, payload, etag);
      } else {
        await createTask(payload);
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

  const personOpts = people.map((p) => ({ value: p.id, label: p.full_name || (`${p.first_name || ""} ${p.last_name || ""}`.trim()) || `Person #${p.id}` }));
  const orgOpts = orgs.map((o) => ({ value: o.id, label: o.name || `Org #${o.id}` }));
  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || `Matter #${m.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={task ? "Edit Task" : "New Task"}>
      {renderInput("Title *", "title", "text", { required: true })}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Description</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.description} onChange={set("description")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Expected Output</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.expected_output} onChange={set("expected_output")} placeholder="What deliverable or result is expected?" />
      </div>
      {form.status === "done" && (
        <div style={{ marginBottom: 14 }}>
          <label style={LABEL_STYLE}>Completion Notes</label>
          <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.completion_notes} onChange={set("completion_notes")} />
        </div>
      )}
      {renderSelect("Status", "status", enums.status)}
      {renderSelect("Task Mode", "task_mode", enums.task_mode)}
      {renderSelect("Task Type", "task_type", enums.task_type)}
      {renderSelect("Priority", "priority", enums.priority)}
      {renderSelect("Assigned To", "assigned_to_person_id", personOpts)}
      {renderInput("Due Date", "due_date", "date")}
      {renderInput("Next Follow-Up Date", "next_follow_up_date", "date")}
      {renderSelect("Deadline Type", "deadline_type", enums.deadline_type)}
      {renderSelect("Matter", "matter_id", matterOpts)}
      {renderSelect("Waiting On Person", "waiting_on_person_id", personOpts)}
      {renderSelect("Waiting On Org", "waiting_on_org_id", orgOpts)}
      {renderSelect("Delegated By", "delegated_by_person_id", personOpts)}
      {renderSelect("Supervising Person", "supervising_person_id", personOpts)}

      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Trigger / Condition</label>
        <input style={INPUT_STYLE} type="text" value={form.trigger_description} onChange={set("trigger_description")} placeholder="What event or condition triggers this task?" />
      </div>

      {/* Tracks / Tracked-by relationship */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Tracks Task (action this follows up on)</label>
        <input style={INPUT_STYLE} type="text" value={form.tracks_task_id} onChange={set("tracks_task_id")} placeholder="Task ID of tracked action" />
      </div>
      {task?.tracks_task_title && (
        <div style={{ marginBottom: 14, fontSize: 12, color: "#94a3b8" }}>
          Tracking: <span style={{ color: "#60a5fa" }}>{task.tracks_task_title}</span>
        </div>
      )}
      {task?.tracked_by_tasks?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <label style={LABEL_STYLE}>Tracked By</label>
          {task.tracked_by_tasks.map(tb => (
            <div key={tb.id} style={{ fontSize: 12, color: "#60a5fa", marginBottom: 2 }}>
              {tb.title}
            </div>
          ))}
        </div>
      )}

      {error && <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", paddingTop: 16, borderTop: "1px solid #1f2937", marginTop: 10 }}>
        <button style={CANCEL_BTN} onClick={onClose}>Cancel</button>
        <button style={{ ...SAVE_BTN, opacity: saving ? 0.6 : 1 }} onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : (task ? "Save Changes" : "Create Task")}
        </button>
      </div>
    </DrawerShell>
  );
}
