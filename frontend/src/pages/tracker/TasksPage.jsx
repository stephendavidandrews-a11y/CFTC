import React, { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listTasks, listPeople, getEnums, updateTask, deleteTask } from "../../api/tracker";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";
import { useOwner } from "../../contexts/OwnerContext";

/* ── Styles ──────────────────────────────────────────────────── */

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
  marginBottom: 20,
};

const titleStyle = {
  fontSize: 22,
  fontWeight: 700,
  color: theme.text.primary,
  marginBottom: 4,
};
const subtitleStyle = {
  fontSize: 13,
  color: theme.text.dim,
  marginBottom: 20,
};

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

const sectionHeaderStyle = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  marginBottom: 12,
};
const sectionTitleStyle = {
  fontSize: 16,
  fontWeight: 700,
  color: theme.text.primary,
};
const sectionBadgeStyle = {
  fontSize: 11,
  fontWeight: 600,
  padding: "2px 8px",
  borderRadius: 10,
  background: theme.bg.input,
  color: theme.text.secondary,
};
const overdueBadgeStyle = {
  fontSize: 11,
  fontWeight: 600,
  padding: "2px 8px",
  borderRadius: 10,
  background: `${theme.accent.red}22`,
  color: theme.accent.red,
};

/* ── Badge color maps ────────────────────────────────────────── */

const STATUS_COLORS = {
  "not started": { bg: "#2a2a2a", text: "#9ca3af" },
  "in progress": { bg: "#1e3a5f", text: "#60a5fa" },
  "needs review": { bg: "#3b1f6e", text: "#a78bfa" },
  "waiting on others": { bg: "#4a3728", text: "#fbbf24" },
  "blocked": { bg: "#4a2020", text: "#f87171" },
  "done": { bg: "#1a4731", text: "#34d399" },
  "completed": { bg: "#1a4731", text: "#34d399" },
  "deferred": { bg: "#2a2a2a", text: "#6b7280" },
};

const PRIORITY_COLORS = {
  critical: { bg: "#4a2020", text: "#f87171" },
  high: { bg: "#4a3728", text: "#fbbf24" },
  medium: { bg: "#1e3a5f", text: "#60a5fa" },
  low: { bg: "#2a2a2a", text: "#9ca3af" },
};

const DEADLINE_COLORS = {
  hard: { bg: "#4a2020", text: "#f87171" },
  soft: { bg: "#2a2a2a", text: "#9ca3af" },
};

/* ── Helpers ─────────────────────────────────────────────────── */

function SmallBadge({ label, colorMap }) {
  if (!label)
    return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
  const c = colorMap?.[label.toLowerCase?.()] ||
    colorMap?.[label] || { bg: theme.bg.input, text: theme.text.faint };
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        padding: "2px 8px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 500,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

const actionBtnStyle = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: "4px 6px",
  borderRadius: 4,
  fontSize: 14,
  lineHeight: 1,
  transition: "background 0.15s",
};

function safeDate(d) {
  if (!d) return null;
  const val =
    typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val);
}

function formatDueDate(d) {
  if (!d) return "\u2014";
  const due = safeDate(d);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const dueDay = new Date(due);
  dueDay.setHours(0, 0, 0, 0);
  const diffDays = Math.floor((dueDay - now) / (1000 * 60 * 60 * 24));
  if (diffDays < 0)
    return `Overdue (${due.toLocaleDateString("en-US", { month: "short", day: "numeric" })})`;
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return due.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function isDueOverdue(d) {
  if (!d) return false;
  return safeDate(d) < new Date(new Date().toDateString());
}

function isDueSoon(d) {
  if (!d) return false;
  const due = safeDate(d);
  const now = new Date();
  const diffDays = (due - now) / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 2;
}

function isActive(t) {
  return (
    t.status !== "done" &&
    t.status !== "completed" &&
    t.status !== "deferred"
  );
}

function daysWaiting(t) {
  if (!t.created_at) return "\u2014";
  const created = safeDate(t.created_at);
  if (!created) return "\u2014";
  const days = Math.floor((new Date() - created) / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

/* ── Saved views (flat-table mode) ───────────────────────────── */

const SAVED_VIEWS = [
  { label: "All Active", filter: null },
  {
    label: "Needs My Attention",
    filter: (t, ownerId) => {
      if (!isActive(t)) return false;
      if (isDueOverdue(t.due_date)) return true;
      if (isDueSoon(t.due_date)) return true;
      if (t.status === "needs review") return true;
      if (t.priority === "critical" || t.priority === "high") return true;
      return false;
    },
  },
  {
    label: "Overdue",
    filter: (t) => isActive(t) && isDueOverdue(t.due_date),
  },
  {
    label: "Due This Week",
    filter: (t) => {
      if (!t.due_date || !isActive(t)) return false;
      const due = safeDate(t.due_date);
      const diffDays = (due - new Date()) / (1000 * 60 * 60 * 24);
      return diffDays >= 0 && diffDays <= 7;
    },
  },
  { label: "Needs Review", filter: (t) => t.status === "needs review" },
  {
    label: "Quick Tasks",
    filter: (t) => !t.matter_id && isActive(t),
  },
];

/* ── Shared column builders ──────────────────────────────────── */

function dueDateColumn(navigate) {
  return {
    key: "due_date",
    label: "Due Date",
    width: 120,
    render: (val) => {
      const overdue = isDueOverdue(val);
      const soon = isDueSoon(val);
      return (
        <span
          style={{
            fontSize: 12,
            color: overdue
              ? "#f87171"
              : soon
                ? theme.accent.yellowLight
                : theme.text.muted,
            fontWeight: overdue || soon ? 600 : 400,
          }}
        >
          {formatDueDate(val)}
        </span>
      );
    },
  };
}

function matterColumn(navigate) {
  return {
    key: "matter_title",
    label: "Matter",
    width: 200,
    render: (val, row) => {
      if (!row.matter_id) {
        return (
          <span
            style={{
              color: theme.text.faint,
              fontStyle: "italic",
              fontSize: 12,
            }}
          >
            Quick task
          </span>
        );
      }
      return (
        <span
          style={{
            color: theme.accent.blueLight,
            cursor: "pointer",
            fontSize: 13,
          }}
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/matters/${row.matter_id}`);
          }}
        >
          {val || "\u2014"}
        </span>
      );
    },
  };
}

function statusColumn() {
  return {
    key: "status",
    label: "Status",
    width: 120,
    render: (val) => <SmallBadge label={val} colorMap={STATUS_COLORS} />,
  };
}

function priorityColumn() {
  return {
    key: "priority",
    label: "Priority",
    width: 80,
    render: (val) =>
      val ? (
        <SmallBadge label={val} colorMap={PRIORITY_COLORS} />
      ) : (
        <span style={{ color: theme.text.faint }}>{"\u2014"}</span>
      ),
  };
}

function taskTitleColumn() {
  return {
    key: "title",
    label: "Task",
    render: (val) => (
      <span style={{ color: theme.text.primary, fontWeight: 500 }}>
        {val || "\u2014"}
      </span>
    ),
  };
}

/* ── Component ───────────────────────────────────────────────── */

export default function TasksPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const { ownerId } = useOwner();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [activeView, setActiveView] = useState(0);
  const [confirmAction, setConfirmAction] = useState(null); // { id, action, title }
  const [actionBusy, setActionBusy] = useState({});

  const { data: enums } = useApi(() => getEnums(), []);
  const { data: taskData, loading: loadingTasks, error, refetch } = useApi(
    () =>
      listTasks({
        search,
        status: statusFilter,
        mode: modeFilter,
        exclude_done: true,
        sort_by: "due_date",
        sort_dir: "asc",
        limit: 500,
      }),
    [search, statusFilter, modeFilter]
  );
  const { data: peopleData, loading: loadingPeople } = useApi(
    () => listPeople({ limit: 500, is_active: true }),
    []
  );

  const loading = loadingTasks || loadingPeople;

  const handleViewClick = useCallback((idx) => {
    setActiveView(idx);
    setStatusFilter("");
    setModeFilter("");
  }, []);

  const handleTaskAction = useCallback(
    async (id, action) => {
      setActionBusy((prev) => ({ ...prev, [id]: true }));
      try {
        if (action === "defer") {
          await updateTask(id, { status: "deferred" });
        } else if (action === "delete") {
          await deleteTask(id);
        }
        setConfirmAction(null);
        refetch();
      } catch (err) {
        console.error(`Task ${action} failed:`, err);
        alert(`Failed to ${action} task: ${err.message || err}`);
      } finally {
        setActionBusy((prev) => ({ ...prev, [id]: false }));
      }
    },
    [refetch]
  );

  const rawTasks = taskData?.items || taskData || [];
  const summary = taskData?.summary || {};

  // Build name lookup from people
  const nameMap = useMemo(() => {
    const people = peopleData?.items || peopleData || [];
    const map = {};
    for (const p of people) {
      map[p.id] = p.full_name || `${p.first_name || ""} ${p.last_name || ""}`.trim();
    }
    return map;
  }, [peopleData]);

  // Build manager lookup
  const managerMap = useMemo(() => {
    const people = peopleData?.items || peopleData || [];
    const map = {};
    for (const p of people) {
      map[p.id] = p.manager_person_id;
    }
    return map;
  }, [peopleData]);

  // ── Section grouping ──
  const {
    myTasks,
    delegatedGroups,
    waitingTasks,
    teamGroups,
    myOverdue,
    teamOverdue,
    blockedCount,
    dueToday,
  } = useMemo(() => {
    const activeTasks = rawTasks.filter(isActive);

    // If no ownerId yet, put everything in "my tasks"
    const me = ownerId;

    // Section 1: My Action Items
    // Tasks assigned to me (or unassigned)
    const _myTasks = activeTasks
      .filter((t) => {
        if (!me) return true; // fallback if no owner configured
        const assignedToMe =
          t.assigned_to_person_id === me || !t.assigned_to_person_id;
        return assignedToMe;
      })
      .sort((a, b) => {
        // Overdue first, then by due date
        const aOver = isDueOverdue(a.due_date) ? 0 : 1;
        const bOver = isDueOverdue(b.due_date) ? 0 : 1;
        if (aOver !== bOver) return aOver - bOver;
        const aD = safeDate(a.due_date)?.getTime() || Infinity;
        const bD = safeDate(b.due_date)?.getTime() || Infinity;
        return aD - bD;
      });

    // Section 2: Assigned Work
    // Tasks where I delegated (delegated_by = me) or action tasks assigned to others
    const delegatedTasks = activeTasks.filter((t) => {
      if (!me) return false;
      return (
        (t.delegated_by_person_id === me &&
          t.assigned_to_person_id !== me) ||
        (t.assigned_to_person_id &&
          t.assigned_to_person_id !== me &&
          t.supervising_person_id === me)
      );
    });

    // Group delegated tasks by assignee, then sub-group by manager chain
    const byAssignee = {};
    for (const t of delegatedTasks) {
      const aid = t.assigned_to_person_id || "unassigned";
      if (!byAssignee[aid]) byAssignee[aid] = [];
      byAssignee[aid].push(t);
    }

    // Build groups: direct reports first, then sub-manager teams
    const _delegatedGroups = [];
    const processedAssignees = new Set();

    // Find direct reports (manager = owner)
    const directReportIds = Object.keys(byAssignee).filter(
      (aid) => managerMap[aid] === me
    );

    // Find sub-managers among direct reports who also manage other assignees
    const subManagerIds = new Set();
    for (const aid of Object.keys(byAssignee)) {
      const mgr = managerMap[aid];
      if (mgr && mgr !== me && directReportIds.includes(mgr)) {
        subManagerIds.add(mgr);
      }
    }

    // Direct reports' own tasks (not sub-managers' reports)
    for (const aid of directReportIds) {
      const name = nameMap[aid] || "Unknown";
      const tasks = byAssignee[aid] || [];
      tasks.sort(
        (a, b) =>
          (safeDate(a.due_date)?.getTime() || Infinity) -
          (safeDate(b.due_date)?.getTime() || Infinity)
      );

      // If this person is a sub-manager, include their reports' tasks in their group
      if (subManagerIds.has(aid)) {
        const subTasks = [];
        for (const [subAid, subTaskList] of Object.entries(byAssignee)) {
          if (managerMap[subAid] === aid) {
            for (const st of subTaskList) {
              subTasks.push({ ...st, _subAssignee: nameMap[subAid] || subAid });
            }
            processedAssignees.add(subAid);
          }
        }
        subTasks.sort(
          (a, b) =>
            (safeDate(a.due_date)?.getTime() || Infinity) -
            (safeDate(b.due_date)?.getTime() || Infinity)
        );

        _delegatedGroups.push({
          key: aid,
          title: `${name.split(" ")[0]}'s Group`,
          rows: [...tasks, ...subTasks],
          overdue: [...tasks, ...subTasks].filter((t) =>
            isDueOverdue(t.due_date)
          ).length,
        });
      } else {
        _delegatedGroups.push({
          key: aid,
          title: name,
          rows: tasks,
          overdue: tasks.filter((t) => isDueOverdue(t.due_date)).length,
        });
      }
      processedAssignees.add(aid);
    }

    // Remaining assignees not yet grouped
    for (const [aid, tasks] of Object.entries(byAssignee)) {
      if (processedAssignees.has(aid)) continue;
      const name = aid === "unassigned" ? "Unassigned" : nameMap[aid] || "Unknown";
      tasks.sort(
        (a, b) =>
          (safeDate(a.due_date)?.getTime() || Infinity) -
          (safeDate(b.due_date)?.getTime() || Infinity)
      );
      _delegatedGroups.push({
        key: aid,
        title: name,
        rows: tasks,
        overdue: tasks.filter((t) => isDueOverdue(t.due_date)).length,
      });
      processedAssignees.add(aid);
    }

    // Sort groups: most overdue first
    _delegatedGroups.sort(
      (a, b) => b.overdue - a.overdue || a.title.localeCompare(b.title)
    );

    // Section 3: Follow-Ups
    const _waitingTasks = activeTasks
      .filter((t) => {
        if (!me) return t.task_mode === "follow_up";
        return (
          t.task_mode === "follow_up" ||
          (t.status === "waiting on others" &&
            t.assigned_to_person_id === me)
        );
      })
      // Don't double-count: remove tasks already in "my tasks" section
      .filter(
        (t) =>
          !_myTasks.some((mt) => mt.id === t.id)
      )
      .sort(
        (a, b) =>
          (safeDate(a.due_date)?.getTime() || Infinity) -
          (safeDate(b.due_date)?.getTime() || Infinity)
      );

    // Section 4: Team Tasks (catch-all for tasks not in any other section)
    const claimedIds = new Set([
      ..._myTasks.map((t) => t.id),
      ...delegatedTasks.map((t) => t.id),
      ..._waitingTasks.map((t) => t.id),
    ]);
    const _teamTasks = activeTasks
      .filter((t) => !claimedIds.has(t.id))
      .sort((a, b) => {
        const aOver = isDueOverdue(a.due_date) ? 0 : 1;
        const bOver = isDueOverdue(b.due_date) ? 0 : 1;
        if (aOver !== bOver) return aOver - bOver;
        const aD = safeDate(a.due_date)?.getTime() || Infinity;
        const bD = safeDate(b.due_date)?.getTime() || Infinity;
        return aD - bD;
      });

    // Group team tasks by assignee
    const _teamGroups = [];
    const teamByAssignee = {};
    for (const t of _teamTasks) {
      const aid = t.assigned_to_person_id || "unassigned";
      if (!teamByAssignee[aid]) teamByAssignee[aid] = [];
      teamByAssignee[aid].push(t);
    }
    for (const [aid, tasks] of Object.entries(teamByAssignee)) {
      const name = aid === "unassigned" ? "Unassigned" : nameMap[aid] || "Unknown";
      _teamGroups.push({
        key: aid,
        title: name,
        rows: tasks,
        overdue: tasks.filter((t) => isDueOverdue(t.due_date)).length,
      });
    }
    _teamGroups.sort(
      (a, b) => b.overdue - a.overdue || a.title.localeCompare(b.title)
    );

    // Stats
    const _myOverdue = _myTasks.filter((t) =>
      isDueOverdue(t.due_date)
    ).length;
    const _teamOverdue = [...delegatedTasks, ..._teamTasks].filter((t) =>
      isDueOverdue(t.due_date)
    ).length;
    const _blockedCount = _waitingTasks.length;
    const _dueToday = activeTasks.filter((t) => {
      if (!t.due_date) return false;
      const d = safeDate(t.due_date);
      const now = new Date();
      return (
        d.getFullYear() === now.getFullYear() &&
        d.getMonth() === now.getMonth() &&
        d.getDate() === now.getDate()
      );
    }).length;

    return {
      myTasks: _myTasks,
      delegatedGroups: _delegatedGroups,
      waitingTasks: _waitingTasks,
      teamGroups: _teamGroups,
      myOverdue: _myOverdue,
      teamOverdue: _teamOverdue,
      blockedCount: _blockedCount,
      dueToday: _dueToday,
    };
  }, [rawTasks, ownerId, nameMap, managerMap]);

  // When a saved view is active (not "All Active"), show flat table
  const isGroupedMode = activeView === 0;

  const filteredTasks = useMemo(() => {
    if (isGroupedMode) return null; // grouped mode, don't need flat list
    const view = SAVED_VIEWS[activeView];
    if (!view?.filter) return rawTasks.filter(isActive);
    return rawTasks.filter((t) => view.filter(t, ownerId));
  }, [rawTasks, activeView, ownerId, isGroupedMode]);

  const statusOpts = enums?.task_status || [];
  const modeOpts = enums?.task_mode || [];

  // ── Action column ──
  const actionsCol = {
    key: "_actions",
    label: "",
    width: 70,
    sortable: false,
    render: (_val, row) => (
      <div
        style={{ display: "flex", gap: 2 }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          title="Defer task"
          style={{ ...actionBtnStyle, color: theme.text.muted }}
          disabled={actionBusy[row.id]}
          onClick={() =>
            setConfirmAction({
              id: row.id,
              action: "defer",
              title: row.title,
            })
          }
          onMouseEnter={(e) =>
            (e.target.style.background = theme.bg.input)
          }
          onMouseLeave={(e) =>
            (e.target.style.background = "transparent")
          }
        >
          ⏸
        </button>
        <button
          title="Delete task"
          style={{ ...actionBtnStyle, color: theme.accent.red }}
          disabled={actionBusy[row.id]}
          onClick={() =>
            setConfirmAction({
              id: row.id,
              action: "delete",
              title: row.title,
            })
          }
          onMouseEnter={(e) =>
            (e.target.style.background = `${theme.accent.red}22`)
          }
          onMouseLeave={(e) =>
            (e.target.style.background = "transparent")
          }
        >
          ✕
        </button>
      </div>
    ),
  };

  // ── Column definitions ──

  const myColumns = [
    taskTitleColumn(),
    matterColumn(navigate),
    statusColumn(),
    priorityColumn(),
    dueDateColumn(navigate),
    {
      key: "deadline_type",
      label: "Deadline",
      width: 80,
      render: (val) =>
        val ? (
          <SmallBadge label={val} colorMap={DEADLINE_COLORS} />
        ) : (
          <span style={{ color: theme.text.faint }}>{"\u2014"}</span>
        ),
    },
    {
      key: "expected_output",
      label: "Expected Output",
      width: 200,
      render: (val) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    actionsCol,
  ];

  const delegatedColumns = [
    taskTitleColumn(),
    {
      key: "owner_name",
      label: "Assignee",
      width: 130,
      render: (val, row) => (
        <span style={{ color: theme.accent.blueLight, fontSize: 13 }}>
          {row._subAssignee || val || "\u2014"}
        </span>
      ),
    },
    matterColumn(navigate),
    statusColumn(),
    dueDateColumn(navigate),
    {
      key: "expected_output",
      label: "Expected Output",
      width: 200,
      render: (val) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    actionsCol,
  ];

  const waitingColumns = [
    taskTitleColumn(),
    {
      key: "waiting_on_person_name",
      label: "Waiting On",
      width: 160,
      render: (val, row) => {
        const display =
          val || row.waiting_on_org_name || row.waiting_on_description;
        if (!display)
          return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
        return (
          <span style={{ color: "#a78bfa", fontSize: 13 }}>{display}</span>
        );
      },
    },
    matterColumn(navigate),
    dueDateColumn(navigate),
    {
      key: "created_at",
      label: "Days Waiting",
      width: 100,
      render: (_val, row) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {daysWaiting(row)}
        </span>
      ),
    },
    {
      key: "expected_output",
      label: "Expected Output",
      width: 200,
      render: (val) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    actionsCol,
  ];

  // Flat-mode columns (when a saved view is active)
  const flatColumns = [
    taskTitleColumn(),
    matterColumn(navigate),
    {
      key: "owner_name",
      label: "Assigned To",
      width: 120,
      render: (val) => (
        <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>
      ),
    },
    statusColumn(),
    dueDateColumn(navigate),
    priorityColumn(),
    {
      key: "task_mode",
      label: "Mode",
      width: 90,
      render: (val) => (
        <SmallBadge
          label={val}
          colorMap={{
            action: { bg: "#1a4731", text: "#34d399" },
            follow_up: { bg: "#4a3728", text: "#fbbf24" },
            monitoring: { bg: "#1a3a4a", text: "#38bdf8" },
          }}
        />
      ),
    },
    {
      key: "expected_output",
      label: "Expected Output",
      width: 200,
      render: (val) => (
        <span style={{ color: theme.text.muted, fontSize: 12 }}>
          {val || "\u2014"}
        </span>
      ),
    },
    actionsCol,
  ];

  if (loading) {
    return (
      <div
        style={{
          padding: "60px 32px",
          textAlign: "center",
          color: theme.text.faint,
        }}
      >
        Loading tasks&hellip;
      </div>
    );
  }

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1650 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 4,
        }}
      >
        <div style={titleStyle}>Tasks</div>
        <div style={{ display: "flex", gap: 8 }}>
          <select
            style={inputStyle}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setActiveView(0);
            }}
          >
            <option value="">All Statuses</option>
            {statusOpts.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <select
            style={inputStyle}
            value={modeFilter}
            onChange={(e) => {
              setModeFilter(e.target.value);
              setActiveView(0);
            }}
          >
            <option value="">All Modes</option>
            {modeOpts.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <button
            style={btnPrimary}
            onClick={() => openDrawer("task", null, refetch)}
          >
            + New Task
          </button>
        </div>
      </div>
      <div style={subtitleStyle}>
        Execution control across your work, assigned work, and follow-ups
      </div>

      {/* Search + Saved View Pills */}
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          marginBottom: 16,
          alignItems: "center",
        }}
      >
        <input
          style={{ ...inputStyle, minWidth: 400 }}
          placeholder="Search tasks by title, matter, assigned person, or expected output..."
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
              color:
                i === activeView
                  ? theme.accent.blueLight
                  : theme.text.muted,
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
        {[
          {
            label: "My Overdue",
            value: myOverdue,
            highlight: myOverdue > 0,
          },
          {
            label: "Team Overdue",
            value: teamOverdue,
            highlight: teamOverdue > 0,
          },
          { label: "Blocked / Waiting", value: blockedCount },
          { label: "Due Today", value: dueToday },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              flex: 1,
              background: theme.bg.card,
              borderRadius: 8,
              padding: "12px 16px",
              border: `1px solid ${theme.border.default}`,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: theme.text.dim,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {card.label}
            </div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                marginTop: 4,
                color: card.highlight ? "#f87171" : theme.text.primary,
              }}
            >
              {card.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Grouped Mode (default) ── */}
      {isGroupedMode && (
        <>
          {/* Section 1: My Action Items */}
          {myTasks.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionHeaderStyle}>
                <div style={sectionTitleStyle}>My Action Items</div>
                <div style={sectionBadgeStyle}>
                  {myTasks.length} task{myTasks.length !== 1 ? "s" : ""}
                </div>
                {myOverdue > 0 && (
                  <div style={overdueBadgeStyle}>
                    {myOverdue} overdue
                  </div>
                )}
              </div>
              <DataTable
                columns={myColumns}
                data={myTasks}
                onRowClick={(row) => openDrawer("task", row, refetch)}
                pageSize={15}
                emptyMessage="No action items."
              />
            </div>
          )}

          {/* Section 2: Assigned Work */}
          {delegatedGroups.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 700,
                  color: theme.text.dim,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 12,
                }}
              >
                Assigned Work
              </div>
              {delegatedGroups.map((group) => (
                <div key={group.key} style={cardStyle}>
                  <div style={sectionHeaderStyle}>
                    <div style={sectionTitleStyle}>{group.title}</div>
                    <div style={sectionBadgeStyle}>
                      {group.rows.length} task
                      {group.rows.length !== 1 ? "s" : ""}
                    </div>
                    {group.overdue > 0 && (
                      <div style={overdueBadgeStyle}>
                        {group.overdue} overdue
                      </div>
                    )}
                  </div>
                  <DataTable
                    columns={delegatedColumns}
                    data={group.rows}
                    onRowClick={(row) => openDrawer("task", row, refetch)}
                    pageSize={10}
                    emptyMessage="No assigned tasks."
                  />
                </div>
              ))}
            </div>
          )}

          {/* Section 3: Waiting On */}
          {waitingTasks.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionHeaderStyle}>
                <div style={sectionTitleStyle}>Follow-Ups</div>
                <div style={sectionBadgeStyle}>
                  {waitingTasks.length} task
                  {waitingTasks.length !== 1 ? "s" : ""}
                </div>
              </div>
              <DataTable
                columns={waitingColumns}
                data={waitingTasks}
                onRowClick={(row) => openDrawer("task", row, refetch)}
                pageSize={10}
                emptyMessage="Nothing pending."
              />
            </div>
          )}

          {/* Empty state if all sections empty */}
          {/* Section 4: Team Tasks */}
          {teamGroups.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
                <div style={sectionTitleStyle}>Team Tasks</div>
                <span style={{ fontSize: 13, color: theme.text.faint }}>
                  {teamGroups.reduce((s, g) => s + g.rows.length, 0)} task
                  {teamGroups.reduce((s, g) => s + g.rows.length, 0) !== 1 ? "s" : ""}
                </span>
              </div>
              {teamGroups.map((group) => (
                <div key={group.key} style={{ marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: theme.text.muted,
                      marginBottom: 6,
                      display: "flex",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>{group.title}</span>
                    <span style={{ fontWeight: 400, fontSize: 12 }}>
                      {group.rows.length} task{group.rows.length !== 1 ? "s" : ""}
                      {group.overdue > 0 && (
                        <span style={{ color: "#f87171", marginLeft: 8 }}>
                          {group.overdue} overdue
                        </span>
                      )}
                    </span>
                  </div>
                  <DataTable
                    data={group.rows}
                    columns={delegatedColumns}
                    onRowClick={(row) => openDrawer("task", row, refetch)}
                    compact
                  />
                </div>
              ))}
            </div>
          )}

          {myTasks.length === 0 &&
            delegatedGroups.length === 0 &&
            waitingTasks.length === 0 &&
            teamGroups.length === 0 && (
              <div style={cardStyle}>
                <EmptyState
                  title="No active tasks"
                  message="All clear! Create a new task or upload a recording."
                  actionLabel="New Task"
                  onAction={() => openDrawer("task", null, refetch)}
                />
              </div>
            )}
        </>
      )}

      {/* ── Flat Table Mode (saved view active) ── */}
      {!isGroupedMode && (
        <div style={cardStyle}>
          {error ? (
            <div style={{ color: theme.accent.red, fontSize: 13 }}>
              Error: {error.message || String(error)}
            </div>
          ) : filteredTasks && filteredTasks.length === 0 ? (
            <EmptyState
              title="No tasks found"
              message="Adjust your filters or create a new task."
              actionLabel="New Task"
              onAction={() => openDrawer("task", null, refetch)}
            />
          ) : (
            <DataTable
              columns={flatColumns}
              data={filteredTasks || []}
              onRowClick={(row) => openDrawer("task", row, refetch)}
              pageSize={25}
              emptyMessage="No tasks found."
            />
          )}
        </div>
      )}

      {/* Confirm dialog */}
      {confirmAction && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
          onClick={() => setConfirmAction(null)}
        >
          <div
            style={{
              background: theme.bg.card,
              border: `1px solid ${theme.border.default}`,
              borderRadius: 10,
              padding: 24,
              minWidth: 340,
              maxWidth: 440,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                color: theme.text.primary,
                marginBottom: 12,
              }}
            >
              {confirmAction.action === "defer"
                ? "Defer Task?"
                : "Delete Task?"}
            </div>
            <div
              style={{
                fontSize: 13,
                color: theme.text.muted,
                marginBottom: 20,
                lineHeight: 1.5,
              }}
            >
              {confirmAction.action === "defer" ? (
                <>
                  This will mark{" "}
                  <strong style={{ color: theme.text.secondary }}>
                    {confirmAction.title}
                  </strong>{" "}
                  as deferred. You can reactivate it later.
                </>
              ) : (
                <>
                  This will permanently delete{" "}
                  <strong style={{ color: theme.text.secondary }}>
                    {confirmAction.title}
                  </strong>
                  . This cannot be undone.
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                style={{
                  ...btnPrimary,
                  background: theme.bg.input,
                  color: theme.text.muted,
                }}
                onClick={() => setConfirmAction(null)}
              >
                Cancel
              </button>
              <button
                style={{
                  ...btnPrimary,
                  background:
                    confirmAction.action === "delete"
                      ? theme.accent.red
                      : theme.accent.blue,
                }}
                disabled={actionBusy[confirmAction.id]}
                onClick={() =>
                  handleTaskAction(confirmAction.id, confirmAction.action)
                }
              >
                {actionBusy[confirmAction.id]
                  ? "..."
                  : confirmAction.action === "defer"
                    ? "Defer"
                    : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer count */}
      {!loading && !error && (
        <div style={{ marginTop: 12, fontSize: 12, color: theme.text.dim }}>
          {isGroupedMode
            ? `${myTasks.length} personal + ${delegatedGroups.reduce((s, g) => s + g.rows.length, 0)} assigned + ${teamGroups.reduce((s, g) => s + g.rows.length, 0)} team + ${waitingTasks.length} follow-ups`
            : `Showing ${(filteredTasks || []).length} task${(filteredTasks || []).length !== 1 ? "s" : ""}`}
        </div>
      )}
    </div>
  );
}
