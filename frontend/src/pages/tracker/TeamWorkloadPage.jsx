import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listPeople, listTasks } from "../../api/tracker";
import StatCard from "../../components/shared/StatCard";
import DataTable from "../../components/shared/DataTable";

/* ── styles ────────────────────────────────────────────────────────────── */

const titleStyle = {
  fontSize: 22,
  fontWeight: 700,
  color: theme.text.primary,
  marginBottom: 4,
};
const subtitleStyle = {
  fontSize: 13,
  color: theme.text.dim,
  marginBottom: 24,
};
const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
  marginBottom: 20,
};
const groupHeaderStyle = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  marginBottom: 12,
};
const groupTitleStyle = {
  fontSize: 16,
  fontWeight: 700,
  color: theme.text.primary,
};
const groupBadgeStyle = {
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

/* ── helpers ───────────────────────────────────────────────────────────── */

function LoadBar({ active, overdue, max }) {
  const pct = max > 0 ? Math.min((active / max) * 100, 100) : 0;
  const color =
    overdue > 3
      ? theme.accent.red
      : overdue > 0
        ? theme.accent.yellow
        : active > 7
          ? theme.accent.yellow
          : theme.accent.blue;
  return (
    <div
      style={{
        width: 80,
        height: 6,
        borderRadius: 3,
        background: theme.bg.input,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: 3,
          background: color,
          transition: "width 0.3s ease",
        }}
      />
    </div>
  );
}

function buildRow(person, tasks, now) {
  const personTasks = tasks.filter(
    (t) =>
      t.assigned_to_person_id === person.id &&
      t.status !== "done" &&
      t.status !== "completed" &&
      t.status !== "deferred"
  );
  const overdue = personTasks.filter((t) => {
    if (!t.due_date) return false;
    const d =
      typeof t.due_date === "string" && t.due_date.length === 10
        ? new Date(t.due_date + "T12:00:00")
        : new Date(t.due_date);
    return d < now;
  });

  const safeD = (d) =>
    typeof d === "string" && d.length === 10 ? new Date(d + "T12:00:00") : new Date(d);
  const urgentTask = personTasks
    .filter((t) => t.due_date)
    .sort((a, b) => safeD(a.due_date) - safeD(b.due_date))[0];

  return {
    id: person.id,
    name:
      person.full_name ||
      `${person.first_name || ""} ${person.last_name || ""}`.trim(),
    title: person.title || "\u2014",
    org_name:
      person.org_short_name ||
      person.org_name ||
      person.organization_name ||
      "\u2014",
    activeTasks: personTasks.length,
    overdueTasks: overdue.length,
    atRiskMatter: urgentTask?.matter_title || null,
    atRiskMatterId: urgentTask?.matter_id || null,
    manager_person_id: person.manager_person_id,
  };
}

/* ── main component ────────────────────────────────────────────────────── */

export default function TeamWorkloadPage() {
  const navigate = useNavigate();

  const { data: peopleData, loading: loadingPeople } = useApi(
    () => listPeople({ limit: 500, is_active: true }),
    []
  );
  const { data: tasksData, loading: loadingTasks } = useApi(
    () => listTasks({ limit: 2000 }),
    []
  );

  const loading = loadingPeople || loadingTasks;

  const {
    groups,
    globalMaxActive,
    totalOverdue,
    membersWithOverdue,
    totalMembers,
  } = useMemo(() => {
    const people = peopleData?.items || peopleData || [];
    const tasks = tasksData?.items || tasksData || [];
    const team = people.filter(
      (p) =>
        p.include_in_team_workload === 1 || p.include_in_team_workload === true
    );
    const now = new Date();

    // Build rows for everyone on the team
    const allRows = team.map((p) => buildRow(p, tasks, now));

    // Build a name lookup for all people (managers might not be on the team)
    const nameMap = {};
    for (const p of people) {
      nameMap[p.id] =
        p.full_name ||
        `${p.first_name || ""} ${p.last_name || ""}`.trim();
    }

    // Find the owner — the common manager of "Direct report" people
    const directReports = team.filter(
      (p) => p.relationship_category === "Direct report"
    );
    const ownerIds = [
      ...new Set(
        directReports.map((p) => p.manager_person_id).filter(Boolean)
      ),
    ];
    const ownerId = ownerIds[0] || null;

    // Group 1: Direct Reports (manager = owner)
    const directRows = allRows.filter(
      (r) => r.manager_person_id === ownerId
    );
    directRows.sort(
      (a, b) =>
        b.overdueTasks - a.overdueTasks || b.activeTasks - a.activeTasks
    );

    // Find sub-managers: people who manage indirect reports
    const subManagerIds = new Set();
    for (const r of allRows) {
      if (r.manager_person_id && r.manager_person_id !== ownerId) {
        subManagerIds.add(r.manager_person_id);
      }
    }

    // Build sub-groups for each sub-manager
    const subGroups = [];
    for (const mgrId of subManagerIds) {
      const mgrName = nameMap[mgrId] || "Unknown";
      const mgrFirstName = mgrName.split(" ")[0];
      const subRows = allRows.filter((r) => r.manager_person_id === mgrId);
      subRows.sort(
        (a, b) =>
          b.overdueTasks - a.overdueTasks || b.activeTasks - a.activeTasks
      );
      const groupOverdue = subRows.reduce((s, r) => s + r.overdueTasks, 0);
      subGroups.push({
        key: mgrId,
        title: `${mgrFirstName}\u2019s Team`,
        managerId: mgrId,
        managerName: mgrName,
        rows: subRows,
        overdue: groupOverdue,
      });
    }
    // Sort sub-groups: most overdue first, then alphabetical
    subGroups.sort(
      (a, b) => b.overdue - a.overdue || a.title.localeCompare(b.title)
    );

    // Catch-all: team members with no manager or whose manager isn't the owner or a sub-manager
    const assignedIds = new Set([
      ...directRows.map((r) => r.id),
      ...subGroups.flatMap((g) => g.rows.map((r) => r.id)),
    ]);
    const unassignedRows = allRows.filter((r) => !assignedIds.has(r.id));
    unassignedRows.sort(
      (a, b) =>
        b.overdueTasks - a.overdueTasks || b.activeTasks - a.activeTasks
    );

    const directGroupOverdue = directRows.reduce(
      (s, r) => s + r.overdueTasks,
      0
    );
    const unassignedOverdue = unassignedRows.reduce(
      (s, r) => s + r.overdueTasks,
      0
    );
    const _groups = [
      {
        key: "direct",
        title: "Your Direct Reports",
        managerId: ownerId,
        managerName: nameMap[ownerId] || "You",
        rows: directRows,
        overdue: directGroupOverdue,
      },
      ...subGroups,
      ...(unassignedRows.length > 0
        ? [
            {
              key: "unassigned",
              title: "Unassigned",
              managerId: null,
              managerName: null,
              rows: unassignedRows,
              overdue: unassignedOverdue,
            },
          ]
        : []),
    ].filter((g) => g.rows.length > 0);

    const _totalOverdue = allRows.reduce((s, r) => s + r.overdueTasks, 0);
    const _membersWithOverdue = allRows.filter(
      (r) => r.overdueTasks > 0
    ).length;
    const _globalMax = allRows.reduce(
      (mx, r) => Math.max(mx, r.activeTasks),
      1
    );

    return {
      groups: _groups,
      globalMaxActive: _globalMax,
      totalOverdue: _totalOverdue,
      membersWithOverdue: _membersWithOverdue,
      totalMembers: allRows.length,
    };
  }, [peopleData, tasksData]);

  if (loading) {
    return (
      <div
        style={{
          padding: "60px 32px",
          textAlign: "center",
          color: theme.text.faint,
        }}
      >
        Loading team workload&hellip;
      </div>
    );
  }

  const columns = [
    {
      key: "name",
      label: "Name",
      width: "24%",
      render: (val) => (
        <span
          style={{
            color: theme.accent.blueLight,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {val}
        </span>
      ),
    },
    { key: "title", label: "Title", width: "20%" },
    {
      key: "activeTasks",
      label: "Active Tasks",
      width: "12%",
      render: (val) => (
        <span
          style={{
            fontWeight: 600,
            color: val > 0 ? theme.text.secondary : theme.text.ghost,
          }}
        >
          {val}
        </span>
      ),
    },
    {
      key: "overdueTasks",
      label: "Overdue",
      width: "10%",
      render: (val) => (
        <span
          style={{
            fontWeight: val > 0 ? 700 : 400,
            color: val > 0 ? theme.accent.red : theme.text.ghost,
          }}
        >
          {val}
        </span>
      ),
    },
    {
      key: "atRiskMatter",
      label: "At-Risk Matter",
      width: "22%",
      sortable: false,
      render: (val, row) =>
        val ? (
          <span
            onClick={(e) => {
              e.stopPropagation();
              if (row.atRiskMatterId)
                navigate(`/matters/${row.atRiskMatterId}`);
            }}
            style={{
              fontSize: 12,
              color: theme.accent.yellow,
              cursor: "pointer",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "block",
              maxWidth: 200,
            }}
            title={val}
          >
            {val}
          </span>
        ) : (
          <span style={{ color: theme.text.ghost }}>&mdash;</span>
        ),
    },
    {
      key: "load",
      label: "Load",
      width: "12%",
      sortable: false,
      render: (_val, row) => (
        <LoadBar
          active={row.activeTasks}
          overdue={row.overdueTasks}
          max={globalMaxActive}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Team Workload</div>
      <div style={subtitleStyle}>
        Management view &mdash; grouped by reporting chain
      </div>

      {/* ── Summary stats ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <StatCard
          value={totalMembers}
          label="Team Members"
          accent={theme.accent.blue}
        />
        <StatCard
          value={totalOverdue}
          label="Total Overdue Tasks"
          accent={totalOverdue > 0 ? theme.accent.red : theme.text.faint}
          pulse={totalOverdue > 0}
        />
        <StatCard
          value={membersWithOverdue}
          label="Members with Overdue"
          accent={
            membersWithOverdue > 0 ? theme.accent.yellow : theme.text.faint
          }
        />
      </div>

      {/* ── Grouped sections ── */}
      {groups.map((group) => (
        <div key={group.key} style={cardStyle}>
          <div style={groupHeaderStyle}>
            <div style={groupTitleStyle}>{group.title}</div>
            <div style={groupBadgeStyle}>
              {group.rows.length} member{group.rows.length !== 1 ? "s" : ""}
            </div>
            {group.overdue > 0 && (
              <div style={overdueBadgeStyle}>
                {group.overdue} overdue
              </div>
            )}
          </div>
          <DataTable
            columns={columns}
            data={group.rows}
            onRowClick={(row) => navigate(`/people/${row.id}`)}
            pageSize={15}
            emptyMessage="No team members in this group."
          />
        </div>
      ))}
    </div>
  );
}
