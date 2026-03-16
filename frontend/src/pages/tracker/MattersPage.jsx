import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listMatters, getEnums } from "../../api/tracker";
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

function formatDate(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function MattersPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [filters, setFilters] = useState({ status: "", priority: "", matter_type: "", search: "" });

  const { data: enums } = useApi(() => getEnums(), []);
  const { data, loading, error, refetch } = useApi(
    () => listMatters(filters),
    [filters.status, filters.priority, filters.matter_type, filters.search]
  );

  const handleFilter = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const matters = data?.items || data || [];

  const columns = [
    { key: "matter_number", label: "Matter #", width: 100 },
    { key: "title", label: "Title" },
    { key: "matter_type", label: "Type", width: 120 },
    {
      key: "status", label: "Status", width: 120,
      render: (val) => {
        const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
      },
    },
    {
      key: "priority", label: "Priority", width: 100,
      render: (val) => {
        const p = theme.priority[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={p.bg} text={p.text} label={p.label || val || "\u2014"} />;
      },
    },
    { key: "owner_name", label: "Owner", width: 130 },
    {
      key: "deadline", label: "Deadline", width: 120,
      render: (val, row) => formatDate(row.work_deadline || row.external_deadline || val),
    },
  ];

  const statusOpts = enums?.matter_status || enums?.status || [];
  const priorityOpts = enums?.priority || [];
  const typeOpts = enums?.matter_type || [];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Matters</div>
        <button style={btnPrimary} onClick={() => openDrawer("matter", null, refetch)}>
          + New Matter
        </button>
      </div>
      <div style={subtitleStyle}>All regulatory matters and cases</div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <select style={inputStyle} value={filters.status} onChange={(e) => handleFilter("status", e.target.value)}>
          <option value="">All Statuses</option>
          {statusOpts.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select style={inputStyle} value={filters.priority} onChange={(e) => handleFilter("priority", e.target.value)}>
          <option value="">All Priorities</option>
          {priorityOpts.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select style={inputStyle} value={filters.matter_type} onChange={(e) => handleFilter("matter_type", e.target.value)}>
          <option value="">All Types</option>
          {typeOpts.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          style={{ ...inputStyle, minWidth: 200 }}
          placeholder="Search matters..."
          value={filters.search}
          onChange={(e) => handleFilter("search", e.target.value)}
        />
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
    </div>
  );
}
