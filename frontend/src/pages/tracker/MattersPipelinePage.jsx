import React, { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import theme from "../../styles/theme";
import { titleStyle, subtitleStyle, inputStyle, cardStyle } from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import { listMatters } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import KanbanBoard from "../../components/shared/KanbanBoard";

// Column definitions mapping workflow_status + regulatory_stage to kanban columns
const PIPELINE_COLUMNS = [
  {
    key: "development",
    label: "Development",
    color: "#6b7280",
    statuses: ["concept", "drafting", "cba_development"],
  },
  {
    key: "internal_review",
    label: "Internal Review",
    color: "#a78bfa",
    statuses: ["internal_review", "client_review", "chairman_review", "commission_review"],
  },
  {
    key: "proposed",
    label: "Proposed",
    color: "#3b82f6",
    statuses: ["ofr_submission"],
    regStages: ["proposed"],
  },
  {
    key: "comment_analysis",
    label: "Comment Analysis",
    color: "#f59e0b",
    statuses: ["comment_analysis", "final_drafting"],
  },
  {
    key: "final_effective",
    label: "Final / Effective",
    color: "#22c55e",
    statuses: ["published", "effective"],
    regStages: ["published", "effective"],
  },
  {
    key: "withdrawn",
    label: "Withdrawn",
    color: "#ef4444",
    statuses: ["withdrawn", "closed"],
  },
];

/** Single source of truth for kanban column placement */
function getPipelineColumn(matter) {
  const wf = (matter.workflow_status || "").toLowerCase();
  const rs = (matter.regulatory_stage || "").toLowerCase();

  // Terminal states first
  if (wf === "withdrawn" || wf === "closed" || matter.status === "withdrawn") return "withdrawn";

  // Check regulatory_stage for broad categorization
  if (rs === "published" || rs === "effective") return "final_effective";
  if (rs === "proposed") return "proposed";

  // Check workflow_status against column statuses
  for (const col of PIPELINE_COLUMNS) {
    if (col.statuses.includes(wf)) return col.key;
  }

  // Default: if no workflow status, infer from regulatory stage or put in development
  return "development";
}

function getDeadlineInfo(matter) {
  const dl = matter.work_deadline || matter.external_deadline;
  if (!dl) return { text: null, severity: null };
  const date = new Date(typeof dl === "string" && dl.length === 10 ? dl + "T12:00:00" : dl);
  const daysUntil = Math.ceil((date - Date.now()) / (1000 * 60 * 60 * 24));
  const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const severity = daysUntil < 0 ? "overdue" : daysUntil <= 3 ? "critical" : daysUntil <= 7 ? "warning" : "ok";
  return { text: label, severity };
}

function getInitials(name) {
  if (!name) return null;
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

function inferTypeBadge(matter) {
  const ext = matter.extension || {};
  const title = (matter.title || "").toLowerCase();
  if (ext.is_petition) return "Petition";
  if (title.includes("anprm") || title.includes("advance notice")) return "ANPRM";
  if (title.includes("nprm") || title.includes("proposed rule") || title.includes("proposal")) return "NPRM";
  if (title.includes("interim final") || title.includes("ifr")) return "IFR";
  if (title.includes("final rule") || title.includes("final order")) return "Final Rule";
  return "Rule";
}


export default function MattersPipelinePage() {
  useEffect(() => { document.title = "Regulatory Pipeline | Command Center"; }, []);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [viewMode, setViewMode] = useState("kanban");
  const priorityFilter = searchParams.get("priority") || "";
  const ownerFilter = searchParams.get("owner") || "";
  const searchFilter = searchParams.get("q") || "";

  const setFilter = (key, val) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val);
    else next.delete(key);
    setSearchParams(next);
  };

  const { data, loading, error } = useApi(
    () => listMatters({ matter_type: "rulemaking", limit: 500 }),
    []
  );

  const rawMatters = data?.items || data || [];

  // Client-side filtering — exclude closed/deleted matters from pipeline
  const filtered = useMemo(() => {
    return rawMatters.filter((m) => {
      if (m.status === "closed") return false;
      if (priorityFilter && m.priority !== priorityFilter) return false;
      if (ownerFilter && m.owner_name !== ownerFilter) return false;
      if (searchFilter) {
        const q = searchFilter.toLowerCase();
        if (!(m.title || "").toLowerCase().includes(q) &&
            !(m.matter_number || "").toLowerCase().includes(q) &&
            !(m.rin || "").toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [rawMatters, priorityFilter, ownerFilter, searchFilter]);

  // Build kanban columns
  const kanbanColumns = useMemo(() => {
    return PIPELINE_COLUMNS.map((col) => {
      const items = filtered
        .filter((m) => getPipelineColumn(m) === col.key)
        .map((m) => {
          const dl = getDeadlineInfo(m);
          return {
            id: m.id,
            title: m.title || m.short_title || "Untitled",
            rin: m.rin,
            matterNumber: m.matter_number,
            typeBadge: inferTypeBadge(m),
            priority: m.priority,
            ownerInitials: getInitials(m.owner_name),
            deadline: dl.text,
            deadlineSeverity: dl.severity,
          };
        });
      return { ...col, items };
    });
  }, [filtered]);

  // Unique owners for filter dropdown
  const owners = useMemo(() => {
    const set = new Set(rawMatters.map(m => m.owner_name).filter(Boolean));
    return [...set].sort();
  }, [rawMatters]);

  const totalItems = filtered.length;

  // Table columns for table view
  const tableColumns = [
    {
      key: "title", label: "Title",
      render: (val, row) => (
        <div style={{ minWidth: 200 }}>
          <div style={{ color: theme.accent.blueLight, fontWeight: 500 }}>{val}</div>
          {row.rin && <div style={{ fontSize: 10, color: theme.accent.purple, fontFamily: theme.font.mono, marginTop: 1 }}>{row.rin}</div>}
        </div>
      ),
    },
    { key: "matter_number", label: "Matter #", width: 120 },
    {
      key: "regulatory_stage", label: "Stage", width: 130,
      render: (val) => {
        if (!val) return <span style={{ color: theme.text.faint }}>{"\u2014"}</span>;
        const colors = { proposed: { bg: "rgba(59,130,246,0.15)", text: "#60a5fa" }, published: { bg: "rgba(34,197,94,0.15)", text: "#22c55e" }, effective: { bg: "rgba(34,197,94,0.15)", text: "#22c55e" }, withdrawn: { bg: "rgba(239,68,68,0.15)", text: "#f87171" } };
        const c = colors[val] || { bg: "rgba(100,116,139,0.15)", text: "#94a3b8" };
        return <Badge bg={c.bg} text={c.text} label={val.replace(/_/g, " ")} />;
      },
    },
    {
      key: "workflow_status", label: "Workflow", width: 130,
      render: (val) => <span style={{ color: theme.text.muted, fontSize: 12 }}>{val || "\u2014"}</span>,
    },
    {
      key: "priority", label: "Priority", width: 140,
      render: (val) => {
        const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
      },
    },
    { key: "owner_name", label: "Owner", width: 100 },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1600 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Regulatory Pipeline</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {/* View toggle */}
          <div style={{ display: "flex", borderRadius: 6, border: `1px solid ${theme.border.default}`, overflow: "hidden" }}>
            {["kanban", "table"].map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                style={{
                  padding: "5px 14px", fontSize: 12, fontWeight: 500, cursor: "pointer", border: "none",
                  background: viewMode === mode ? theme.accent.blue : theme.bg.input,
                  color: viewMode === mode ? "#fff" : theme.text.muted,
                  transition: "all 0.15s",
                }}
              >
                {mode === "kanban" ? "Board" : "Table"}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div style={subtitleStyle}>
        {totalItems} rulemaking matter{totalItems !== 1 ? "s" : ""} across the regulatory lifecycle
      </div>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <input
          style={{ ...inputStyle, maxWidth: 280 }}
          placeholder="Search by title, RIN, or matter #..."
          value={searchFilter}
          onChange={(e) => setFilter("q", e.target.value)}
        />
        <select
          style={{ ...inputStyle, maxWidth: 200 }}
          value={priorityFilter}
          onChange={(e) => setFilter("priority", e.target.value)}
        >
          <option value="">All Priorities</option>
          <option value="critical this week">Critical This Week</option>
          <option value="important this month">Important This Month</option>
          <option value="strategic / slow burn">Strategic / Slow Burn</option>
          <option value="monitoring only">Monitoring Only</option>
          <option value="backlog">Backlog</option>
        </select>
        <select
          style={{ ...inputStyle, maxWidth: 180 }}
          value={ownerFilter}
          onChange={(e) => setFilter("owner", e.target.value)}
        >
          <option value="">All Owners</option>
          {owners.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        {(priorityFilter || ownerFilter || searchFilter) && (
          <button
            onClick={() => setSearchParams({})}
            style={{
              padding: "5px 12px", borderRadius: 6, fontSize: 11, cursor: "pointer",
              background: "transparent", color: theme.text.muted,
              border: `1px solid ${theme.border.default}`,
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: theme.text.faint, fontSize: 13 }}>Loading pipeline...</div>
      ) : error ? (
        <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No rulemaking matters"
          message="No rulemaking matters match your current filters."
        />
      ) : viewMode === "kanban" ? (
        <KanbanBoard
          columns={kanbanColumns}
          onCardClick={(item) => navigate(`/matters/${item.id}`)}
        />
      ) : (
        <div style={cardStyle}>
          <DataTable
            columns={tableColumns}
            data={filtered}
            onRowClick={(row) => navigate(`/matters/${row.id}`)}
          />
        </div>
      )}
    </div>
  );
}
