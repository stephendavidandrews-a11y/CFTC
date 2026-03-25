import React, { useState, useCallback, useMemo , useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, inputStyle, btnPrimary, cardStyle } from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import { listPeople, getEnums } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";


/* ── Badge color maps ───────────────────────────────────────── */

const CATEGORY_COLORS = {
  "Boss":                 { bg: "#3b1f6e", text: "#a78bfa" },
  "Leadership":           { bg: "#3b1f6e", text: "#a78bfa" },
  "Direct report":        { bg: "#1e3a5f", text: "#60a5fa" },
  "Indirect report":      { bg: "#1e3a5f", text: "#93c5fd" },
  "OGC peer":             { bg: "#1a4731", text: "#34d399" },
  "Internal client":      { bg: "#1a4731", text: "#34d399" },
  "Commissioner office":  { bg: "#3b1f6e", text: "#a78bfa" },
  "Partner agency":       { bg: "#1a3a4a", text: "#38bdf8" },
  "Hill":                 { bg: "#4a3728", text: "#fbbf24" },
  "Outside party":        { bg: "#3a2a3a", text: "#c084fc" },
};

/* ── Helpers ─────────────────────────────────────────────────── */

function timeAgo(d) {
  if (!d) return "\u2014";
  const now = new Date();
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  const then = new Date(val);
  const diffDays = Math.floor((now - then) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 14) return "1 week ago";
  return `${Math.floor(diffDays / 7)} weeks ago`;
}

function nextNeededLabel(d) {
  if (!d) return "\u2014";
  const now = new Date();
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  const then = new Date(val);
  const diffDays = Math.floor((then - now) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "Overdue";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays <= 7) return "This week";
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/* ── Saved views ─────────────────────────────────────────────── */

const SAVED_VIEWS = [
  { label: "All People", filter: () => true },
  { label: "Team", filter: (p) => p.include_in_team_workload === 1 || p.include_in_team_workload === true || p.relationship_category === "Direct report" || p.relationship_category === "Indirect report" },
  { label: "Leadership", filter: (p) => p.relationship_category === "Boss" || p.relationship_category === "Leadership" },
  { label: "Internal Clients", filter: (p) => p.relationship_category === "Internal client" },
  { label: "Partner Agencies", filter: (p) => p.relationship_category === "Partner agency" },
  { label: "Hill", filter: (p) => p.relationship_category === "Hill" },
  { label: "Outside Parties", filter: (p) => p.relationship_category === "Outside party" },
  { label: "Active Work", filter: (p) => (p.active_matters || 0) > 0 || (p.open_tasks || 0) > 0 },
  { label: "Follow Up Needed", filter: (p) => {
    if (!p.next_interaction_needed_date) return false;
    const nd = p.next_interaction_needed_date;
    const safeNd = typeof nd === "string" && nd.length === 10 ? nd + "T12:00:00" : nd;
    const diffDays = (new Date(safeNd) - Date.now()) / (1000 * 60 * 60 * 24);
    return diffDays <= 7;
  }},
];

/* ── Component ───────────────────────────────────────────────── */

export default function PeoplePage() {
  useEffect(() => { document.title = "People | Command Center"; }, []);
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sortBy, setSortBy] = useState("full_name");
  const [activeView, setActiveView] = useState(0);

  const { data: enums } = useApi(() => getEnums(), []);
  const { data, loading, error, refetch } = useApi(
    () => listPeople({
      search,
      relationship_category: categoryFilter,
      is_active: true,
      sort_by: sortBy,
      sort_dir: sortBy === "last_interaction_date" || sortBy === "active_matters" || sortBy === "open_tasks" ? "desc" : "asc",
      limit: 500,
    }),
    [search, categoryFilter, sortBy]
  );

  const handleViewClick = useCallback((idx) => {
    setActiveView(idx);
    setCategoryFilter("");
  }, []);

  const rawPeople = data?.items || data || [];
  const summary = data?.summary || {};

  // Apply saved-view client-side filtering
  const people = useMemo(() => {
    const view = SAVED_VIEWS[activeView];
    return view ? rawPeople.filter(view.filter) : rawPeople;
  }, [rawPeople, activeView]);

  const categoryOpts = enums?.relationship_category || [];

  const columns = [
    {
      key: "full_name", label: "Person",
      render: (val, row) => (
        <span style={{ color: theme.accent.blueLight, fontWeight: 500 }}>
          {val || `${row.first_name || ""} ${row.last_name || ""}`.trim() || "\u2014"}
        </span>
      ),
    },
    {
      key: "title", label: "Title", width: 160,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "org_name", label: "Organization", width: 120,
      render: (val, row) => (
        <span style={{ color: theme.text.muted }}>{row.org_short_name || val || "\u2014"}</span>
      ),
    },
    {
      key: "relationship_category", label: "Category", width: 130,
      render: (val) => {
        const c = CATEGORY_COLORS[val] || { bg: theme.bg.input, text: theme.text.faint };
        return (
          <span style={{
            background: c.bg, color: c.text,
            padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 500, whiteSpace: "nowrap",
          }}>
            {val || "\u2014"}
          </span>
        );
      },
    },
    {
      key: "active_matters", label: "Active Matters", width: 100,
      render: (val) => (
        <span style={{ fontWeight: val > 0 ? 600 : 400, color: val > 0 ? theme.text.primary : theme.text.faint }}>
          {val ?? 0}
        </span>
      ),
    },
    {
      key: "open_tasks", label: "Open Tasks", width: 85,
      render: (val) => (
        <span style={{ fontWeight: val > 0 ? 600 : 400, color: val > 0 ? theme.text.primary : theme.text.faint }}>
          {val ?? 0}
        </span>
      ),
    },
    {
      key: "last_interaction_date", label: "Last Interaction", width: 110,
      render: (val) => <span style={{ color: theme.text.muted, fontSize: 12 }}>{timeAgo(val)}</span>,
    },
    {
      key: "next_interaction_needed_date", label: "Next Needed", width: 110,
      render: (val) => {
        const label = nextNeededLabel(val);
        const isUrgent = label === "Overdue" || label === "Today" || label === "Tomorrow";
        return (
          <span style={{
            color: isUrgent ? theme.accent.yellowLight : theme.text.muted,
            fontWeight: isUrgent ? 600 : 400,
            fontSize: 12,
          }}>
            {label}
          </span>
        );
      },
    },
  ];

  const summaryCards = [
    { label: "Team", value: summary.team ?? "\u2014" },
    { label: "Internal Clients", value: summary.internal_clients ?? "\u2014" },
    { label: "External Stakeholders", value: summary.external_stakeholders ?? "\u2014" },
    { label: "Follow Up Needed", value: summary.follow_up_needed ?? "\u2014" },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1600 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>People</div>
        <div style={{ display: "flex", gap: 8 }}>
          <select style={inputStyle} value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setActiveView(0); }}>
            <option value="">All Categories</option>
            {categoryOpts.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select style={inputStyle} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="full_name">Sort: Name</option>
            <option value="last_interaction_date">Sort: Last Interaction</option>
            <option value="next_interaction_needed_date">Sort: Next Needed</option>
            <option value="active_matters">Sort: Active Matters</option>
            <option value="open_tasks">Sort: Open Tasks</option>
          </select>
          <button style={btnPrimary} onClick={() => openDrawer("person", null, refetch)}>
            + New Person
          </button>
        </div>
      </div>
      <div style={subtitleStyle}>Relationship and work-context portfolio across internal and external stakeholders</div>

      {/* Search + Saved View Pills */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
        <input
          style={{ ...inputStyle, minWidth: 340 }}
          placeholder="Search people by name, title, organization, or relationship category..."
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
        ) : people.length === 0 ? (
          <EmptyState
            title="No people found"
            message="Adjust your filters or add a new person."
            actionLabel="New Person"
            onAction={() => openDrawer("person", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={people}
            onRowClick={(row) => navigate(`/people/${row.id}`)}
          />
        )}
      </div>

      {/* Footer count */}
      {!loading && !error && people.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: theme.text.dim }}>
          Showing {people.length} {people.length !== 1 ? "people" : "person"}
        </div>
      )}
    </div>
  );
}
