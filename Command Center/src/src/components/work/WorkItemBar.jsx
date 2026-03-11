import React from "react";
import theme from "../../styles/theme";
import ProgressBar from "./ProgressBar";
import DeadlineBadge from "./DeadlineBadge";
import InlineEditor from "./InlineEditor";
import QuickAdd from "./QuickAdd";

const STATUS_LABELS = {
  not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
  in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
  in_review: { bg: "#312e81", text: "#a78bfa", label: "In Review" },
  blocked: { bg: "#450a0a", text: "#f87171", label: "Blocked" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
};

function formatAssignees(assignees) {
  if (!assignees || assignees.length === 0) return "";
  // Lead first
  const sorted = [...assignees].sort((a, b) => (a.role === "lead" ? -1 : 1));
  const names = sorted.map((a) => a.name || `#${a.team_member_id}`);
  if (names.length <= 3) return names.join(", ");
  return `${names[0]}, ${names[1]} +${names.length - 2}`;
}

export default function WorkItemBar({
  item, depth = 0, isExpanded, toggleExpand, editingId, setEditingId,
  onUpdateItem, onAddItem, onDeleteItem, onAddAssignment, onRemoveAssignment,
  onCreateTask, team,
}) {
  const hasChildren = item.children && item.children.length > 0;
  const expanded = isExpanded(`item-${item.id}`);
  const editing = editingId === item.id;
  const st = STATUS_LABELS[item.status] || STATUS_LABELS.not_started;
  const indent = 24 * depth;

  const chevron = item.status === "completed"
    ? "\u2713"
    : hasChildren
    ? (expanded ? "\u25BC" : "\u25B6")
    : "\u2500";

  return (
    <div>
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 12px", paddingLeft: 12 + indent,
          background: editing ? "rgba(59,130,246,0.06)" : "transparent",
          borderRadius: 6, cursor: "pointer",
          borderLeft: depth > 0 ? `1px solid #1f2937` : "none",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => { if (!editing) e.currentTarget.style.background = theme.bg.cardHover; }}
        onMouseLeave={(e) => { if (!editing) e.currentTarget.style.background = editing ? "rgba(59,130,246,0.06)" : "transparent"; }}
      >
        {/* Chevron */}
        <button
          onClick={(e) => { e.stopPropagation(); if (hasChildren) toggleExpand(`item-${item.id}`); }}
          style={{
            background: "none", border: "none",
            color: item.status === "completed" ? theme.accent.green : theme.text.faint,
            fontSize: 10, cursor: hasChildren ? "pointer" : "default",
            width: 16, textAlign: "center", padding: 0, flexShrink: 0,
          }}
        >{chevron}</button>

        {/* Title */}
        <span
          onClick={() => setEditingId(editing ? null : item.id)}
          style={{
            flex: 1, fontSize: 12, fontWeight: 500,
            color: item.status === "completed" ? theme.text.faint : theme.text.primary,
            textDecoration: item.status === "completed" ? "line-through" : "none",
            minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}
        >{item.title}</span>

        {/* Assignees */}
        <span style={{ fontSize: 11, color: theme.text.dim, whiteSpace: "nowrap", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
          {formatAssignees(item.assignees)}
        </span>

        {/* Progress */}
        {hasChildren && (
          <ProgressBar completed={item.progress_completed} total={item.progress_total} width={60} />
        )}

        {/* Deadline */}
        <DeadlineBadge date={item.effective_deadline || item.due_date} />

        {/* Status badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, padding: "2px 7px",
          borderRadius: 4, background: st.bg, color: st.text,
          whiteSpace: "nowrap",
        }}>{st.label}</span>
      </div>

      {/* Inline editor */}
      {editing && (
        <div style={{ paddingLeft: 12 + indent + 24 }}>
          <InlineEditor
            item={item}
            onUpdate={onUpdateItem}
            onDelete={onDeleteItem}
            onCreateTask={onCreateTask}
            team={team}
            onAddAssignment={onAddAssignment}
            onRemoveAssignment={onRemoveAssignment}
          />
        </div>
      )}

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {item.children.map((child) => (
            <WorkItemBar
              key={child.id}
              item={child}
              depth={depth + 1}
              isExpanded={isExpanded}
              toggleExpand={toggleExpand}
              editingId={editingId}
              setEditingId={setEditingId}
              onUpdateItem={onUpdateItem}
              onAddItem={onAddItem}
              onDeleteItem={onDeleteItem}
              onAddAssignment={onAddAssignment}
              onRemoveAssignment={onRemoveAssignment}
              onCreateTask={onCreateTask}
              team={team}
            />
          ))}
          <div style={{ paddingLeft: 12 + (depth + 1) * 24 + 24, paddingTop: 2, paddingBottom: 4 }}>
            <QuickAdd
              placeholder="+ Add sub-item..."
              onAdd={(title) => onAddItem(item.project_id, title, item.id)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
