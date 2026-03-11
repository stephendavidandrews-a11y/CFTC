import React from "react";
import theme from "../../styles/theme";
import ProgressBar from "./ProgressBar";
import DeadlineBadge from "./DeadlineBadge";
import InlineEditor from "./InlineEditor";
import QuickAdd from "./QuickAdd";
import TaskItemBar from "./TaskItemBar";

const STATUS_LABELS = {
  not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
  in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
  in_review: { bg: "#312e81", text: "#a78bfa", label: "In Review" },
  waiting_on_stephen: { bg: "#431407", text: "#fb923c", label: "Waiting on Stephen" },
  blocked: { bg: "#450a0a", text: "#f87171", label: "Blocked" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
};

function formatAssignees(assignees) {
  if (!assignees || assignees.length === 0) return "";
  const sorted = [...assignees].sort((a, b) => (a.role === "lead" ? -1 : 1));
  const names = sorted.map((a) => a.name || `#${a.team_member_id}`);
  if (names.length <= 3) return names.join(", ");
  return `${names[0]}, ${names[1]} +${names.length - 2}`;
}

function countTasks(tasks) {
  if (!tasks) return 0;
  let count = 0;
  for (const t of tasks) {
    count++;
    if (t.children) count += countTasks(t.children);
  }
  return count;
}

export default function WorkItemBar({
  item, depth = 0, isExpanded, toggleExpand, editingId, setEditingId,
  onUpdateItem, onAddItem, onDeleteItem, onAddAssignment, onRemoveAssignment,
  onCreateTask, onUpdateTask, onDeleteTask, team,
}) {
  const hasChildren = item.children && item.children.length > 0;
  const hasTasks = item.tasks && item.tasks.length > 0;
  const hasContent = hasChildren || hasTasks;
  const expanded = isExpanded(`item-${item.id}`);
  const editing = editingId === item.id;
  const st = STATUS_LABELS[item.status] || STATUS_LABELS.not_started;
  const indent = 24 * depth;
  const taskCount = countTasks(item.tasks);

  const chevron = item.status === "completed"
    ? "\u2713"
    : hasContent
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
          borderLeft: item.needs_attention ? `3px solid ${theme.accent.red}` : (depth > 0 ? `1px solid #1f2937` : "none"),
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => { if (!editing) e.currentTarget.style.background = theme.bg.cardHover; }}
        onMouseLeave={(e) => { if (!editing) e.currentTarget.style.background = editing ? "rgba(59,130,246,0.06)" : "transparent"; }}
      >
        {/* Chevron */}
        <button
          onClick={(e) => { e.stopPropagation(); if (hasContent) toggleExpand(`item-${item.id}`); }}
          style={{
            background: "none", border: "none",
            color: item.status === "completed" ? theme.accent.green : theme.text.faint,
            fontSize: 10, cursor: hasContent ? "pointer" : "default",
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

        {/* Task count badge */}
        {taskCount > 0 && (
          <span style={{
            fontSize: 9, fontWeight: 600, padding: "1px 6px",
            borderRadius: 3, background: "#172554", color: theme.accent.blueLight,
            whiteSpace: "nowrap",
          }}>{taskCount} task{taskCount !== 1 ? "s" : ""}</span>
        )}

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

      {/* Expanded content: children work items + tasks */}
      {expanded && hasContent && (
        <div>
          {/* Child work items */}
          {hasChildren && item.children.map((child) => (
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
              onUpdateTask={onUpdateTask}
              onDeleteTask={onDeleteTask}
              team={team}
            />
          ))}

          {/* Tasks section */}
          {hasTasks && (
            <div style={{
              paddingLeft: 12 + (depth + 1) * 24,
              borderLeft: `1px solid #1e293b`,
              marginLeft: 12 + indent + 7,
              marginTop: hasChildren ? 2 : 0,
            }}>
              <div style={{ fontSize: 9, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em", padding: "3px 8px", fontWeight: 600 }}>
                Tasks
              </div>
              {item.tasks.map((task) => (
                <TaskItemBar
                  key={task.id}
                  task={task}
                  depth={0}
                  onUpdateTask={onUpdateTask}
                  onCreateSubTask={onCreateTask}
                  onDeleteTask={onDeleteTask}
                />
              ))}
            </div>
          )}

          {/* Quick add sub-item + task */}
          <div style={{ paddingLeft: 12 + (depth + 1) * 24 + 24, paddingTop: 2, paddingBottom: 4, display: "flex", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <QuickAdd
                placeholder="+ Add sub-item..."
                onAdd={(title) => onAddItem(item.project_id, title, item.id)}
              />
            </div>
            {onCreateTask && (
              <div style={{ flex: 1 }}>
                <QuickAdd
                  placeholder="+ Add task..."
                  onAdd={(title) => onCreateTask({ title, work_item_id: item.id, project_id: item.project_id })}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
