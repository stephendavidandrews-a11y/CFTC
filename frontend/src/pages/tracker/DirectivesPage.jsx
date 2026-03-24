import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listPolicyDirectives, getEnums, listPeople } from "../../api/tracker";
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
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  borderRadius: 6, padding: "7px 12px", fontSize: 13,
  color: theme.text.secondary, outline: "none", minWidth: 140,
};
const btnPrimary = {
  padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};

const STATUS_COLORS = {
  not_started: { bg: theme.bg.input, text: theme.text.dim },
  scoping: { bg: "#1a3a5c", text: "#60a5fa" },
  in_progress: { bg: "#3b2a1a", text: "#fbbf24" },
  partially_implemented: { bg: "#2a3b1a", text: "#86efac" },
  implemented: { bg: "#1a3b2a", text: "#34d399" },
  deferred: { bg: theme.bg.input, text: theme.text.dim },
  not_applicable: { bg: theme.bg.input, text: theme.text.dim },
};

const TIER_COLORS = {
  immediate_action: { bg: "#3b1a1a", text: "#f87171" },
  priority_guidance: { bg: "#3b2a1a", text: "#fbbf24" },
  possible_regulation: { bg: "#1a3a5c", text: "#60a5fa" },
  possible_legislation: { bg: "#2a1a3b", text: "#c084fc" },
  longer_term: { bg: theme.bg.input, text: theme.text.dim },
  other: { bg: theme.bg.input, text: theme.text.dim },
};

function fmt(val) {
  return val ? val.replace(/_/g, " ") : "";
}

export default function DirectivesPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [filters, setFilters] = useState({});

  const { data, loading, error, refetch } = useApi(
    () => listPolicyDirectives(filters), [JSON.stringify(filters)]
  );
  const { data: enumsData } = useApi(() => getEnums(), []);

  const directives = data?.items || [];
  const enums = enumsData || {};

  const columns = [
    { key: "directive_label", label: "Directive", flex: 1,
      render: (r) => <span style={{ fontWeight: 600 }}>{r.directive_label}</span> },
    { key: "source_document", label: "Source", width: 180,
      render: (r) => <span title={r.source_document} style={{ fontSize: 12, color: theme.text.dim }}>
        {r.source_document?.length > 30 ? r.source_document.slice(0, 30) + "..." : r.source_document}
      </span> },
    { key: "priority_tier", label: "Priority", width: 130,
      render: (r) => r.priority_tier ? <Badge {...(TIER_COLORS[r.priority_tier] || {})} label={fmt(r.priority_tier)} /> : null },
    { key: "responsible_entity", label: "Responsible", width: 100,
      render: (r) => r.responsible_entity ? <Badge bg={theme.bg.input} text={theme.text.secondary} label={fmt(r.responsible_entity)} /> : null },
    { key: "ogc_role", label: "OGC Role", width: 100,
      render: (r) => r.ogc_role ? <span style={{ fontSize: 12, color: theme.text.dim }}>{fmt(r.ogc_role)}</span> : null },
    { key: "implementation_status", label: "Status", width: 140,
      render: (r) => <Badge {...(STATUS_COLORS[r.implementation_status] || {})} label={fmt(r.implementation_status)} /> },
    { key: "linked_matter_count", label: "Matters", width: 70, render: (r) => r.linked_matter_count || 0 },
    { key: "assigned_to_name", label: "Assigned To", width: 130,
      render: (r) => r.assigned_to_name || <span style={{ color: theme.text.dim }}>--</span> },
  ];

  // Summary cards
  const total = directives.length;
  const byStatus = {};
  directives.forEach((d) => { byStatus[d.implementation_status] = (byStatus[d.implementation_status] || 0) + 1; });

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div>
          <div style={titleStyle}>Policy Directives</div>
          <div style={subtitleStyle}>External mandates requiring CFTC implementation</div>
        </div>
        <button style={btnPrimary} onClick={() => openDrawer("directive", {}, refetch)}>+ New Directive</button>
      </div>

      {/* Summary */}
      {total > 0 && (
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: theme.text.dim }}>
            {total} directives: {Object.entries(byStatus).map(([s, c]) => `${c} ${fmt(s)}`).join(" \u00b7 ")}
          </span>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <input style={inputStyle} placeholder="Search..." value={filters.search || ""}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })} />
        <select style={inputStyle} value={filters.implementation_status || ""}
          onChange={(e) => setFilters({ ...filters, implementation_status: e.target.value })}>
          <option value="">All Statuses</option>
          {(enums.directive_implementation_status || []).map((v) => <option key={v} value={v}>{fmt(v)}</option>)}
        </select>
        <select style={inputStyle} value={filters.responsible_entity || ""}
          onChange={(e) => setFilters({ ...filters, responsible_entity: e.target.value })}>
          <option value="">All Entities</option>
          {(enums.directive_responsible_entity || []).map((v) => <option key={v} value={v}>{fmt(v)}</option>)}
        </select>
        <select style={inputStyle} value={filters.ogc_role || ""}
          onChange={(e) => setFilters({ ...filters, ogc_role: e.target.value })}>
          <option value="">All OGC Roles</option>
          {(enums.directive_ogc_role || []).map((v) => <option key={v} value={v}>{fmt(v)}</option>)}
        </select>
        <select style={inputStyle} value={filters.priority_tier || ""}
          onChange={(e) => setFilters({ ...filters, priority_tier: e.target.value })}>
          <option value="">All Priorities</option>
          {(enums.directive_priority_tier || []).map((v) => <option key={v} value={v}>{fmt(v)}</option>)}
        </select>
      </div>

      <div style={cardStyle}>
        {loading && <div style={{ color: theme.text.dim, padding: 24 }}>Loading...</div>}
        {error && <div style={{ color: theme.accent.red, padding: 24 }}>Error: {error.message || "Failed to load"}</div>}
        {!loading && !error && directives.length === 0 && (
          <EmptyState icon="\ud83d\udcdc" title="No directives yet" subtitle="Add external mandates to track implementation" />
        )}
        {!loading && !error && directives.length > 0 && (
          <DataTable columns={columns} data={directives}
            onRowClick={(row) => navigate(`/directives/${row.id}`)} />
        )}
      </div>
    </div>
  );
}
