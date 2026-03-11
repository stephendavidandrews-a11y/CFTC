import React, { useState, useCallback } from "react";
import theme from "../styles/theme";
import useApi from "../hooks/useApi";
import {
  listTasks, createTask, updateTask, deleteTask,
  listProjects,
} from "../api/work";
import { listTeam } from "../api/pipeline";
import DeadlineBadge from "../components/work/DeadlineBadge";
import FilterBar from "../components/work/FilterBar";
import Modal from "../components/shared/Modal";

const PRIORITIES = ["critical", "high", "medium", "low"];
const TASK_STATUSES = ["todo", "in_progress", "done", "deferred"];

export default function TasksPage() {
  const [filters, setFilters] = useState({});
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", priority_label: "medium" });
  const [quickAdd, setQuickAdd] = useState("");
  const [groupBy, setGroupBy] = useState("none");

  const { data: tasks, loading, refetch } = useApi(
    () => listTasks(Object.fromEntries(Object.entries(filters).filter(([_, v]) => v != null))),
    [JSON.stringify(filters)]
  );
  const { data: projects } = useApi(() => listProjects(), []);
  const { data: team } = useApi(() => listTeam(), []);

  const handleQuickAdd = async () => {
    if (!quickAdd.trim()) return;
    try {
      await createTask({ title: quickAdd.trim() });
      setQuickAdd("");
      refetch();
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  };

  const handleToggleTask = async (task) => {
    try {
      await updateTask(task.id, { status: task.status === "done" ? "todo" : "done" });
      refetch();
    } catch (err) {
      console.error("Failed to update task:", err);
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await deleteTask(taskId);
      refetch();
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  const handleCreateTask = async () => {
    if (!newTask.title.trim()) return;
    try {
      await createTask(newTask);
      setShowNewTask(false);
      setNewTask({ title: "", priority_label: "medium" });
      refetch();
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  };

  const taskList = tasks || [];
  const openCount = taskList.filter((t) => t.status !== "done" && t.status !== "deferred").length;
  const today = new Date().toISOString().split("T")[0];
  const overdueCount = taskList.filter((t) => t.due_date && t.due_date < today && t.status !== "done").length;
  const thisWeekEnd = new Date(Date.now() + 7 * 86400000).toISOString().split("T")[0];
  const dueThisWeek = taskList.filter((t) => t.due_date && t.due_date >= today && t.due_date <= thisWeekEnd && t.status !== "done").length;

  // Grouping
  let grouped = {};
  if (groupBy === "project") {
    taskList.forEach((t) => {
      const key = t.project_title || "No Project";
      (grouped[key] = grouped[key] || []).push(t);
    });
  } else if (groupBy === "priority") {
    PRIORITIES.forEach((p) => { grouped[p] = []; });
    grouped["none"] = [];
    taskList.forEach((t) => {
      const key = t.priority_label || "none";
      (grouped[key] = grouped[key] || []).push(t);
    });
  } else {
    grouped["all"] = taskList;
  }

  const pStyle = (p) => theme.priority[p] || theme.priority.medium;

  const fieldStyle = {
    background: theme.bg.input, border: `1px solid ${theme.border.default}`,
    borderRadius: 6, padding: "8px 10px", color: theme.text.primary,
    fontSize: 13, outline: "none", width: "100%",
  };

  return (
    <div style={{ padding: "24px 32px", maxWidth: 900 }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0 }}>My Tasks</h1>
            <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 4 }}>
              {openCount} open{overdueCount > 0 ? ` · ${overdueCount} overdue` : ""}{dueThisWeek > 0 ? ` · ${dueThisWeek} due this week` : ""}
            </div>
          </div>
          <button
            onClick={() => setShowNewTask(true)}
            style={{
              background: theme.accent.blue, border: "none",
              borderRadius: 6, padding: "6px 14px", color: "#fff",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}
          >+ New Task</button>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
          <FilterBar
            filters={filters}
            setFilters={setFilters}
            types={[]}
            team={team || []}
            showType={false}
            showSearch={false}
            statusOptions={TASK_STATUSES}
          />
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
            style={{
              background: theme.bg.input, border: `1px solid ${theme.border.default}`,
              borderRadius: 6, padding: "5px 8px", color: theme.text.primary,
              fontSize: 11, outline: "none",
            }}
          >
            <option value="none">No grouping</option>
            <option value="project">By Project</option>
            <option value="priority">By Priority</option>
          </select>
        </div>

        {/* Quick add */}
        <form onSubmit={(e) => { e.preventDefault(); handleQuickAdd(); }}
          style={{ display: "flex", gap: 6 }}
        >
          <input
            value={quickAdd}
            onChange={(e) => setQuickAdd(e.target.value)}
            placeholder="Quick add a task... (press Enter)"
            style={{
              flex: 1, background: theme.bg.input,
              border: `1px solid ${theme.border.default}`,
              borderRadius: 6, padding: "8px 12px", color: theme.text.primary,
              fontSize: 12, outline: "none",
            }}
          />
        </form>
      </div>

      {/* Task list */}
      {loading && (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.dim }}>Loading...</div>
      )}

      {!loading && Object.entries(grouped).map(([group, groupTasks]) => (
        <div key={group} style={{ marginBottom: 16 }}>
          {groupBy !== "none" && (
            <div style={{
              fontSize: 11, fontWeight: 600, color: theme.text.faint,
              textTransform: "uppercase", letterSpacing: "0.05em",
              marginBottom: 6, paddingLeft: 4,
            }}>{group} ({groupTasks.length})</div>
          )}

          <div style={{
            background: theme.bg.card, border: `1px solid ${theme.border.default}`,
            borderRadius: 10, overflow: "hidden",
          }}>
            {groupTasks.length === 0 && (
              <div style={{ padding: 16, color: theme.text.faint, fontSize: 12, textAlign: "center" }}>No tasks</div>
            )}
            {groupTasks.map((task, idx) => (
              <div key={task.id} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 14px",
                borderTop: idx > 0 ? `1px solid ${theme.border.subtle}` : "none",
                transition: "background 0.15s",
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = theme.bg.cardHover; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={task.status === "done"}
                  onChange={() => handleToggleTask(task)}
                  style={{ cursor: "pointer", flexShrink: 0 }}
                />

                {/* Title */}
                <span style={{
                  flex: 1, fontSize: 12,
                  color: task.status === "done" ? theme.text.faint : theme.text.primary,
                  textDecoration: task.status === "done" ? "line-through" : "none",
                }}>{task.title}</span>

                {/* Project link */}
                {task.project_title && (
                  <span style={{
                    fontSize: 10, color: theme.accent.blueLight,
                    background: "rgba(59,130,246,0.1)", borderRadius: 4,
                    padding: "1px 6px", whiteSpace: "nowrap",
                  }}>{task.project_title}</span>
                )}

                {/* Member */}
                {task.member_name && (
                  <span style={{ fontSize: 10, color: theme.text.dim, whiteSpace: "nowrap" }}>{task.member_name}</span>
                )}

                {/* Source badge */}
                {task.source_system && task.source_system !== "manual" && (
                  <span style={{
                    fontSize: 8, padding: "1px 5px", borderRadius: 3,
                    background: "#1f2937", color: theme.text.faint,
                    textTransform: "uppercase",
                  }}>{task.source_system}</span>
                )}

                {/* Priority */}
                <span style={{
                  fontSize: 9, fontWeight: 600, padding: "2px 6px",
                  borderRadius: 3, background: pStyle(task.priority_label).bg,
                  color: pStyle(task.priority_label).text,
                }}>{(task.priority_label || "medium").toUpperCase()}</span>

                {/* Deadline */}
                <DeadlineBadge date={task.due_date} />

                {/* Delete */}
                <button
                  onClick={() => handleDeleteTask(task.id)}
                  style={{
                    background: "none", border: "none", color: theme.text.faint,
                    fontSize: 12, cursor: "pointer", padding: "2px 4px",
                    opacity: 0.5, transition: "opacity 0.15s",
                  }}
                  onMouseEnter={(e) => { e.target.style.opacity = 1; }}
                  onMouseLeave={(e) => { e.target.style.opacity = 0.5; }}
                >x</button>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* New Task Modal */}
      <Modal isOpen={showNewTask} onClose={() => setShowNewTask(false)} title="New Task" width={480}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Title</label>
            <input
              autoFocus
              value={newTask.title}
              onChange={(e) => setNewTask((t) => ({ ...t, title: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreateTask(); }}
              style={fieldStyle}
              placeholder="What needs to be done?"
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Priority</label>
              <select
                value={newTask.priority_label}
                onChange={(e) => setNewTask((t) => ({ ...t, priority_label: e.target.value }))}
                style={fieldStyle}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Due Date</label>
              <input
                type="date"
                value={newTask.due_date || ""}
                onChange={(e) => setNewTask((t) => ({ ...t, due_date: e.target.value || undefined }))}
                style={fieldStyle}
              />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Project (optional)</label>
            <select
              value={newTask.project_id || ""}
              onChange={(e) => setNewTask((t) => ({ ...t, project_id: e.target.value ? parseInt(e.target.value) : undefined }))}
              style={fieldStyle}
            >
              <option value="">None</option>
              {(projects || []).map((p) => (
                <option key={p.id} value={p.id}>{p.title}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Team Member (optional)</label>
            <select
              value={newTask.linked_member_id || ""}
              onChange={(e) => setNewTask((t) => ({ ...t, linked_member_id: e.target.value ? parseInt(e.target.value) : undefined }))}
              style={fieldStyle}
            >
              <option value="">None</option>
              {(team || []).map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Description</label>
            <textarea
              value={newTask.description || ""}
              onChange={(e) => setNewTask((t) => ({ ...t, description: e.target.value }))}
              rows={3}
              style={{ ...fieldStyle, resize: "vertical" }}
              placeholder="Optional details..."
            />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
            <button
              onClick={() => setShowNewTask(false)}
              style={{
                background: "transparent", border: `1px solid ${theme.border.default}`,
                borderRadius: 6, padding: "8px 16px", color: theme.text.dim,
                fontSize: 12, cursor: "pointer",
              }}
            >Cancel</button>
            <button
              onClick={handleCreateTask}
              style={{
                background: theme.accent.blue, border: "none",
                borderRadius: 6, padding: "8px 16px", color: "#fff",
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >Create Task</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
