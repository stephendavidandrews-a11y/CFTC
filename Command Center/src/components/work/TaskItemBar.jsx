import React, { useState } from "react";
import theme from "../../styles/theme";
import QuickAdd from "./QuickAdd";

const STATUS_COLORS = {
  todo: { bg: "#1f2937", text: "#9ca3af" },
  in_progress: { bg: "#1e3a5f", text: "#60a5fa" },
  done: { bg: "#14532d", text: "#4ade80" },
  deferred: { bg: "#422006", text: "#fbbf24" },
};

export default function TaskItemBar({ task, depth = 0, onUpdateTask, onCreateSubTask, onDeleteTask }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = task.children && task.children.length > 0;
  const isDone = task.status === "done";
  const st = STATUS_COLORS[task.status] || STATUS_COLORS.todo;
  const indent = 20 * depth;

  return (
    <div>
      <div
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "4px 8px", paddingLeft: 8 + indent,
          borderRadius: 4, transition: "background 0.12s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      >
        {/* Expand/collapse for children */}
        {hasChildren ? (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "none", border: "none", color: theme.text.faint,
              fontSize: 8, cursor: "pointer", width: 12, textAlign: "center", padding: 0, flexShrink: 0,
            }}
          >{expanded ? "\u25BC" : "\u25B6"}</button>
        ) : (
          <span style={{ width: 12, flexShrink: 0 }} />
        )}

        {/* Checkbox */}
        <input
          type="checkbox"
          checked={isDone}
          onChange={() => {
            if (onUpdateTask) onUpdateTask(task.id, { status: isDone ? "todo" : "done" });
          }}
          style={{ margin: 0, cursor: "pointer", flexShrink: 0 }}
        />

        {/* Title */}
        <span style={{
          flex: 1, fontSize: 11, fontWeight: 500,
          color: isDone ? theme.text.faint : theme.text.secondary,
          textDecoration: isDone ? "line-through" : "none",
          minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{task.title}</span>

        {/* Project badge (shown at root level in TasksPage) */}
        {task.project_title && depth === 0 && (
          <span style={{
            fontSize: 9, color: theme.accent.blueLight,
            background: "rgba(59,130,246,0.1)", borderRadius: 3,
            padding: "1px 5px", whiteSpace: "nowrap",
          }}>{task.project_title}</span>
        )}

        {/* Due date */}
        {task.due_date && (
          <span style={{ fontSize: 9, color: theme.text.faint, fontFamily: theme.font.mono, whiteSpace: "nowrap" }}>
            {task.due_date}
          </span>
        )}

        {/* Status badge */}
        <span style={{
          fontSize: 8, fontWeight: 600, padding: "1px 5px",
          borderRadius: 3, background: st.bg, color: st.text, whiteSpace: "nowrap",
        }}>{task.status.replace("_", " ")}</span>

        {/* Add sub-task button */}
        {onCreateSubTask && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(true);
              // Will show the quick-add below
            }}
            title="Add sub-task"
            style={{
              background: "none", border: "none", color: theme.text.faint,
              fontSize: 11, cursor: "pointer", padding: "0 2px", flexShrink: 0,
            }}
          >+</button>
        )}

        {/* Delete */}
        {onDeleteTask && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm(`Delete task "${task.title}"?`)) onDeleteTask(task.id);
            }}
            style={{
              background: "none", border: "none", color: theme.text.faint,
              fontSize: 10, cursor: "pointer", padding: "0 2px", flexShrink: 0,
              opacity: 0.5,
            }}
          >&times;</button>
        )}
      </div>

      {/* Children */}
      {expanded && (
        <div>
          {hasChildren && task.children.map((child) => (
            <TaskItemBar
              key={child.id}
              task={child}
              depth={depth + 1}
              onUpdateTask={onUpdateTask}
              onCreateSubTask={onCreateSubTask}
              onDeleteTask={onDeleteTask}
            />
          ))}
          {onCreateSubTask && (
            <div style={{ paddingLeft: 8 + (depth + 1) * 20 + 12, paddingTop: 2, paddingBottom: 2 }}>
              <QuickAdd
                placeholder="+ Sub-task..."
                onAdd={(title) => onCreateSubTask({
                  title,
                  parent_id: task.id,
                  work_item_id: task.work_item_id,
                  project_id: task.project_id,
                })}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
