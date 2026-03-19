import React, { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listTasks, getEnums } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";

/* ── Styles ──────────────────────────────────────────────────── */

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 20 };

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

/* ── Badge color maps ────────────────────────────────────────── */

const STATUS_COLORS = {
  "not started":        { bg: "#2a2a2a", text: "#9ca3af" },
  "in progress":        { bg: "#1e3a5f", text: "#60a5fa" },
  "needs review":       { bg: "#3b1f6e", text: "#a78bfa" },
  "waiting on others":  { bg: "#4a3728", text: "#fbbf24" },
  "blocked":            { bg: "#4a2020", text: "#f87171" },
  "done":               { bg: "#1a4731", text: "#34d399" },
  "completed":          { bg: "#1a4731", text: "#34d399" },
  "deferred":           { bg: "#2a2a2a", text: "#6b7280" },
};

const MODE_COLORS = {
  "action":       { bg: "#1a4731", text: "#34d399" },
  "reading":      { bg: "#1e1b4b", text: "#a78bfa" },
  "waiting":      { bg: "#4a3728", text: "#fbbf24" },
  "follow-up":    { bg: "#1a3a4a", text: "#38bdf8" },
  "delegated":    { bg: "#1e3a5f", text: "#60a5fa" },
  "quick task":   { bg: "#2a2a2a", text: "#9ca3af" },
};

const DEADLINE_COLORS = {
  "hard":  { bg: "#4a2020", text: "#f87171" },
  "soft":  { bg: "#2a2a2a", text: "#9ca3af" },
};

/* ── Helpers ─────────────────────────────────────────────────── */

function SmallBadge({ label, colorMap }) {
  if (!label) return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
  const c = colorMap?.[label.toLowerCase?.()] || colorMap?.[label] || { bg: theme.bg.input, text: theme.text.faint };
  return (
    <span style={{
      background: c.bg, color: c.text,
      padding: "2px 8px", borderRadius: 10,
      fontSize: 11, fontWeight: 500, whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

function formatDueDate(d) {
  if (!d) return "\u2014";
  const due = new Date(d);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const dueDay = new Date(due);
  dueDay.setHours(0, 0, 0, 0);
  const diffDays = Math.floor((dueDay - now) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `Overdue (${due.toLocaleDateString("en-US", { month: "short", day: "numeric" })})`;
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return due.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function isDueOverdue(d) {
  if (!d) return false;
  return new Date(d) < new Date(new Date().toDateString());
}

function isDueSoon(d) {
  if (!d) return false;
  const due = new Date(d);
  const now = new Date();
  const diffDays = (due - now) / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 2;
}

/* ── Saved views ─────────────────────────────────────────────── */

const SAVED_VIEWS = [
  {
    label: "Needs My Attention",
    filter: (t) => {
      if (t.status === "done" || t.status === "completed" || t.status === "deferred") return false;
      if (isDueOverdue(t.due_date)) return true;
      if (isDueSoon(t.due_date)) return true;
      if (t.status === "needs review") return true;
      if (t.status === "waiting on others") return true;
      if (t.priority === "critical" || t.priority === "high") return true;
      return false;
    },
  },
  { label: "My Tasks", filter: (t) => !t.delegated_by_person_id && t.status !== "done" && t.status !== "completed" && t.status !== "deferred" },
  { label: "Delegated by Me", filter: (t) => !!t.delegated_by_person_id && t.status !== "done" && t.status !== "completed" && t.status !== "deferred" },
  { label: "Waiting on Others", filter: (t) => t.status === "waiting on others" },
  {
    label: "Overdue",
    filter: (t) => isDueOverdue(t.due_date) && t.status !== "done" && t.status !== "completed" && t.status !== "deferred",
  },
  {
    label: "Due This Week",
    filter: (t) => {
      if (!t.due_date || t.status === "done" || t.status === "completed" || t.status === "deferred") return false;
      const due = new Date(t.due_date);
      const now = new Date();
      const diffDays = (due - now) / (1000 * 60 * 60 * 24);
      return diffDays >= 0 && diffDays <= 7;
    },
  },
  { label: "Needs Review", filter: (t) => t.status === "needs review" },
  {
    label: "Quick Tasks",
    filter: (t) => !t.matter_id && t.status !== "done" && t.status !== "completed" && t.status !== "deferred",
  },
];

/* ── Component ───────────────────────────────────────────────── */

export default function TasksPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [sortBy, setSortBy] = useState("due_date");
  const [activeView, setActiveView] = useState(0);

  const { data: enums } = useApi(() => getEnums(), []);
  const { data, loading, error, refetch } = useApi(
    () => listTasks({
      search,
      status: statusFilter,
      mode: modeFilter,
      exclude_done: true,
      sort_by: sortBy,
      sort_dir: sortBy === "due_date" ? "asc" : "asc",
      limit: 500,
    }),
    [search, statusFilter, modeFilter, sortBy]
  );

  const handleViewClick = useCallback((idx) => {
    setActiveView(idx);
    setStatusFilter("");
    setModeFilter("");
  }, []);

  const rawTasks = data?.items || data || [];
  const summary = data?.summary || {};

  // Apply saved-view client-side filtering
  const tasks = useMemo(() => {
    const view = SAVED_VIEWS[activeView];
    return view ? rawTasks.filter(view.filter) : rawTasks;
  }, [rawTasks, activeView]);

  const statusOpts = enums?.task_status || [];
  const modeOpts = enums?.task_mode || [];

  const columns = [
    {
      key: "title", label: "Task",
      render: (val) => (
        <span style={{ color: theme.text.primary, fontWeight: 500 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    {
      key: "matter_title", label: "Matter", width: 220,
      render: (val, row) => {
        if (!row.matter_id) {
          return <span style={{ color: theme.text.faint, fontStyle: "italic", fontSize: 12 }}>Quick task</span>;
        }
        return (
          <div>
            <span
              style={{ color: theme.accent.blueLight, cursor: "pointer", fontSize: 13 }}
              onClick={(e) => { e.stopPropagation(); navigate(`/matters/${row.matter_id}`); }}
            >
              {val || "\u2014"}
            </span>
            {row.matter_number && (
              <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>{row.matter_number}</div>
            )}
          </div>
        );
      },
    },
    {
      key: "owner_name", label: "Assigned To", width: 120,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "status", label: "Status", width: 120,
      render: (val) => <SmallBadge label={val} colorMap={STATUS_COLORS} />,
    },
    {
      key: "due_date", label: "Due Date", width: 120,
      render: (val) => {
        const overdue = isDueOverdue(val);
        const soon = isDueSoon(val);
        return (
          <span style={{
            fontSize: 12,
            color: overdue ? "#f87171" : soon ? theme.accent.yellowLight : theme.text.muted,
            fontWeight: overdue || soon ? 600 : 400,
          }}>
            {formatDueDate(val)}
          </span>
        );
      },
    },
    {
      key: "deadline_type", label: "Deadline", width: 80,
      render: (val) => val ? <SmallBadge label={val} colorMap={DEADLINE_COLORS} /> : <span style={{ color: theme.text.faint }}>{"\u2014"}</span>,
    },
    {
      key: "waiting_on_person_name", label: "Waiting On", width: 120,
      render: (val, row) => {
        const display = val || row.waiting_on_org_name || row.waiting_on_description;
        if (!display) return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
        return <span style={{ color: "#a78bfa", fontSize: 12 }}>{display}</span>;
      },
    },
    {
      key: "expected_output", label: "Expected Output", width: 220,
      render: (val) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    {
      key: "task_type", label: "Type", width: 120,
      render: (val) => <span style={{ color: theme.text.muted, fontSize: 12 }}>{val || "\u2014"}</span>,
    },
    {
      key: "task_mode", label: "Mode", width: 100,
      render: (val) => <SmallBadge label={val} colorMap={MODE_COLORS} />,
    },
  ];

  const summaryCards = [
    { label: "Due Today", value: summary.due_today ?? "\u2014" },
    { label: "Overdue", value: summary.overdue ?? "\u2014", highlight: (summary.overdue || 0) > 0 },
    { label: "Waiting on Others", value: summary.waiting_on_others ?? "\u2014" },
    { label: "Needs Review", value: summary.needs_review ?? "\u2014" },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1650 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Tasks</div>
        <div style={{ display: "flex", gap: 8 }}>
          <select style={inputStyle} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Statuses</option>
            {statusOpts.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select style={inputStyle} value={modeFilter} onChange={(e) => { setModeFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Modes</option>
            {modeOpts.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select style={inputStyle} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="due_date">Sort: Due Date</option>
            <option value="title">Sort: Title</option>
            <option value="status">Sort: Status</option>
            <option value="priority">Sort: Priority</option>
            <option value="owner_name">Sort: Assigned To</option>
            <option value="task_mode">Sort: Mode</option>
            <option value="task_type">Sort: Type</option>
          </select>
          <button style={btnPrimary} onClick={() => openDrawer("task", null, refetch)}>
            + New Task
          </button>
        </div>
      </div>
      <div style={subtitleStyle}>Execution control across your work, delegated work, and quick tasks</div>

      {/* Search + Saved View Pills */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
        <input
          style={{ ...inputStyle, minWidth: 400 }}
          placeholder="Search tasks by title, matter, assigned person, waiting on, or expected output..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {SAVED_VIEWS.map((view, i) => (
          <div
            key={view.label}
            onClick={() => handleViewClick(i)}
            style={{
              padding: "5px 12px",
              borderRadius: 16,
              fontSize: 12,
              cursor: "pointer",
              background: i === activeView ? "#1e3a5f" : theme.bg.input,
              color: i === activeView ? theme.accent.blueLight : theme.text.muted,
              border: `1px solid ${i === activeView ? theme.accent.blue : theme.border.default}`,
              fontWeight: i === activeView ? 600 : 400,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            }}
          >
            {view.label}
          </div>
        ))}
      </div>

      {/* Summary Strip */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        {summaryCards.map((card) => (
          <div key={card.label} style={{
            flex: 1,
            background: theme.bg.card,
            borderRadius: 8,
            padding: "12px 16px",
            border: `1px solid ${theme.border.default}`,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: theme.text.dim, textTransform: "uppercase", letterSpacing: "0.05em" }}>{card.label}</div>
            <div style={{
              fontSize: 22, fontWeight: 700, marginTop: 4,
              color: card.highlight ? "#f87171" : theme.text.primary,
            }}>{card.value}</div>
          </div>
        ))}
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
            message="Adjust your filters or create a new task."
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

      {/* Footer count */}
      {!loading && !error && tasks.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: theme.text.dim }}>
          Showing {tasks.length} {tasks.length !== 1 ? "tasks" : "task"}
        </div>
      )}
    </div>
  );
}
