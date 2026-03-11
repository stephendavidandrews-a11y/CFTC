import React, { useState } from "react";
import theme from "../styles/theme";
import DataTable from "../components/shared/DataTable";
import Badge from "../components/shared/Badge";
import PriorityBadge from "../components/shared/PriorityBadge";
import EmptyState from "../components/shared/EmptyState";
import useApi from "../hooks/useApi";
import { listItems, getUpcomingDeadlines, getTeamDashboard } from "../api/pipeline";

const REPORTS = [
  { key: "pipeline", label: "Pipeline Status", icon: "◤", desc: "All active items with stage, priority, and deadline status" },
  { key: "deadlines", label: "Deadline Report", icon: "⏰", desc: "Upcoming and overdue deadlines across all items" },
  { key: "workload", label: "Team Workload", icon: "⊡", desc: "Team member capacity and assignment distribution" },
];

export default function ReportsPage() {
  const [activeReport, setActiveReport] = useState(null);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Reports</h1>
          <p style={{ color: theme.text.faint, fontSize: 13, margin: "4px 0 0" }}>Generate and view operational reports</p>
        </div>
        {activeReport && (
          <button
            onClick={() => window.print()}
            style={{
              padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
              background: theme.bg.input, color: theme.text.muted,
              border: `1px solid ${theme.border.default}`, cursor: "pointer",
            }}
          >
            🖨 Print
          </button>
        )}
      </div>

      {!activeReport && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {REPORTS.map((r) => (
            <button
              key={r.key}
              onClick={() => setActiveReport(r.key)}
              style={{
                background: theme.bg.card, borderRadius: 10, padding: 24,
                border: `1px solid ${theme.border.default}`, cursor: "pointer",
                textAlign: "left", transition: "border-color 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = theme.accent.blue}
              onMouseLeave={e => e.currentTarget.style.borderColor = theme.border.default}
            >
              <div style={{ fontSize: 28, marginBottom: 12 }}>{r.icon}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: theme.text.primary, marginBottom: 6 }}>{r.label}</div>
              <div style={{ fontSize: 12, color: theme.text.faint, lineHeight: 1.5 }}>{r.desc}</div>
            </button>
          ))}
        </div>
      )}

      {activeReport === "pipeline" && <PipelineReport onBack={() => setActiveReport(null)} />}
      {activeReport === "deadlines" && <DeadlineReport onBack={() => setActiveReport(null)} />}
      {activeReport === "workload" && <WorkloadReport onBack={() => setActiveReport(null)} />}
    </div>
  );
}

function ReportHeader({ title, onBack }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <button onClick={onBack} style={{
        background: "transparent", border: "none", color: theme.text.faint,
        fontSize: 18, cursor: "pointer", padding: "2px 6px",
      }}>←</button>
      <h2 style={{ fontSize: 17, fontWeight: 700, color: theme.text.primary, margin: 0 }}>{title}</h2>
      <span style={{ fontSize: 11, color: theme.text.faint }}>Generated {new Date().toLocaleDateString()}</span>
    </div>
  );
}

function PipelineReport({ onBack }) {
  const { data, loading } = useApi(() => listItems({ status: "active", page_size: 200 }), []);
  const items = data?.items || [];

  const columns = [
    { key: "title", label: "Title", width: "25%", render: (v) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { key: "module", label: "Module", width: "10%", render: (v) => <Badge bg={v === "rulemaking" ? "#172554" : "#2e1065"} text={v === "rulemaking" ? "#60a5fa" : "#a78bfa"} label={v} /> },
    { key: "item_type", label: "Type", width: "10%" },
    { key: "stage_label", label: "Stage", width: "12%" },
    { key: "days_in_stage", label: "Days in Stage", width: "8%", render: (v) => <span style={{ color: v > 30 ? theme.accent.red : theme.text.muted }}>{v ?? "—"}</span> },
    { key: "priority_label", label: "Priority", width: "10%", render: (v, row) => v ? <PriorityBadge label={v} score={row.priority_composite} /> : "—" },
    { key: "lead_attorney_name", label: "Lead", width: "12%" },
    { key: "status", label: "Status", width: "8%", render: (v) => { const s = theme.status[v]; return s ? <Badge bg={s.bg} text={s.text} label={s.label} /> : v; } },
  ];

  if (loading) return <div style={{ color: theme.text.faint, padding: 40, textAlign: "center" }}>Loading report...</div>;

  return (
    <div>
      <ReportHeader title="Pipeline Status Report" onBack={onBack} />
      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "4px 16px" }}>
        {items.length ? <DataTable columns={columns} data={items} pageSize={50} /> : <EmptyState title="No active items" />}
      </div>
    </div>
  );
}

function DeadlineReport({ onBack }) {
  const { data: deadlines, loading } = useApi(() => getUpcomingDeadlines(90), []);

  const columns = [
    { key: "title", label: "Deadline", width: "25%", render: (v) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { key: "item_title", label: "Item", width: "20%" },
    { key: "deadline_type", label: "Type", width: "10%", render: (v) => <Badge bg="#172554" text="#60a5fa" label={v} /> },
    { key: "due_date", label: "Due Date", width: "12%" },
    { key: "days_remaining", label: "Days Left", width: "10%", render: (v) => (
      <span style={{ fontWeight: 700, color: v < 0 ? theme.accent.red : v <= 7 ? theme.accent.yellow : theme.text.muted }}>{v}</span>
    )},
    { key: "severity", label: "Severity", width: "10%", render: (v) => {
      const colors = { overdue: "#ef4444", critical: "#ef4444", warning: "#f59e0b", ok: "#22c55e" };
      return <span style={{ color: colors[v] || theme.text.muted, fontWeight: 600, fontSize: 12 }}>{v}</span>;
    }},
    { key: "owner_name", label: "Owner", width: "12%" },
  ];

  if (loading) return <div style={{ color: theme.text.faint, padding: 40, textAlign: "center" }}>Loading report...</div>;

  return (
    <div>
      <ReportHeader title="Deadline Report (Next 90 Days)" onBack={onBack} />
      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "4px 16px" }}>
        {deadlines?.length ? <DataTable columns={columns} data={deadlines} pageSize={50} /> : <EmptyState title="No upcoming deadlines" />}
      </div>
    </div>
  );
}

function WorkloadReport({ onBack }) {
  const { data: dashboard, loading } = useApi(getTeamDashboard, []);
  const members = dashboard?.members || [];

  const columns = [
    { key: "name", label: "Attorney", width: "20%", render: (v) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { key: "role", label: "Role", width: "18%" },
    { key: "active_items", label: "Active Items", width: "10%", render: (v) => <span style={{ fontWeight: 700, color: theme.text.primary }}>{v || 0}</span> },
    { key: "lead_items", label: "As Lead", width: "10%" },
    { key: "overdue_deadlines", label: "Overdue", width: "10%", render: (v) => <span style={{ color: v > 0 ? theme.accent.red : theme.text.muted, fontWeight: v > 0 ? 700 : 400 }}>{v || 0}</span> },
    { key: "capacity_remaining", label: "Capacity Left", width: "10%", render: (v, row) => {
      const max = row.max_concurrent || 5;
      const pct = Math.round(((max - (row.active_items || 0)) / max) * 100);
      return <span style={{ color: pct <= 20 ? theme.accent.red : pct <= 50 ? theme.accent.yellow : theme.accent.green, fontWeight: 600 }}>{pct}%</span>;
    }},
    { key: "max_concurrent", label: "Max Concurrent", width: "10%" },
  ];

  if (loading) return <div style={{ color: theme.text.faint, padding: 40, textAlign: "center" }}>Loading report...</div>;

  return (
    <div>
      <ReportHeader title="Team Workload Report" onBack={onBack} />
      <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "4px 16px" }}>
        {members.length ? <DataTable columns={columns} data={members} pageSize={50} /> : <EmptyState title="No team members" />}
      </div>
    </div>
  );
}
