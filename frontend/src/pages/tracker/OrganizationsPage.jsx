import React, { useState, useCallback, useMemo , useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listOrganizations, getEnums } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";
import { titleStyle, subtitleStyle, inputStyle, btnPrimary, cardStyle } from "../../styles/pageStyles";

// Saved view presets — each maps to a set of org types for client-side filtering
const SAVED_VIEWS = [
  { label: "All Organizations", types: null },
  { label: "CFTC Offices", types: ["CFTC office", "CFTC division", "Commissioner office"] },
  { label: "Federal Agencies", types: ["Federal agency", "White House / OMB"] },
  { label: "Congressional Offices", types: ["Congressional office"] },
  { label: "Industry / Regulated", types: ["Exchange", "Clearinghouse", "Trade association", "Regulated entity"] },
  { label: "Partner Agencies", types: ["Federal agency", "White House / OMB", "Outside counsel", "Inspector General / auditor"] },
];

export default function OrganizationsPage() {
  useEffect(() => { document.title = "Organizations | Command Center"; }, []);
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sortBy, setSortBy] = useState("name");
  const [activeView, setActiveView] = useState(0);
  const [showInactive, setShowInactive] = useState(false);

  const { data: enums } = useApi(() => getEnums(), []);
  const { data, loading, error, refetch } = useApi(
    () => listOrganizations({ search, organization_type: typeFilter, sort_by: sortBy, sort_dir: "asc", is_active: showInactive ? undefined : true, limit: 500 }),
    [search, typeFilter, sortBy, showInactive]
  );

  const handleViewClick = useCallback((idx) => {
    setActiveView(idx);
    // Clear individual type filter when picking a saved view
    setTypeFilter("");
  }, []);

  const handleTypeFilter = useCallback((val) => {
    setTypeFilter(val);
    // If user manually picks a type, deselect saved views (back to "All")
    setActiveView(0);
  }, []);

  const rawOrgs = data?.items || data || [];
  const summary = data?.summary || {};

  // Apply saved-view client-side filtering (multi-type)
  const orgs = useMemo(() => {
    const view = SAVED_VIEWS[activeView];
    if (!view || !view.types) return rawOrgs;
    return rawOrgs.filter((o) => view.types.includes(o.organization_type));
  }, [rawOrgs, activeView]);

  const typeOpts = enums?.organization_type || [];

  const columns = [
    {
      key: "name", label: "Organization",
      render: (val) => (
        <span style={{ color: theme.accent.blueLight, fontWeight: 500 }}>{val || "\u2014"}</span>
      ),
    },
    { key: "short_name", label: "Short Name", width: 100 },
    {
      key: "organization_type", label: "Type", width: 160,
      render: (val) => {
        const c = theme.orgType[val] || theme.orgType["Other"] || { bg: theme.bg.input, text: theme.text.faint };
        return (
          <span style={{
            background: c.bg, color: c.text,
            padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 500,
            whiteSpace: "nowrap",
          }}>
            {val || "\u2014"}
          </span>
        );
      },
    },
    {
      key: "parent_org_name", label: "Parent Org", width: 150,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "jurisdiction", label: "Jurisdiction", width: 150,
      render: (val) => <span style={{ color: theme.text.muted }}>{val || "\u2014"}</span>,
    },
    {
      key: "active_matters", label: "Active Matters", width: 110,
      render: (val) => (
        <span style={{
          color: val > 5 ? theme.accent.yellowLight : theme.text.muted,
          fontWeight: val > 5 ? 600 : 400,
        }}>
          {val ?? 0}
        </span>
      ),
    },
    {
      key: "people_count", label: "Key People", width: 90,
      render: (val) => <span style={{ color: theme.text.muted }}>{val ?? 0}</span>,
    },
    {
      key: "is_active", label: "Status", width: 90,
      render: (val) => {
        const active = val === 1 || val === true;
        return (
          <span style={{
            background: active ? "#1a4731" : "#1f2937",
            color: active ? "#34d399" : "#6b7280",
            padding: "2px 8px", borderRadius: 10, fontSize: 11,
          }}>
            {active ? "Active" : "Inactive"}
          </span>
        );
      },
    },
  ];

  const summaryCards = [
    { label: "Total Active", value: summary.total_active ?? orgs.length },
    { label: "CFTC Internal", value: summary.cftc_internal ?? 0 },
    { label: "Federal / Interagency", value: summary.federal_interagency ?? 0 },
    { label: "External", value: summary.external ?? 0 },
    { label: "Congressional", value: summary.congressional ?? 0 },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Organizations</div>
        <button style={btnPrimary} onClick={() => openDrawer("organization", null, refetch)}>
          + New Organization
        </button>
      </div>
      <div style={subtitleStyle}>Agencies, offices, and external organizations</div>

      {/* Search + Filter bar */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        <input
          style={{ ...inputStyle, flex: 1, minWidth: 220 }}
          placeholder="Search organizations..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select style={inputStyle} value={typeFilter} onChange={(e) => handleTypeFilter(e.target.value)}>
          <option value="">All Types</option>
          {typeOpts.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select style={inputStyle} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="name">Sort: Name</option>
          <option value="organization_type">Sort: Type</option>
          <option value="active_matters">Sort: Active Matters</option>
          <option value="people_count">Sort: People Count</option>
          <option value="created_at">Sort: Date Added</option>
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: theme.text.muted, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            style={{ accentColor: theme.accent.blue }}
          />
          Show inactive
        </label>
      </div>

      {/* Saved View Pills */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
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
            <div style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary }}>{card.value}</div>
            <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>{card.label}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={cardStyle}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: theme.text.faint, fontSize: 13 }}>Loading...</div>
        ) : error ? (
          <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
        ) : orgs.length === 0 ? (
          <EmptyState
            title="No organizations found"
            message="Adjust your filters or create a new organization."
            actionLabel="New Organization"
            onAction={() => openDrawer("organization", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={orgs}
            onRowClick={(row) => navigate(`/organizations/${row.id}`)}
            rowStyle={(row) => (row.is_active === 0 || row.is_active === false) ? { opacity: 0.45 } : {}}
          />
        )}
      </div>

      {/* Footer count */}
      {!loading && !error && orgs.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12, color: theme.text.dim }}>
          Showing {orgs.length} organization{orgs.length !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
