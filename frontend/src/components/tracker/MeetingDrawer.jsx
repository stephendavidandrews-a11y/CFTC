import React from "react";
import DrawerShell from "./DrawerShell";
import { fetchJSON } from "../../api/client";
import {
  createMeeting,
  updateMeeting,
  addMeetingParticipant,
  removeMeetingParticipant,
  updateMeetingMatters,
} from "../../api/tracker";

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
const CHIP_STYLE = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: 6,
  padding: "4px 10px",
  fontSize: 12,
  color: "#e2e8f0",
  marginBottom: 4,
  marginRight: 4,
};
const REMOVE_BTN = {
  background: "none",
  border: "none",
  color: "#ef4444",
  cursor: "pointer",
  fontSize: 14,
  padding: 0,
  lineHeight: 1,
};
const ADD_ROW = { display: "flex", gap: 6, alignItems: "flex-end", marginTop: 6 };
const ADD_BTN = {
  background: "#1e40af",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "7px 14px",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const MEETING_ROLES_FALLBACK = ["chair", "presenter", "attendee", "decision-maker", "note-taker", "guest"];

const EMPTY = {
  title: "",
  meeting_type: "",
  date_time_start: "",
  duration_minutes: "",
  location_or_link: "",
  purpose: "",
  boss_attends: false,
  external_parties_attend: false,
  prep_needed: "",
  assigned_to_person_id: "",
  notes: "",
  decisions_made: "",
  readout_summary: "",
};

export default function MeetingDrawer({ isOpen, onClose, meeting, onSaved }) {
  const isEdit = !!meeting?.id;

  const [form, setForm] = React.useState({ ...EMPTY });
  const [participants, setParticipants] = React.useState([]);
  const [newParticipant, setNewParticipant] = React.useState({ person_id: "", meeting_role: "attendee" });
  const [linkedMatterIds, setLinkedMatterIds] = React.useState([]);
  const [newMatterId, setNewMatterId] = React.useState("");

  const [enums, setEnums] = React.useState({});
  const [people, setPeople] = React.useState([]);
  const [matters, setMatters] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState(null);

  // Load lookups on open
  React.useEffect(() => {
    if (!isOpen) return;
    Promise.all([
      fetchJSON("/tracker/lookups/enums/meeting_type").catch(() => []),
      fetchJSON("/tracker/lookups/enums/meeting_role").catch(() => MEETING_ROLES_FALLBACK),
      fetchJSON("/tracker/people?limit=100").catch(() => ({ items: [] })),
      fetchJSON("/tracker/matters?limit=200").catch(() => ({ items: [] })),
    ]).then(([meetingType, meetingRoles, ppl, matterList]) => {
      setEnums({ meeting_type: meetingType, meeting_role: Array.isArray(meetingRoles) ? meetingRoles : MEETING_ROLES_FALLBACK });
      setPeople(ppl.items || ppl || []);
      setMatters(matterList.items || matterList || []);
    });
  }, [isOpen]);

  // Populate form when meeting changes
  React.useEffect(() => {
    if (meeting) {
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
        boss_attends: meeting.boss_attends || false,
        external_parties_attend: meeting.external_parties_attend || false,
        prep_needed: meeting.prep_needed || "",
        assigned_to_person_id: meeting.assigned_to_person_id || "",
        notes: meeting.notes || "",
        decisions_made: meeting.decisions_made || "",
        readout_summary: meeting.readout_summary || "",
      });
      setParticipants(
        (meeting.participants || []).map((p) => ({
          id: p.id,
          person_id: p.person_id,
          meeting_role: p.meeting_role || "attendee",
          full_name: p.full_name || "",
          isNew: false,
        }))
      );
      setLinkedMatterIds((meeting.matters || []).map((m) => m.matter_id));
    } else {
      setForm({ ...EMPTY });
      setParticipants([]);
      setLinkedMatterIds([]);
    }
    setNewParticipant({ person_id: "", meeting_role: "attendee" });
    setNewMatterId("");
    setError(null);
  }, [meeting, isOpen]);

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const setCheck = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.checked }));

  const personName = (personId) => {
    const p = people.find((x) => x.id === personId);
    if (!p) return "Person #" + personId;
    return ((p.first_name || "") + " " + (p.last_name || "")).trim() || p.full_name || ("Person #" + p.id);
  };

  const handleAddParticipant = () => {
    if (!newParticipant.person_id) return;
    if (participants.some((p) => String(p.person_id) === String(newParticipant.person_id))) return;
    setParticipants((prev) => [
      ...prev,
      {
        ...newParticipant,
        full_name: personName(newParticipant.person_id),
        isNew: true,
        id: "new-" + Date.now(),
      },
    ]);
    setNewParticipant({ person_id: "", meeting_role: "attendee" });
  };

  const handleRemoveParticipant = (index) => {
    setParticipants((prev) => prev.filter((_, i) => i !== index));
  };

  const handleParticipantRoleChange = (index, role) => {
    setParticipants((prev) => prev.map((p, i) => (i === index ? { ...p, meeting_role: role } : p)));
  };

  const matterTitle = (matterId) => {
    const m = matters.find((x) => x.id === matterId);
    return m ? m.title || ("Matter #" + m.id) : ("Matter #" + matterId);
  };

  const handleAddMatter = () => {
    if (!newMatterId || linkedMatterIds.includes(newMatterId)) return;
    setLinkedMatterIds((prev) => [...prev, newMatterId]);
    setNewMatterId("");
  };

  const handleRemoveMatter = (matterId) => {
    setLinkedMatterIds((prev) => prev.filter((id) => id !== matterId));
  };

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const payload = {
        title: form.title || null,
        meeting_type: form.meeting_type || null,
        date_time_start: form.date_time_start || null,
        location_or_link: form.location_or_link || null,
        purpose: form.purpose || null,
        boss_attends: form.boss_attends,
        external_parties_attend: form.external_parties_attend,
        assigned_to_person_id: form.assigned_to_person_id || null,
        prep_needed: form.prep_needed || null,
        notes: form.notes || null,
        decisions_made: form.decisions_made || null,
        readout_summary: form.readout_summary || null,
      };

      if (form.date_time_start && form.duration_minutes) {
        const start = new Date(form.date_time_start);
        const end = new Date(start.getTime() + parseInt(form.duration_minutes, 10) * 60000);
        payload.date_time_end = end.toISOString().slice(0, 16);
      }

      if (!isEdit) { Object.keys(payload).forEach((k) => { if (payload[k] === null || payload[k] === undefined) delete payload[k]; }); }

      const missing = [];
      if (!payload.title) missing.push("Title");
      if (!payload.date_time_start) missing.push("Start Time");
      if (missing.length > 0) { setError("Required fields missing: " + missing.join(", ")); setSaving(false); return; }

      if (isEdit) {
        await updateMeeting(meeting.id, payload);

        const currentOrigIds = participants.filter((p) => !p.isNew).map((p) => p.id);
        for (const p of meeting.participants || []) {
          if (!currentOrigIds.includes(p.id)) {
            await removeMeetingParticipant(meeting.id, p.id);
          }
        }
        for (const p of participants.filter((p) => p.isNew)) {
          await addMeetingParticipant(meeting.id, { person_id: p.person_id, meeting_role: p.meeting_role });
        }

        await updateMeetingMatters(meeting.id, linkedMatterIds);
      } else {
        payload.participants = participants.map((p) => ({
          person_id: p.person_id,
          meeting_role: p.meeting_role,
        }));
        payload.matter_ids = linkedMatterIds;
        await createMeeting(payload);
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

  const personOpts = people.map((p) => ({
    value: p.id,
    label: ((p.first_name || "") + " " + (p.last_name || "")).trim() || p.full_name || ("Person #" + p.id),
  }));
  const matterOpts = matters.map((m) => ({ value: m.id, label: m.title || ("Matter #" + m.id) }));

  return (
    <DrawerShell isOpen={isOpen} onClose={onClose} title={isEdit ? "Edit Meeting" : "New Meeting"}>
      {renderInput("Title *", "title", "text", { required: true })}
      {renderSelect("Meeting Type", "meeting_type", enums.meeting_type)}
      {renderInput("Start Time *", "date_time_start", "datetime-local")}
      {renderInput("Duration (minutes)", "duration_minutes", "number", { min: 0 })}
      {renderInput("Location / Link", "location_or_link")}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Purpose</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.purpose} onChange={set("purpose")} />
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Prep Needed</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.prep_needed} onChange={set("prep_needed")} />
      </div>

      {/* Checkboxes */}
      <div style={{ display: "flex", gap: 20, marginBottom: 14 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#e2e8f0", cursor: "pointer" }}>
          <input type="checkbox" checked={form.boss_attends} onChange={setCheck("boss_attends")} style={{ accentColor: "#1e40af" }} />
          Boss attends
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#e2e8f0", cursor: "pointer" }}>
          <input type="checkbox" checked={form.external_parties_attend} onChange={setCheck("external_parties_attend")} style={{ accentColor: "#1e40af" }} />
          External parties attend
        </label>
      </div>

      {renderSelect("Owner", "assigned_to_person_id", personOpts)}

      {/* Participants */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Participants</label>
        <div style={{ border: "1px solid #1f2937", borderRadius: 6, background: "#0f172a", padding: "8px 10px", minHeight: 40 }}>
          {participants.length === 0 && <span style={{ color: "#64748b", fontSize: 12 }}>No participants added</span>}
          {participants.map((p, i) => (
            <div key={p.id || i} style={{ ...CHIP_STYLE, display: "flex", width: "100%", justifyContent: "space-between", marginRight: 0 }}>
              <span style={{ flex: 1 }}>{p.full_name || personName(p.person_id)}</span>
              <select
                value={p.meeting_role}
                onChange={(e) => handleParticipantRoleChange(i, e.target.value)}
                style={{ ...INPUT_STYLE, width: "auto", padding: "2px 6px", fontSize: 11, marginLeft: 6, minWidth: 100 }}
              >
                {(enums.meeting_role || MEETING_ROLES_FALLBACK).map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <button style={REMOVE_BTN} onClick={() => handleRemoveParticipant(i)} title="Remove">{"\u00D7"}</button>
            </div>
          ))}
          <div style={ADD_ROW}>
            <select
              style={{ ...INPUT_STYLE, flex: 1 }}
              value={newParticipant.person_id}
              onChange={(e) => setNewParticipant((np) => ({ ...np, person_id: e.target.value }))}
            >
              <option value="">Select person...</option>
              {personOpts
                .filter((o) => !participants.some((p) => String(p.person_id) === String(o.value)))
                .map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
            </select>
            <select
              style={{ ...INPUT_STYLE, width: "auto", minWidth: 110 }}
              value={newParticipant.meeting_role}
              onChange={(e) => setNewParticipant((np) => ({ ...np, meeting_role: e.target.value }))}
            >
              {(enums.meeting_role || MEETING_ROLES_FALLBACK).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button style={ADD_BTN} onClick={handleAddParticipant}>+ Add</button>
          </div>
        </div>
      </div>

      {/* Post-Meeting Fields */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Meeting Notes</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 80, resize: "vertical" }} value={form.notes} onChange={set("notes")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Decisions Made</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.decisions_made} onChange={set("decisions_made")} />
      </div>
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Readout Summary</label>
        <textarea style={{ ...INPUT_STYLE, minHeight: 60, resize: "vertical" }} value={form.readout_summary} onChange={set("readout_summary")} />
      </div>

      {/* Linked Matters */}
      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE}>Linked Matters</label>
        <div style={{ border: "1px solid #1f2937", borderRadius: 6, background: "#0f172a", padding: "8px 10px", minHeight: 40 }}>
          {linkedMatterIds.length === 0 && <span style={{ color: "#64748b", fontSize: 12 }}>No matters linked</span>}
          {linkedMatterIds.map((mid) => (
            <div key={mid} style={CHIP_STYLE}>
              <span>{matterTitle(mid)}</span>
              <button style={REMOVE_BTN} onClick={() => handleRemoveMatter(mid)} title="Remove">{"\u00D7"}</button>
            </div>
          ))}
          <div style={ADD_ROW}>
            <select
              style={{ ...INPUT_STYLE, flex: 1 }}
              value={newMatterId}
              onChange={(e) => setNewMatterId(e.target.value)}
            >
              <option value="">Select matter...</option>
              {matterOpts
                .filter((o) => !linkedMatterIds.includes(o.value))
                .map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
            </select>
            <button style={ADD_BTN} onClick={handleAddMatter}>+ Link</button>
          </div>
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
