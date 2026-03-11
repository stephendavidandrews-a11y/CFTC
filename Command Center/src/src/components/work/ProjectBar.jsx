import React from "react";
import theme from "../../styles/theme";
import ProgressBar from "./ProgressBar";
import DeadlineBadge from "./DeadlineBadge";
import WorkItemBar from "./WorkItemBar";
import QuickAdd from "./QuickAdd";

const TYPE_COLORS = {
  rulemaking: "#3b82f6",
  guidance: "#a78bfa",
  exemptive_relief: "#34d399",
  interagency: "#f59e0b",
  congressional: "#ef4444",
  legal_opinion: "#60a5fa",
  enforcement: "#f87171",
  foia: "#6b7280",
  policy_research: "#22c55e",
};

const STATUS_STYLES = {
  active: { bg: "#172554", text: "#60a5fa" },
  paused: { bg: "#422006", text: "#fbbf24" },
  completed: { bg: "#14532d", text: "#4ade80" },
  archived: { bg: "#1f2937", text: "#6b7280" },
};

export default function ProjectBar({
  project, items = [], isExpanded, toggleExpand,
  editingId, setEditingId, onUpdateItem, onAddItem,
  onDeleteItem, onDeleteProject, onAddAssignment, onRemoveAssignment,
  onCreateTask, team, onClickProject,
}) {
  const expanded = isExpanded(`proj-${project.id}`);
  const pStyle = theme.priority[project.priority_label] || theme.priority.medium;
  const sStyle = STATUS_STYLES[project.status] || STATUS_STYLES.active;
  const typeColor = TYPE_COLORS[project.project_type] || "#6b7280";

  return (
    <div style={{
      background: theme.bg.card,
      border: `1px solid ${theme.border.default}`,
      borderRadius: 10, marginBottom: 6, overflow: "hidden",
    }}>
      {/* Collapsed bar */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px", cursor: "pointer",
          transition: "background 0.15s",
        }}
        onClick={() => toggleExpand(`proj-${project.id}`)}
        onMouseEnter={(e) => { e.currentTarget.style.background = theme.bg.cardHover; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      >
        {/* Chevron */}
        <span style={{ fontSize: 10, color: theme.text.faint, width: 14, textAlign: "center", flexShrink: 0 }}>
          {expanded ? "\u25BC" : "\u25B6"}
        </span>

        {/* Type badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, padding: "2px 7px",
          borderRadius: 4, background: `${typeColor}20`, color: typeColor,
          whiteSpace: "nowrap", flexShrink: 0,
        }}>
          {project.type_label || project.project_type}
        </span>

        {/* Title */}
        <span
          onClick={(e) => { e.stopPropagation(); if (onClickProject) onClickProject(project.id); }}
          style={{
            flex: 1, fontSize: 13, fontWeight: 600,
            color: theme.text.primary, minWidth: 0,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}
        >{project.title}</span>

        {/* Lead attorney */}
        <span style={{
          fontSize: 11, color: theme.text.dim, whiteSpace: "nowrap",
          maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis",
        }}>
          {project.lead_attorney_name || "Unassigned"}
        </span>

        {/* Progress */}
        {project.progress_total > 0 && (
          <ProgressBar
            completed={project.progress_completed}
            total={project.progress_total}
            width={70}
          />
        )}

        {/* Deadline */}
        <DeadlineBadge date={project.effective_deadline} />

        {/* Priority badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, padding: "2px 7px",
          borderRadius: 4, background: pStyle.bg, color: pStyle.text,
          whiteSpace: "nowrap",
        }}>
          {project.priority_label.toUpperCase()}
        </span>

        {/* Status badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, padding: "2px 7px",
          borderRadius: 4, background: sStyle.bg, color: sStyle.text,
          whiteSpace: "nowrap",
        }}>
          {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
        </span>
      </div>

      {/* Expanded: work items */}
      {expanded && (
        <div style={{
          borderTop: `1px solid ${theme.border.subtle}`,
          padding: "6px 0",
        }}>
          {items.length === 0 && (
            <div style={{ padding: "8px 24px", fontSize: 12, color: theme.text.faint }}>
              No work items yet
            </div>
          )}
          {items.map((item) => (
            <WorkItemBar
              key={item.id}
              item={item}
              depth={0}
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
          <div style={{ display: "flex", alignItems: "center", padding: "4px 24px 8px", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <QuickAdd
                placeholder="+ Add work item..."
                onAdd={(title) => onAddItem(project.id, title, null)}
              />
            </div>
            {onDeleteProject && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`Delete project "${project.title}" and all its items?`)) {
                    onDeleteProject(project.id);
                  }
                }}
                style={{
                  background: "transparent", border: `1px solid rgba(239,68,68,0.25)`,
                  borderRadius: 6, padding: "4px 10px", color: theme.accent.red,
                  fontSize: 10, cursor: "pointer", whiteSpace: "nowrap",
                }}
              >Delete Project</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
