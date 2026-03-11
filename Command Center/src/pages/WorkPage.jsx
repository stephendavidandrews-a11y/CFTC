import React, { useState, useCallback, useEffect } from "react";
import theme from "../styles/theme";
import useApi from "../hooks/useApi";
import useWorkTree, { buildTree } from "../hooks/useWorkTree";
import {
  listProjects, getProjectItems, createProject, deleteProject,
  createWorkItem, updateWorkItem, deleteWorkItem,
  addAssignment, removeAssignment, listProjectTypes,
  createTask, updateTask, deleteTask,
} from "../api/work";
import { listTeam, listItemsSimple } from "../api/pipeline";
import ProjectBar from "../components/work/ProjectBar";
import FilterBar from "../components/work/FilterBar";
import Modal from "../components/shared/Modal";
import { useNavigate } from "react-router-dom";

const PRIORITIES = ["critical", "high", "medium", "low"];
const PROJECT_SOURCES = [
  "Chairman", "General Counsel", "Commissioner", "PWG", "Treasury",
  "SEC", "Fed Reserve", "OCC", "FDIC", "FSOC", "OMB", "DOJ",
  "Congress", "Self-Initiated", "Other",
];

export default function WorkPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState({ status: "active" });
  const [projectItems, setProjectItems] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProject, setNewProject] = useState({ title: "", project_type: "rulemaking", priority_label: "medium", apply_template: true });
  const [pipelineItems, setPipelineItems] = useState([]);
  const [pipelineSearch, setPipelineSearch] = useState("");

  const { toggleExpand, isExpanded, expandAll, collapseAll } = useWorkTree();

  const { data: projects, loading, refetch } = useApi(
    () => listProjects(Object.fromEntries(Object.entries(filters).filter(([_, v]) => v != null))),
    [JSON.stringify(filters)]
  );
  const { data: types } = useApi(() => listProjectTypes(), []);
  const { data: team } = useApi(() => listTeam(), []);

  // Load pipeline items when New Project modal opens
  useEffect(() => {
    if (showNewProject) {
      listItemsSimple().then(setPipelineItems).catch(() => setPipelineItems([]));
    }
  }, [showNewProject]);

  // Load items when project is expanded
  const loadProjectItems = useCallback(async (projectId) => {
    if (projectItems[projectId]) return;
    try {
      const items = await getProjectItems(projectId);
      setProjectItems((prev) => ({ ...prev, [projectId]: items }));
    } catch (err) {
      console.error("Failed to load items:", err);
    }
  }, [projectItems]);

  const handleToggleExpand = useCallback((key) => {
    toggleExpand(key);
    // Load items when expanding a project
    if (key.startsWith("proj-")) {
      const id = parseInt(key.replace("proj-", ""));
      if (!isExpanded(key)) loadProjectItems(id);
    }
  }, [toggleExpand, isExpanded, loadProjectItems]);

  const handleAddItem = useCallback(async (projectId, title, parentId) => {
    try {
      await createWorkItem(projectId, { title, parent_id: parentId });
      const items = await getProjectItems(projectId);
      setProjectItems((prev) => ({ ...prev, [projectId]: items }));
      refetch();
    } catch (err) {
      console.error("Failed to add item:", err);
    }
  }, [refetch]);

  const handleUpdateItem = useCallback(async (itemId, data) => {
    try {
      const updated = await updateWorkItem(itemId, data);
      // Reload the project's items
      if (updated && updated.project_id) {
        const items = await getProjectItems(updated.project_id);
        setProjectItems((prev) => ({ ...prev, [updated.project_id]: items }));
        refetch();
      }
    } catch (err) {
      console.error("Failed to update item:", err);
    }
  }, [refetch]);

  const handleAddAssignment = useCallback(async (itemId, memberId) => {
    try {
      await addAssignment(itemId, { team_member_id: memberId, role: "assigned" });
      // Determine project and reload
      for (const [projId, items] of Object.entries(projectItems)) {
        if (items.some((i) => i.id === itemId)) {
          const reloaded = await getProjectItems(parseInt(projId));
          setProjectItems((prev) => ({ ...prev, [projId]: reloaded }));
          break;
        }
      }
    } catch (err) {
      console.error("Failed to add assignment:", err);
    }
  }, [projectItems]);

  const handleRemoveAssignment = useCallback(async (assignmentId) => {
    try {
      await removeAssignment(assignmentId);
      // Reload all expanded projects
      for (const projId of Object.keys(projectItems)) {
        const reloaded = await getProjectItems(parseInt(projId));
        setProjectItems((prev) => ({ ...prev, [projId]: reloaded }));
      }
    } catch (err) {
      console.error("Failed to remove assignment:", err);
    }
  }, [projectItems]);

  const handleDeleteItem = useCallback(async (itemId) => {
    try {
      await deleteWorkItem(itemId);
      // Reload all expanded projects
      for (const projId of Object.keys(projectItems)) {
        const reloaded = await getProjectItems(parseInt(projId));
        setProjectItems((prev) => ({ ...prev, [projId]: reloaded }));
      }
      refetch();
    } catch (err) {
      console.error("Failed to delete item:", err);
    }
  }, [projectItems, refetch]);

  const handleDeleteProject = useCallback(async (projectId) => {
    try {
      await deleteProject(projectId);
      setProjectItems((prev) => {
        const copy = { ...prev };
        delete copy[projectId];
        return copy;
      });
      refetch();
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
  }, [refetch]);

  const handleCreateTask = useCallback(async (taskData) => {
    try {
      await createTask(taskData);
      // Reload project items to show the new task
      if (taskData.project_id) {
        const items = await getProjectItems(taskData.project_id);
        setProjectItems((prev) => ({ ...prev, [taskData.project_id]: items }));
      }
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  }, []);

  const handleUpdateTask = useCallback(async (taskId, data) => {
    try {
      await updateTask(taskId, data);
      // Reload all expanded projects to reflect changes
      for (const projId of Object.keys(projectItems)) {
        const items = await getProjectItems(parseInt(projId));
        setProjectItems((prev) => ({ ...prev, [projId]: items }));
      }
    } catch (err) {
      console.error("Failed to update task:", err);
    }
  }, [projectItems]);

  const handleDeleteTask = useCallback(async (taskId) => {
    try {
      await deleteTask(taskId);
      // Reload all expanded projects
      for (const projId of Object.keys(projectItems)) {
        const items = await getProjectItems(parseInt(projId));
        setProjectItems((prev) => ({ ...prev, [projId]: items }));
      }
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  }, [projectItems]);

  const handleCreateProject = async () => {
    if (!newProject.title.trim()) return;
    try {
      await createProject(newProject);
      setShowNewProject(false);
      setNewProject({ title: "", project_type: "rulemaking", priority_label: "medium", apply_template: true });
      setPipelineSearch("");
      refetch();
    } catch (err) {
      console.error("Failed to create project:", err);
    }
  };

  const handleSelectPipelineItem = (itemId) => {
    if (!itemId) {
      setNewProject((p) => ({ ...p, linked_pipeline_id: null }));
      setPipelineSearch("");
      return;
    }
    const item = pipelineItems.find((i) => i.id === parseInt(itemId));
    if (item) {
      setNewProject((p) => ({
        ...p,
        title: item.title,
        project_type: "rulemaking",
        linked_pipeline_id: item.id,
      }));
      setPipelineSearch("");
    }
  };

  const filteredPipelineItems = pipelineSearch
    ? pipelineItems.filter(
        (i) =>
          i.title.toLowerCase().includes(pipelineSearch.toLowerCase()) ||
          (i.rin && i.rin.toLowerCase().includes(pipelineSearch.toLowerCase()))
      )
    : pipelineItems;

  const projectList = projects || [];
  const activeCount = projectList.filter((p) => p.status === "active").length;
  const totalItems = projectList.reduce((sum, p) => sum + (p.progress_total || 0), 0);
  const overdueCount = projectList.reduce((sum, p) => {
    const dl = p.effective_deadline;
    if (dl && new Date(dl) < new Date() && p.status !== "completed") return sum + 1;
    return sum;
  }, 0);

  const fieldStyle = {
    background: theme.bg.input, border: `1px solid ${theme.border.default}`,
    borderRadius: 6, padding: "8px 10px", color: theme.text.primary,
    fontSize: 13, outline: "none", width: "100%",
  };

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
              Work Management
            </h1>
            <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 4 }}>
              {activeCount} active projects · {totalItems} work items{overdueCount > 0 ? ` · ${overdueCount} overdue` : ""}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={collapseAll}
              style={{
                background: "transparent", border: `1px solid ${theme.border.default}`,
                borderRadius: 6, padding: "6px 12px", color: theme.text.dim,
                fontSize: 11, cursor: "pointer",
              }}
            >Collapse All</button>
            <button
              onClick={() => {
                if (projects) expandAll(projects.map((p) => `proj-${p.id}`));
              }}
              style={{
                background: "transparent", border: `1px solid ${theme.border.default}`,
                borderRadius: 6, padding: "6px 12px", color: theme.text.dim,
                fontSize: 11, cursor: "pointer",
              }}
            >Expand All</button>
            <button
              onClick={() => setShowNewProject(true)}
              style={{
                background: theme.accent.blue, border: "none",
                borderRadius: 6, padding: "6px 14px", color: "#fff",
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >+ New Project</button>
          </div>
        </div>

        <FilterBar
          filters={filters}
          setFilters={setFilters}
          types={types || []}
          team={team || []}
        />
      </div>

      {/* Project list */}
      {loading && (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.dim }}>Loading...</div>
      )}

      {!loading && projectList.length === 0 && (
        <div style={{
          padding: 40, textAlign: "center", color: theme.text.faint,
          background: theme.bg.card, borderRadius: 10,
          border: `1px solid ${theme.border.default}`,
        }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>No projects found</div>
          <div style={{ fontSize: 12 }}>Create a project to get started</div>
        </div>
      )}

      {projectList.map((project) => {
        const rawItems = projectItems[project.id] || [];
        const tree = buildTree(rawItems);
        return (
          <ProjectBar
            key={project.id}
            project={project}
            items={tree}
            isExpanded={isExpanded}
            toggleExpand={handleToggleExpand}
            editingId={editingId}
            setEditingId={setEditingId}
            onUpdateItem={handleUpdateItem}
            onAddItem={handleAddItem}
            onDeleteItem={handleDeleteItem}
            onDeleteProject={handleDeleteProject}
            onAddAssignment={handleAddAssignment}
            onRemoveAssignment={handleRemoveAssignment}
            onCreateTask={handleCreateTask}
            onUpdateTask={handleUpdateTask}
            onDeleteTask={handleDeleteTask}
            team={team || []}
            onClickProject={(id) => navigate(`/work/${id}`)}
          />
        );
      })}

      {/* New Project Modal */}
      <Modal
        isOpen={showNewProject}
        onClose={() => setShowNewProject(false)}
        title="New Project"
        width={480}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Link to Pipeline Rule */}
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Link to Pipeline Rule (optional)</label>
            <select
              value={newProject.linked_pipeline_id || ""}
              onChange={(e) => handleSelectPipelineItem(e.target.value)}
              style={fieldStyle}
            >
              <option value="">— None —</option>
              {filteredPipelineItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}{item.rin ? ` (${item.rin})` : ""}
                </option>
              ))}
            </select>
            {newProject.linked_pipeline_id && (
              <div style={{ marginTop: 4, fontSize: 10, color: "#a78bfa" }}>
                Linked — title and type auto-filled from pipeline item
              </div>
            )}
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Title</label>
            <input
              autoFocus
              value={newProject.title}
              onChange={(e) => setNewProject((p) => ({ ...p, title: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreateProject(); }}
              style={fieldStyle}
              placeholder="Project title"
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Type</label>
              <select
                value={newProject.project_type}
                onChange={(e) => setNewProject((p) => ({ ...p, project_type: e.target.value }))}
                style={fieldStyle}
              >
                {(types || []).map((t) => (
                  <option key={t.type_key} value={t.type_key}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Priority</label>
              <select
                value={newProject.priority_label}
                onChange={(e) => setNewProject((p) => ({ ...p, priority_label: e.target.value }))}
                style={fieldStyle}
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Lead Attorney</label>
            <select
              value={newProject.lead_attorney_id || ""}
              onChange={(e) => setNewProject((p) => ({ ...p, lead_attorney_id: e.target.value ? parseInt(e.target.value) : null }))}
              style={fieldStyle}
            >
              <option value="">None</option>
              {(team || []).map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Source</label>
              <select
                value={newProject.source || ""}
                onChange={(e) => setNewProject((p) => ({ ...p, source: e.target.value || null }))}
                style={fieldStyle}
              >
                <option value="">— None —</option>
                {PROJECT_SOURCES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Due Date</label>
              <input
                type="date"
                value={newProject.due_date || ""}
                onChange={(e) => setNewProject((p) => ({ ...p, due_date: e.target.value || null }))}
                style={fieldStyle}
              />
            </div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: theme.text.muted, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={newProject.apply_template}
              onChange={(e) => setNewProject((p) => ({ ...p, apply_template: e.target.checked }))}
            />
            Apply project type template
          </label>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
            <button
              onClick={() => setShowNewProject(false)}
              style={{
                background: "transparent", border: `1px solid ${theme.border.default}`,
                borderRadius: 6, padding: "8px 16px", color: theme.text.dim,
                fontSize: 12, cursor: "pointer",
              }}
            >Cancel</button>
            <button
              onClick={handleCreateProject}
              style={{
                background: theme.accent.blue, border: "none",
                borderRadius: 6, padding: "8px 16px", color: "#fff",
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >Create Project</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
