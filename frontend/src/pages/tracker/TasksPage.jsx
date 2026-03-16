import React, { useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listTasks, getEnums, listMatters, listPeople } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 24 };

const inputStyle = {
  background: theme.bg.input,
  border: `1px solid ${theme.border.default}`,
  borderRadius: 6,
  padding: "7px 12px",
  fontSize: 13,
  color: theme.text.secondary,
  outline: "none",
  minWidth: 140,
};

const btnPrimary = {
  padding: "8px 18px",
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 600,
  background: theme.accent.blue,
  color: "#fff",
  border: "none",
  cursor: "pointer",
};

function formatDate(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function TasksPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState({
    status: searchParams.get("status") || "",
    mode: searchParams.get("mode") || "",
    assigned_to: searchParams.get("assigned_to") || "",
    matter_id: searchParams.get("matter_id") || "",
  });
  const [viewMode, setViewMode] = useState(searchParams.get("view") === "attention" ? "attention" : "all");


  const { data: enums } = useApi(() => getEnums(), []);
  const { data: peopleData } = useApi(() => listPeople({ limit: 500 }), []);
  const { data: mattersData } = useApi(() => listMatters({ limit: 500 }), []);

  const { data, loading, error, refetch } = useApi(
    () => listTasks(filters),
    [filters.status, filters.mode, filters.assigned_to, filters.matter_id]
  );

  const handleFilter = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const allTasks = data?.items || data || [];

  const now = new Date();
  const sevenDaysOut = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  const attentionTasks = allTasks.filter((t) => {
    if (t.status === "done" || t.status === "deferred") return false;
    const due = t.due_date ? new Date(t.due_date) : null;
    if (due && due < now) return true; // overdue
    if (due && due <= sevenDaysOut) return true; // due soon
    if (t.priority === "critical" || t.priority === "high") return true;
    if (t.status === "needs review") return true;
    if (t.status === "waiting on others") return true;
    return false;
  });

  const tasks = viewMode === "attention" ? attentionTasks : allTasks;
  const people = peopleData?.items || peopleData || [];
  const matters = mattersData?.items || mattersData || [];
  const statusOpts = enums?.task_status || enums?.status || [];
  const modeOpts = enums?.task_mode || ["action", "reading", "waiting"];

  const columns = [
    { key: "title", label: "Title" },
    {
      key: "matter_title", label: "Matter", width: 180,
      render: (val, row) => (
        <span style={{ color: theme.accent.blue, cursor: "pointer" }}
          onClick={(e) => { e.stopPropagation(); if (row.matter_id) navigate(`/matters/${row.matter_id}`); }}
        >{val || "\u2014"}</span>
      ),
    },
    {
      key: "status", label: "Status", width: 110,
      render: (val) => {
        const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
      },
    },
    { key: "mode", label: "Mode", width: 90 },
    { key: "owner_name", label: "Assignee", width: 130 },
    { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
    {
      key: "priority", label: "Priority", width: 100,
      render: (val) => {
        const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
      },
    },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Tasks</div>
        <button style={btnPrimary} onClick={() => openDrawer("task", null, refetch)}>
          + New Task
        </button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <button
          onClick={() => setViewMode("all")}
          style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
            background: viewMode === "all" ? "#3b82f6" : "transparent",
            color: viewMode === "all" ? "#fff" : "#64748b",
            border: viewMode === "all" ? "none" : "1px solid #1f2937",
          }}
        >All Tasks</button>
        <button
          onClick={() => setViewMode("attention")}
          style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
            background: viewMode === "attention" ? "#ef4444" : "transparent",
            color: viewMode === "attention" ? "#fff" : "#64748b",
            border: viewMode === "attention" ? "none" : "1px solid #1f2937",
          }}
        >
          Needs Attention{attentionTasks.length > 0 ? ` (${attentionTasks.length})` : ""}
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <select style={inputStyle} value={filters.status} onChange={(e) => handleFilter("status", e.target.value)}>
          <option value="">All Statuses</option>
          {statusOpts.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select style={inputStyle} value={filters.mode} onChange={(e) => handleFilter("mode", e.target.value)}>
          <option value="">All Modes</option>
          {modeOpts.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select style={inputStyle} value={filters.assigned_to} onChange={(e) => handleFilter("assigned_to", e.target.value)}>
          <option value="">All Assignees</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>{p.full_name || `${p.first_name} ${p.last_name}`}</option>
          ))}
        </select>
        <select style={inputStyle} value={filters.matter_id} onChange={(e) => handleFilter("matter_id", e.target.value)}>
          <option value="">All Matters</option>
          {matters.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={cardStyle}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: theme.text.faint, fontSize: 13 }}>Loading...</div>
        ) : error ? (
          <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
        ) : tasks.length === 0 ? (
          <EmptyState
            title="No tasks found"
            message="Adjust filters or create a new task."
            actionLabel="New Task"
            onAction={() => openDrawer("task", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={tasks}
            onRowClick={(row) => openDrawer("task", row, refetch)}
          />
        )}
      </div>
    </div>
  );
}
