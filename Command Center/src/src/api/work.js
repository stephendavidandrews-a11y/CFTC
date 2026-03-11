/**
 * Work Management API calls.
 */

import { fetchJSON } from "./client";

const W = "/pipeline/work";

// ── Projects ───────────────────────────────────────────────────────

export const listProjects = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${W}/projects?${q}`);
};

export const getProject = (id) => fetchJSON(`${W}/projects/${id}`);

export const createProject = (data) =>
  fetchJSON(`${W}/projects`, { method: "POST", body: JSON.stringify(data) });

export const updateProject = (id, data) =>
  fetchJSON(`${W}/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteProject = (id) =>
  fetchJSON(`${W}/projects/${id}`, { method: "DELETE" });

export const reorderProjects = (items) =>
  fetchJSON(`${W}/projects/reorder`, { method: "PATCH", body: JSON.stringify({ items }) });

// ── Work Items ─────────────────────────────────────────────────────

export const getProjectItems = (projectId) =>
  fetchJSON(`${W}/projects/${projectId}/items`);

export const createWorkItem = (projectId, data) =>
  fetchJSON(`${W}/projects/${projectId}/items`, { method: "POST", body: JSON.stringify(data) });

export const updateWorkItem = (id, data) =>
  fetchJSON(`${W}/items/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteWorkItem = (id) =>
  fetchJSON(`${W}/items/${id}`, { method: "DELETE" });

export const reorderWorkItems = (items) =>
  fetchJSON(`${W}/items/reorder`, { method: "PATCH", body: JSON.stringify({ items }) });

export const moveWorkItem = (id, data) =>
  fetchJSON(`${W}/items/${id}/move`, { method: "POST", body: JSON.stringify(data) });

// ── Assignments ────────────────────────────────────────────────────

export const getAssignments = (itemId) =>
  fetchJSON(`${W}/items/${itemId}/assignments`);

export const addAssignment = (itemId, data) =>
  fetchJSON(`${W}/items/${itemId}/assignments`, { method: "POST", body: JSON.stringify(data) });

export const removeAssignment = (id) =>
  fetchJSON(`${W}/assignments/${id}`, { method: "DELETE" });

export const getMemberItems = (memberId) =>
  fetchJSON(`${W}/team/${memberId}/items`);

// ── Dependencies ───────────────────────────────────────────────────

export const addDependency = (itemId, data) =>
  fetchJSON(`${W}/items/${itemId}/dependencies`, { method: "POST", body: JSON.stringify(data) });

export const removeDependency = (id) =>
  fetchJSON(`${W}/dependencies/${id}`, { method: "DELETE" });

// ── Tasks ──────────────────────────────────────────────────────────

export const listTasks = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${W}/tasks?${q}`);
};

export const createTask = (data) =>
  fetchJSON(`${W}/tasks`, { method: "POST", body: JSON.stringify(data) });

export const updateTask = (id, data) =>
  fetchJSON(`${W}/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteTask = (id) =>
  fetchJSON(`${W}/tasks/${id}`, { method: "DELETE" });

// ── Notes ──────────────────────────────────────────────────────────

export const listNotes = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`${W}/notes?${q}`);
};

export const createNote = (data) =>
  fetchJSON(`${W}/notes`, { method: "POST", body: JSON.stringify(data) });

export const deleteNote = (id) =>
  fetchJSON(`${W}/notes/${id}`, { method: "DELETE" });

// ── Dashboard ──────────────────────────────────────────────────────

export const getWorkDashboard = () => fetchJSON(`${W}/dashboard`);

export const getBottlenecks = () => fetchJSON(`${W}/dashboard/bottlenecks`);

// ── Types & Templates ──────────────────────────────────────────────

export const listProjectTypes = () => fetchJSON(`${W}/types`);

export const createProjectType = (data) =>
  fetchJSON(`${W}/types`, { method: "POST", body: JSON.stringify(data) });

export const getTemplates = (projectType) =>
  fetchJSON(`${W}/templates/${projectType}`);

export const replaceTemplates = (projectType, items) =>
  fetchJSON(`${W}/templates/${projectType}`, { method: "PUT", body: JSON.stringify(items) });
