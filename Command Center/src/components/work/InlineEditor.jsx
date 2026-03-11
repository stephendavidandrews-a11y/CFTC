import React, { useState } from "react";
import theme from "../../styles/theme";

const ITEM_STATUSES = ["not_started", "in_progress", "in_review", "waiting_on_stephen", "blocked", "completed"];
const PRIORITIES = ["critical", "high", "medium", "low"];

const labelStyle = { fontSize: 10, color: theme.text.faint, marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.05em" };
const fieldStyle = {
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  borderRadius: 6, padding: "6px 8px", color: theme.text.primary,
  fontSize: 12, outline: "none", width: "100%",
};

export default function InlineEditor({ item, onUpdate, onDelete, team = [], onAddAssignment, onRemoveAssignment, onCreateTask }) {
  const [desc, setDesc] = useState(item.description || "");
  const [newTaskTitle, setNewTaskTitle] = useState("");

  const handleField = (field, value) => {
    onUpdate(item.id, { [field]: value });
  };

  const handleAddTask = () => {
    if (!newTaskTitle.trim() || !onCreateTask) return;
    onCreateTask({ title: newTaskTitle.trim(), work_item_id: item.id, project_id: item.project_id });
    setNewTaskTitle("");
  };

  return (
    <div style={{
      background: theme.bg.cardHover, borderRadius: 8,
      border: `1px solid ${theme.border.subtle}`,
      padding: 16, marginTop: 4, marginBottom: 4,
    }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
        <div>
          <div style={labelStyle}>Status</div>
          <select
            value={item.status}
            onChange={(e) => handleField("status", e.target.value)}
            style={fieldStyle}
          >
            {ITEM_STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>
        <div>
          <div style={labelStyle}>Priority</div>
          <select
            value={item.priority_label || ""}
            onChange={(e) => handleField("priority_label", e.target.value || null)}
            style={fieldStyle}
          >
            <option value="">None</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
        </div>
        <div>
          <div style={labelStyle}>Due Date</div>
          <input
            type="date"
            value={item.due_date || ""}
            onChange={(e) => handleField("due_date", e.target.value || null)}
            style={fieldStyle}
          />
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={labelStyle}>Description</div>
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          onBlur={() => { if (desc !== (item.description || "")) handleField("description", desc); }}
          rows={3}
          style={{ ...fieldStyle, resize: "vertical" }}
        />
      </div>

      {item.status === "blocked" && (
        <div style={{ marginBottom: 12 }}>
          <div style={labelStyle}>Blocked Reason</div>
          <input
            value={item.blocked_reason || ""}
            onChange={(e) => handleField("blocked_reason", e.target.value)}
            style={fieldStyle}
            placeholder="Why is this blocked?"
          />
        </div>
      )}

      {/* Assignees */}
      <div style={{ marginBottom: 12 }}>
        <div style={labelStyle}>Assignees</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
          {(item.assignees || []).map((a) => (
            <span key={a.id} style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              background: "#172554", color: theme.accent.blueLight,
              borderRadius: 4, padding: "2px 8px", fontSize: 11,
            }}>
              {a.name || `ID ${a.team_member_id}`}
              <span style={{ fontSize: 9, color: theme.text.faint }}>({a.role})</span>
              {onRemoveAssignment && (
                <button
                  onClick={() => onRemoveAssignment(a.id)}
                  style={{
                    background: "none", border: "none", color: theme.text.faint,
                    cursor: "pointer", fontSize: 12, padding: 0, marginLeft: 2,
                  }}
                >x</button>
              )}
            </span>
          ))}
        </div>
        {onAddAssignment && team.length > 0 && (
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) onAddAssignment(item.id, parseInt(e.target.value));
            }}
            style={{ ...fieldStyle, width: "auto" }}
          >
            <option value="">+ Add assignee...</option>
            {team.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Quick-add task linked to this work item */}
      {onCreateTask && (
        <div style={{ marginBottom: 12 }}>
          <div style={labelStyle}>Add Task</div>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={newTaskTitle}
              onChange={(e) => setNewTaskTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleAddTask(); }}
              placeholder="Quick task linked to this item..."
              style={{ ...fieldStyle, flex: 1 }}
            />
            <button
              onClick={handleAddTask}
              style={{
                background: theme.accent.blue, border: "none", borderRadius: 6,
                padding: "5px 10px", color: "#fff", fontSize: 11, fontWeight: 600,
                cursor: "pointer", whiteSpace: "nowrap",
              }}
            >+ Task</button>
          </div>
        </div>
      )}

      {/* Delete work item */}
      {onDelete && (
        <div style={{ borderTop: `1px solid ${theme.border.subtle}`, paddingTop: 10 }}>
          <button
            onClick={() => {
              if (window.confirm(`Delete "${item.title}" and all sub-items?`)) onDelete(item.id);
            }}
            style={{
              background: "transparent", border: `1px solid rgba(239,68,68,0.3)`,
              borderRadius: 6, padding: "5px 12px", color: theme.accent.red,
              fontSize: 11, cursor: "pointer",
            }}
          >Delete this item</button>
        </div>
      )}
    </div>
  );
}
