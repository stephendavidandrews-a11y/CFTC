import React, { useState, useCallback, useMemo , useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, inputStyle, btnPrimary, cardStyle } from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import { listMatters, getEnums } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";
import { formatDate } from "../../utils/dateUtils";



function formatShortDate(d) {
  if (!d) return "\u2014";
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function timeAgo(d) {
  if (!d) return "\u2014";
  const now = new Date();
  const then = new Date(d);
  const diffMs = now - then;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 14) return "1 week ago";
  return `${Math.floor(diffDays / 7)} weeks ago`;
}

// Saved view presets — client-side filters on the loaded data
const isOpen = (m) => m.status !== "closed";
const isActive = (m) => isOpen(m) && m.status !== "parked / monitoring";

const SAVED_VIEWS = [
  { label: "All Open Matters", filter: isActive },
  { label: "Critical This Week", filter: (m) => isActive(m) && m.priority === "critical this week" },
  { label: "Awaiting Decision", filter: (m) => isActive(m) && (m.status === "awaiting comments" || m.status === "awaiting decision" || (m.pending_decision && m.pending_decision.trim())) },
  { label: "Needs My Attention", filter: (m) => isActive(m) && (m.next_step_owner_name === "You" || m.owner_name === "You") },
  { label: "Leadership-Sensitive", filter: (m) => isActive(m) && m.boss_involvement_level && m.boss_involvement_level !== "none" && m.boss_involvement_level !== "" },
  { label: "Stale Matters", filter: (m) => {
    if (!isOpen(m)) return false;
    if (!m.updated_at) return true;
    const diffDays = (Date.now() - new Date(m.updated_at).getTime()) / (1000 * 60 * 60 * 24);
    return diffDays > 14;
  }},
  { label: "Parked / Monitoring", filter: (m) => isOpen(m) && m.status === "parked / monitoring" },
];

// Smart hybrid ranking: priority score + deadline proximity + pending decision + staleness
function matterRankScore(m) {
  let score = 0;
  // Priority weight
  if (m.priority === "critical this week") score += 100;
  else if (m.priority === "important this month") score += 60;
  else if (m.priority === "strategic / slow burn") score += 30;
  // Pending decision
  if (m.pending_decision && m.pending_decision.trim()) score += 25;
  // Deadline proximity (next 7 days = high, next 14 = medium)
  const deadline = m.work_deadline || m.external_deadline || m.decision_deadline;
  if (deadline) {
    const daysUntil = (new Date(deadline) - Date.now()) / (1000 * 60 * 60 * 24);
    if (daysUntil < 0) score += 50; // overdue
    else if (daysUntil <= 3) score += 40;
    else if (daysUntil <= 7) score += 25;
    else if (daysUntil <= 14) score += 10;
  }
  // Staleness penalty (newer = higher)
  if (m.updated_at) {
    const daysSinceUpdate = (Date.now() - new Date(m.updated_at).getTime()) / (1000 * 60 * 60 * 24);
    if (daysSinceUpdate > 14) score += 15; // stale matters need attention
  }
  return score;
}

export default function MattersPage() {
  useEffect(() => { document.title = "Matters | Command Center"; }, []);
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [activeView, setActiveView] = useState(0);

  const { data: enums } = useApi(() => getEnums(), []);
  const { data, loading, error, refetch } = useApi(
    () => listMatters({ search, status: statusFilter, priority: priorityFilter, matter_type: typeFilter, limit: 500 }),
    [search, statusFilter, priorityFilter, typeFilter]
  );

  const handleViewClick = useCallback((idx) => {
    setActiveView(idx);
    // Reset dropdown filters when picking a saved view
    setStatusFilter("");
    setPriorityFilter("");
    setTypeFilter("");
  }, []);

  const rawMatters = data?.items || data || [];
  const summary = data?.summary || {};

  // Apply saved-view client-side filtering, then smart hybrid ranking
  const matters = useMemo(() => {
    const view = SAVED_VIEWS[activeView];
    let filtered = view ? rawMatters.filter(view.filter) : rawMatters;
    // Smart hybrid ranking: closed last, then by composite score desc
    return [...filtered].sort((a, b) => {
      const closedA = a.status === "closed" ? 1 : 0;
      const closedB = b.status === "closed" ? 1 : 0;
      if (closedA !== closedB) return closedA - closedB;
      return matterRankScore(b) - matterRankScore(a);
    });
  }, [rawMatters, activeView]);

  const statusOpts = enums?.matter_status || enums?.status || [];
  const priorityOpts = enums?.priority || [];
  const typeOpts = enums?.matter_type || [];

  const columns = [
    {
      key: "title", label: "Matter",
      render: (val, row) => (
        <div style={{ minWidth: 200 }}>
          <div style={{ color: theme.accent.blueLight, fontWeight: 500 }}>{val}</div>
          {row.matter_number && <div style={{ fontSize: 10, color: theme.text.dim, marginTop: 2 }}>{row.matter_number}</div>}
        </div>
      ),
    },
    { key: "matter_type", label: "Type", width: 130 },
    { key: "owner_name", label: "Owner", width: 100 },
    {
      key: "priority", label: "Priority", width: 140,
      render: (val) => {
        const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
      },
    },
    {
      key: "status", label: "Status", width: 140,
      render: (val) => {
        const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
      },
    },
    {
      key: "deadline", label: "Next Deadline", width: 100,
      render: (val, row) => {
        const d = row.work_deadline || row.external_deadline || row.decision_deadline;
        if (!d) return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
        const isOverdue = new Date(d) < new Date();
        return <span style={{ fontWeight: 600, color: isOverdue ? theme.accent.red : theme.text.primary }}>{formatShortDate(d)}</span>;
      },
    },
    {
      key: "next_step", label: "Next Step", width: 200,
      render: (val) => (
        <div style={{ fontSize: 12, color: theme.text.muted, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {val || "\u2014"}
        </div>
      ),
    },
    {
      key: "next_step_owner_name", label: "Step Owner", width: 100,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "pending_decision", label: "Pending Decision", width: 180,
      render: (val) => (
        <div style={{ fontSize: 12, color: val ? theme.accent.yellowLight : theme.text.faint, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {val || "\u2014"}
        </div>
      ),
    },
    {
      key: "client_org_name", label: "Client", width: 120,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "updated_at", label: "Last Update", width: 90,
      render: (val) => <span style={{ color: theme.text.dim, fontSize: 12 }}>{timeAgo(val)}</span>,
    },
  ];

  const summaryCards = [
    { label: "Open Matters", value: summary.open_matters ?? "\u2014" },
    { label: "Critical This Week", value: summary.critical_this_week ?? "\u2014" },
    { label: "Awaiting Decision", value: summary.awaiting_decision ?? "\u2014" },
    { label: "Stale Matters", value: summary.stale_matters ?? "\u2014" },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1600 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Matters</div>
        <div style={{ display: "flex", gap: 8 }}>
          <select style={inputStyle} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Statuses</option>
            {statusOpts.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
          <select style={inputStyle} value={priorityFilter} onChange={(e) => { setPriorityFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Priorities</option>
            {priorityOpts.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select style={inputStyle} value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Types</option>
            {typeOpts.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button style={btnPrimary} onClick={() => openDrawer("matter", null, refetch)}>
            + New Matter
          </button>
        </div>
      </div>
      <div style={subtitleStyle}>Portfolio view of live regulatory matters and cases</div>

      {/* Search + Saved View Pills */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
        <input
          style={{ ...inputStyle, minWidth: 320 }}
          placeholder="Search matters by title, matter number, owner, or client office..."
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
            <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginTop: 4 }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={cardStyle}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: theme.text.faint, fontSize: 13 }}>Loading...</div>
        ) : error ? (
          <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
        ) : matters.length === 0 ? (
          <EmptyState
            title="No matters found"
            message="Adjust your filters or create a new matter."
            actionLabel="New Matter"
            onAction={() => openDrawer("matter", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={matters}
            onRowClick={(row) => navigate(`/matters/${row.id}`)}
          />
        )}
      </div>

      {/* Footer count */}
      {!loading && !error && matters.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: theme.text.dim }}>
          Showing {matters.length} matter{matters.length !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
