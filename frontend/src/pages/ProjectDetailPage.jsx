import React, { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../styles/theme";
import useApi from "../hooks/useApi";
import useWorkTree, { buildTree } from "../hooks/useWorkTree";
import {
  getProject, updateProject, deleteProject,
  getProjectItems, createWorkItem, updateWorkItem, deleteWorkItem,
  addAssignment, removeAssignment,
  listNotes, createNote, deleteNote,
  listTasks, createTask, updateTask, deleteTask,
} from "../api/work";
import { listTeam, processNotes } from "../api/pipeline";
import WorkItemBar from "../components/work/WorkItemBar";
import QuickAdd from "../components/work/QuickAdd";
import DeadlineBadge from "../components/work/DeadlineBadge";
import ProgressBar from "../components/work/ProgressBar";

const STATUS_OPTS = ["active", "paused", "completed", "archived"];
const PRIORITY_OPTS = ["critical", "high", "medium", "low"];
const NOTE_TYPES = ["general", "one_on_one", "decision", "followup", "meeting"];
const CONTEXT_TYPES = ["general", "one_on_one", "team_meeting", "hallway", "email", "work_review"];

export default function ProjectDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [editingId, setEditingId] = useState(null);
  const [activeTab, setActiveTab] = useState("notes");
  const [newNote, setNewNote] = useState("");
  const [newNoteType, setNewNoteType] = useState("general");
  const [newContextType, setNewContextType] = useState("general");
  const [processingAI, setProcessingAI] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");

  const { toggleExpand, isExpanded, expandAll, collapseAll } = useWorkTree();

  const { data: project, refetch: refetchProject } = useApi(() => getProject(id), [id]);
  const { data: rawItems, refetch: refetchItems } = useApi(() => getProjectItems(id), [id]);
  const { data: team } = useApi(() => listTeam(), []);
  const { data: notes, refetch: refetchNotes } = useApi(() => listNotes({ project_id: id }), [id]);
  const { data: tasks, refetch: refetchTasks } = useApi(() => listTasks({ project_id: id }), [id]);

  const items = rawItems ? buildTree(rawItems) : [];

  const handleUpdateProject = async (field, value) => {
    try {
      await updateProject(id, { [field]: value });
      refetchProject();
    } catch (err) {
      console.error("Failed to update project:", err);
    }
  };

  const handleDeleteProject = async () => {
    if (!window.confirm("Delete this project and all its work items?")) return;
    try {
      await deleteProject(id);
      navigate("/work");
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
  };

  const handleAddItem = useCallback(async (projectId, title, parentId) => {
    try {
      await createWorkItem(projectId, { title, parent_id: parentId });
      refetchItems();
      refetchProject();
    } catch (err) {
      console.error("Failed to add item:", err);
    }
  }, [refetchItems, refetchProject]);

  const handleUpdateItem = useCallback(async (itemId, data) => {
    try {
      await updateWorkItem(itemId, data);
      refetchItems();
      refetchProject();
    } catch (err) {
      console.error("Failed to update item:", err);
    }
  }, [refetchItems, refetchProject]);

  const handleAddAssignment = useCallback(async (itemId, memberId) => {
    try {
      await addAssignment(itemId, { team_member_id: memberId, role: "assigned" });
      refetchItems();
    } catch (err) {
      console.error("Failed to add assignment:", err);
    }
  }, [refetchItems]);

  const handleRemoveAssignment = useCallback(async (assignmentId) => {
    try {
      await removeAssignment(assignmentId);
      refetchItems();
    } catch (err) {
      console.error("Failed to remove assignment:", err);
    }
  }, [refetchItems]);

  const handleDeleteItem = useCallback(async (itemId) => {
    try {
      await deleteWorkItem(itemId);
      refetchItems();
      refetchProject();
    } catch (err) {
      console.error("Failed to delete item:", err);
    }
  }, [refetchItems, refetchProject]);

  const handleCreateTaskForItem = useCallback(async (taskData) => {
    try {
      await createTask(taskData);
      refetchItems();
      refetchTasks();
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  }, [refetchItems, refetchTasks]);

  const handleUpdateTask = useCallback(async (taskId, data) => {
    try {
      await updateTask(taskId, data);
      refetchItems();
      refetchTasks();
    } catch (err) {
      console.error("Failed to update task:", err);
    }
  }, [refetchItems, refetchTasks]);

  const handleDeleteTask = useCallback(async (taskId) => {
    try {
      await deleteTask(taskId);
      refetchItems();
      refetchTasks();
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  }, [refetchItems, refetchTasks]);

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    try {
      await createNote({ content: newNote, project_id: parseInt(id), note_type: newNoteType, context_type: newContextType });
      setNewNote("");
      refetchNotes();
    } catch (err) {
      console.error("Failed to add note:", err);
    }
  };

  const handleDeleteNote = async (noteId) => {
    try {
      await deleteNote(noteId);
      refetchNotes();
    } catch (err) {
      console.error("Failed to delete note:", err);
    }
  };

  const handleAddTask = async () => {
    if (!newTaskTitle.trim()) return;
    try {
      await createTask({ title: newTaskTitle, project_id: parseInt(id) });
      setNewTaskTitle("");
      refetchTasks();
    } catch (err) {
      console.error("Failed to add task:", err);
    }
  };

  if (!project) {
    return <div style={{ padding: 40, color: theme.text.dim }}>Loading...</div>;
  }

  const fieldStyle = {
    background: theme.bg.input, border: `1px solid ${theme.border.default}`,
    borderRadius: 6, padding: "6px 8px", color: theme.text.primary,
    fontSize: 12, outline: "none",
  };

  const tabStyle = (active) => ({
    padding: "8px 14px", fontSize: 12, fontWeight: active ? 600 : 500,
    color: active ? theme.accent.blueLight : theme.text.dim,
    background: active ? "rgba(59,130,246,0.12)" : "transparent",
    border: `1px solid ${active ? "rgba(59,130,246,0.2)" : "transparent"}`,
    borderRadius: 6, cursor: "pointer",
  });

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Back nav */}
      <button
        onClick={() => navigate("/work")}
        style={{
          background: "none", border: "none", color: theme.accent.blue,
          fontSize: 12, cursor: "pointer", padding: 0, marginBottom: 16,
        }}
      >{"\u2190"} Back to Projects</button>

      {/* Header */}
      <div style={{
        background: theme.bg.card, border: `1px solid ${theme.border.default}`,
        borderRadius: 10, padding: 20, marginBottom: 20,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
            {project.title}
          </h1>
          <button
            onClick={handleDeleteProject}
            style={{
              background: "transparent", border: `1px solid ${theme.border.default}`,
              borderRadius: 6, padding: "4px 10px", color: theme.accent.red,
              fontSize: 11, cursor: "pointer",
            }}
          >Delete</button>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", marginBottom: 12 }}>
          <select value={project.status} onChange={(e) => handleUpdateProject("status", e.target.value)} style={fieldStyle}>
            {STATUS_OPTS.map((s) => (<option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>))}
          </select>
          <select value={project.priority_label} onChange={(e) => handleUpdateProject("priority_label", e.target.value)} style={fieldStyle}>
            {PRIORITY_OPTS.map((p) => (<option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>))}
          </select>
          <select
            value={project.lead_attorney_id || ""}
            onChange={(e) => handleUpdateProject("lead_attorney_id", e.target.value ? parseInt(e.target.value) : null)}
            style={fieldStyle}
          >
            <option value="">No lead</option>
            {(team || []).map((m) => (<option key={m.id} value={m.id}>{m.name}</option>))}
          </select>
          <ProgressBar completed={project.progress_completed} total={project.progress_total} width={100} />
          <DeadlineBadge date={project.effective_deadline} />
        </div>

        {project.description && (
          <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>{project.description}</div>
        )}
      </div>

      {/* Main content: items + sidebar */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20 }}>
        {/* Work items tree */}
        <div style={{
          background: theme.bg.card, border: `1px solid ${theme.border.default}`,
          borderRadius: 10, padding: "12px 0",
        }}>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "0 14px 10px", borderBottom: `1px solid ${theme.border.subtle}`,
          }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: theme.text.primary }}>Work Items</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={collapseAll} style={{
                background: "none", border: "none", color: theme.text.faint, fontSize: 10, cursor: "pointer",
              }}>Collapse</button>
              <button onClick={() => {
                if (rawItems) expandAll(rawItems.map((i) => `item-${i.id}`));
              }} style={{
                background: "none", border: "none", color: theme.text.faint, fontSize: 10, cursor: "pointer",
              }}>Expand</button>
            </div>
          </div>

          <div style={{ padding: "8px 0" }}>
            {items.length === 0 && (
              <div style={{ padding: "16px 24px", color: theme.text.faint, fontSize: 12 }}>No work items</div>
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
                onUpdateItem={handleUpdateItem}
                onAddItem={handleAddItem}
                onDeleteItem={handleDeleteItem}
                onAddAssignment={handleAddAssignment}
                onRemoveAssignment={handleRemoveAssignment}
                onCreateTask={handleCreateTaskForItem}
                onUpdateTask={handleUpdateTask}
                onDeleteTask={handleDeleteTask}
                team={team || []}
              />
            ))}
            <div style={{ padding: "6px 14px" }}>
              <QuickAdd
                placeholder="+ Add work item..."
                onAdd={(title) => handleAddItem(parseInt(id), title, null)}
              />
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div>
          <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
            {["notes", "tasks"].map((tab) => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={tabStyle(activeTab === tab)}>
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div style={{
            background: theme.bg.card, border: `1px solid ${theme.border.default}`,
            borderRadius: 10, padding: 14,
          }}>
            {/* Notes tab */}
            {activeTab === "notes" && (
              <div>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
                    <select value={newNoteType} onChange={(e) => setNewNoteType(e.target.value)} style={{ ...fieldStyle, flex: 0 }}>
                      {NOTE_TYPES.map((t) => (<option key={t} value={t}>{t.replace(/_/g, " ")}</option>))}
                    </select>
                    <select value={newContextType} onChange={(e) => setNewContextType(e.target.value)} style={{ ...fieldStyle, flex: 0 }}>
                      {CONTEXT_TYPES.map((t) => (<option key={t} value={t}>{t.replace(/_/g, " ")}</option>))}
                    </select>
                  </div>
                  <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Add a note..."
                    rows={3}
                    style={{ ...fieldStyle, width: "100%", resize: "vertical", marginBottom: 6 }}
                  />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={handleAddNote} style={{
                      background: theme.accent.blue, border: "none", borderRadius: 6,
                      padding: "5px 12px", color: "#fff", fontSize: 11, fontWeight: 600, cursor: "pointer",
                    }}>Save Note</button>
                    {(notes || []).some((n) => !n.processed) && (
                      <button
                        disabled={processingAI}
                        onClick={async () => {
                          setProcessingAI(true);
                          try {
                            const unprocessedIds = (notes || []).filter((n) => !n.processed).map((n) => n.id);
                            await processNotes(unprocessedIds);
                            refetchNotes();
                          } catch (err) {
                            console.error("AI processing failed:", err);
                          } finally {
                            setProcessingAI(false);
                          }
                        }}
                        style={{
                          background: processingAI ? "#1f2937" : "#1e1b4b",
                          border: "1px solid rgba(167,139,250,0.3)", borderRadius: 6,
                          padding: "5px 12px", color: processingAI ? theme.text.faint : "#a78bfa",
                          fontSize: 11, fontWeight: 600, cursor: processingAI ? "not-allowed" : "pointer",
                        }}
                      >{processingAI ? "Processing..." : "Process with AI"}</button>
                    )}
                  </div>
                </div>
                {(notes || []).map((note) => (
                  <div key={note.id} style={{
                    padding: "10px 0", borderTop: `1px solid ${theme.border.subtle}`,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <span style={{ fontSize: 9, color: theme.text.faint, textTransform: "uppercase" }}>
                          {note.note_type.replace(/_/g, " ")}
                        </span>
                        {note.context_type && note.context_type !== "general" && (
                          <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "#1e1b4b", color: "#a78bfa" }}>
                            {note.context_type.replace(/_/g, " ")}
                          </span>
                        )}
                        {note.processed && (
                          <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "#052e16", color: "#4ade80" }}>
                            AI processed
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 10, color: theme.text.faint }}>
                          {new Date(note.created_at).toLocaleDateString()}
                        </span>
                        <button
                          onClick={() => handleDeleteNote(note.id)}
                          style={{ background: "none", border: "none", color: theme.text.faint, fontSize: 11, cursor: "pointer" }}
                        >x</button>
                      </div>
                    </div>
                    <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                      {note.content}
                    </div>
                    {note.member_name && (
                      <div style={{ fontSize: 10, color: theme.text.dim, marginTop: 4 }}>
                        Linked to: {note.member_name}
                      </div>
                    )}
                    {note.ai_insights && (
                      <div style={{
                        marginTop: 6, padding: "8px 10px", borderRadius: 6,
                        background: "rgba(167,139,250,0.06)", border: "1px solid rgba(167,139,250,0.15)",
                      }}>
                        <div style={{ fontSize: 9, fontWeight: 600, color: "#a78bfa", textTransform: "uppercase", marginBottom: 3 }}>
                          AI Insight
                        </div>
                        <div style={{ fontSize: 11, color: theme.text.secondary, lineHeight: 1.5 }}>
                          {note.ai_insights}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {(!notes || notes.length === 0) && (
                  <div style={{ color: theme.text.faint, fontSize: 12, padding: "8px 0" }}>No notes yet</div>
                )}
              </div>
            )}

            {/* Tasks tab */}
            {activeTab === "tasks" && (
              <div>
                <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                  <input
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") handleAddTask(); }}
                    placeholder="New task..."
                    style={{ ...fieldStyle, flex: 1 }}
                  />
                  <button onClick={handleAddTask} style={{
                    background: theme.accent.blue, border: "none", borderRadius: 6,
                    padding: "5px 12px", color: "#fff", fontSize: 11, fontWeight: 600, cursor: "pointer",
                  }}>Add</button>
                </div>
                {(tasks || []).map((task) => (
                  <div key={task.id} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "8px 0", borderTop: `1px solid ${theme.border.subtle}`,
                  }}>
                    <input
                      type="checkbox"
                      checked={task.status === "done"}
                      onChange={async () => {
                        const { updateTask } = await import("../api/work");
                        await updateTask(task.id, { status: task.status === "done" ? "todo" : "done" });
                        refetchTasks();
                      }}
                    />
                    <span style={{
                      fontSize: 12, flex: 1,
                      color: task.status === "done" ? theme.text.faint : theme.text.primary,
                      textDecoration: task.status === "done" ? "line-through" : "none",
                    }}>{task.title}</span>
                    {task.due_date && <DeadlineBadge date={task.due_date} />}
                  </div>
                ))}
                {(!tasks || tasks.length === 0) && (
                  <div style={{ color: theme.text.faint, fontSize: 12, padding: "8px 0" }}>No tasks yet</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
