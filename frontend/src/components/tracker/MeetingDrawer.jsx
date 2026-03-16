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
  meeting_type: "",
  date_time_start: "",
  duration_minutes: "",
  location_or_link: "",
  purpose: "",
  matter_id: "",
  participant_ids: [],
};

export default function MeetingDrawer({ isOpen, onClose, meeting, onSaved }) {
  const [form, setForm] = React.useState({ ...EMPTY });
  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/meeting_type").catch(() => []),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/matters?limit=200").catch(() => ({ items: [] })),
    ]).then(([meetingType, ppl, matterList]) => {
      setEnums({ meeting_type: meetingType });
      setPeople(ppl.items || ppl || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  React.useEffect(() => {
    if (meeting) {
      // Compute duration from start/end if available
      let duration = "";
      if (meeting.date_time_start && meeting.date_time_end) {
        const diffMs = new Date(meeting.date_time_end) - new Date(meeting.date_time_start);
        if (diffMs > 0) duration = String(Math.round(diffMs / 60000));
      }
      setForm({
        title: meeting.title || "",
        meeting_type: meeting.meeting_type || "",
        date_time_start: meeting.date_time_start ? meeting.date_time_start.slice(0, 16) : "",
        duration_minutes: duration || "",
        location_or_link: meeting.location_or_link || "",
        purpose: meeting.purpose || "",
        matter_id: meeting.matter_id || (meeting.matters && meeting.matters[0] ? meeting.matters[0].matter_id : "") || "",
        participant_ids: meeting.participant_ids || (meeting.participants || []).map((p) => p.id || p.person_id) || [],
      });
    } else {
      setForm({ ...EMPTY });
    }
    setError(null);
  }, [meeting, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const toggleParticipant = (id) => {
    setForm((f) => {
      const ids = f.participant_ids.includes(id)
        ? f.participant_ids.filter((x) => x !== id)
        : [...f.participant_ids, id];
      return { ...f, participant_ids: ids };
    });
  };

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      // Build payload with correct backend field names
      const payload = {
        title: form.title || null,
        meeting_type: form.meeting_type || null,
        date_time_start: form.date_time_start || null,
        location_or_link: form.location_or_link || null,
        purpose: form.purpose || null,
        assigned_to_person_id: null,
        matter_ids: form.matter_id ? [form.matter_id] : [],
      };

      // Compute date_time_end from start + duration
      if (form.date_time_start && form.duration_minutes) {
        const start = new Date(form.date_time_start);
        const end = new Date(start.getTime() + parseInt(form.duration_minutes, 10) * 60000);
        payload.date_time_end = end.toISOString().slice(0, 16);
      }

      if (!payload.title) { setError("Title is required"); setSaving(false); return; }
      if (!payload.date_time_start) { setError("Start time is required"); setSaving(false); return; }

      // For create, include participants as array of objects
      if (!meeting?.id) {
        payload.participants = form.participant_ids.map((pid) => ({ person_id: pid }));
      }

      if (meeting?.id) {
        await fetchJSON(`/tracker/meetings/${meeting.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await fetchJSON("/tracker/meetings", { method: "POST", body: JSON.stringify(payload) });
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

  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || `Matter #${m.id}` }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={meeting ? "Edit Meeting" : "New Meeting"}>
      {renderInput("Title", "title", "text", { required: true })}
      {renderSelect("Meeting Type", "meeting_type", enums.meeting_type)}
      {renderInput("Start Time", "date_time_start", "datetime-local")}
      {renderInput("Duration (minutes)", "duration_minutes", "number", { min: 0 })}
      {renderInput("Location / Link", "location_or_link")}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Purpose</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.purpose} onChange={set("purpose")} />
      </div>
      {renderSelect("Matter", "matter_id", matterOpts)}

      {/* Participants multi-select */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Participants</label>
        <div
          style={{
            maxHeight: 160,
            overflowY: "auto",
            border: "1px solid #1f2937",
            borderRadius: 6,
            background: "#0f172a",
            padding: "6px 10px",
          }}
        >
          {people.length === 0 && <span style={{ color: "#64748b", fontSize: 12 }}>No people loaded</span>}
          {people.map((p) => {
            const label = `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.full_name || `Person #${p.id}`;
            const checked = form.participant_ids.includes(p.id);
            return (
              <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0" }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleParticipant(p.id)}
                  style={{ accentColor: "#1e40af" }}
                />
                <span style={{ fontSize: 12, color: "#f1f5f9" }}>{label}</span>
              </div>
            );
          })}
        </div>
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
