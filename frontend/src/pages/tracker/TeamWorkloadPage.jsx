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

/* ── main component ────────────────────────────────────────────────────── */

export default function TeamWorkloadPage() {
  const navigate = useNavigate();

  const { data: peopleData, loading: loadingPeople } = useApi(
    () => listPeople({ limit: 500 }),
    []
  );
  const { data: tasksData, loading: loadingTasks } = useApi(
    () => listTasks({ limit: 500 }),
    []
  );

  const loading = loadingPeople || loadingTasks;

  const { teamRows, maxActive, totalOverdue, membersWithOverdue } =
    useMemo(() => {
      const people = peopleData?.items || peopleData || [];
      const tasks = tasksData?.items || tasksData || [];
      const team = people.filter((p) => p.include_in_team_workload);
      const now = new Date();

      let _totalOverdue = 0;
      let _membersWithOverdue = 0;

      const rows = team.map((person) => {
        const personTasks = tasks.filter(
          (t) =>
            t.assigned_to_person_id === person.id &&
            t.status !== "done" &&
            t.status !== "deferred"
        );
        const overdue = personTasks.filter(
          (t) => t.due_date && new Date(t.due_date) < now
        );

        _totalOverdue += overdue.length;
        if (overdue.length > 0) _membersWithOverdue += 1;

        // Find most urgent matter (earliest due-date task's matter)
        const urgentTask = personTasks
          .filter((t) => t.due_date)
          .sort((a, b) => new Date(a.due_date) - new Date(b.due_date))[0];

        return {
          id: person.id,
          name:
            person.full_name ||
            `${person.first_name || ""} ${person.last_name || ""}`.trim(),
          title: person.title || "\u2014",
          org_name: person.organization_name || person.org_name || "\u2014",
          activeTasks: personTasks.length,
          overdueTasks: overdue.length,
          atRiskMatter: urgentTask?.matter_title || null,
          atRiskMatterId: urgentTask?.matter_id || null,
        };
      });

      rows.sort((a, b) => b.overdueTasks - a.overdueTasks || b.activeTasks - a.activeTasks);

      const _maxActive = rows.reduce(
        (mx, r) => Math.max(mx, r.activeTasks),
        1
      );

      return {
        teamRows: rows,
        maxActive: _maxActive,
        totalOverdue: _totalOverdue,
        membersWithOverdue: _membersWithOverdue,
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
        Loading team workload\u2026
      </div>
    );
  }

  const columns = [
    {
      key: "name",
      label: "Name",
      width: "22%",
      render: (val, row) => (
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
    { key: "title", label: "Title", width: "18%" },
    { key: "org_name", label: "Organization", width: "16%" },
    {
      key: "activeTasks",
      label: "Active Tasks",
      width: "10%",
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
      width: "18%",
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
      width: "6%",
      sortable: false,
      render: (_val, row) => (
        <LoadBar
          active={row.activeTasks}
          overdue={row.overdueTasks}
          max={maxActive}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Team Workload</div>
      <div style={subtitleStyle}>Management view</div>

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
          value={teamRows.length}
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

      {/* ── Main table ── */}
      <div style={cardStyle}>
        <DataTable
          columns={columns}
          data={teamRows}
          onRowClick={(row) => navigate(`/people/${row.id}`)}
          pageSize={25}
          emptyMessage="No team members with workload tracking enabled."
        />
      </div>
    </div>
  );
}
