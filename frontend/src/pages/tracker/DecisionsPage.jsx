import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listDecisions, getEnums, listMatters, listPeople } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import DataTable from "../../components/shared/DataTable";
import EmptyState from "../../components/shared/EmptyState";
import { useDrawer } from "../../contexts/DrawerContext";
import { formatDate } from "../../utils/dateUtils";

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


function isOverdue(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

export default function DecisionsPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [filters, setFilters] = useState({ status: "", matter_id: "", search: "" });

  const { data: enums } = useApi(() => getEnums(), []);
  const { data: mattersData } = useApi(() => listMatters({ limit: 500 }), []);

  const { data, loading, error, refetch } = useApi(
    () => listDecisions(filters),
    [filters.status, filters.matter_id, filters.search]
  );

  const handleFilter = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const decisions = data?.items || data || [];
  const matters = mattersData?.items || mattersData || [];
  const statusOpts = enums?.decision_status || ["pending", "under consideration", "made", "deferred", "no longer needed"];

  const columns = [
    { key: "title", label: "Title" },
    {
      key: "matter_title", label: "Matter", width: 180,
      render: (val, row) => (
        <span style={{ color: theme.accent.blue, cursor: "pointer" }}
          onClick={(e) => { e.stopPropagation(); if (row.matter_id) navigate(`/matters/${row.matter_id}`); }}
        >{val || "\u2014"}</span>
      ),
    },
    {
      key: "status", label: "Status", width: 130,
      render: (val) => {
        const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
        return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
      },
    },
    { key: "owner_name", label: "Assigned To", width: 140 },
    {
      key: "decision_due_date", label: "Due Date", width: 120,
      render: (v) => {
        const overdue = isOverdue(v);
        return (
          <span style={overdue ? { color: theme.accent.red, fontWeight: 600 } : undefined}>
            {formatDate(v)}
          </span>
        );
      },
    },
    { key: "decision_type", label: "Type", width: 110 },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Decisions</div>
        <button style={btnPrimary} onClick={() => openDrawer("decision", null, refetch)}>
          + New Decision
        </button>
      </div>
      <div style={subtitleStyle}>All decisions across matters</div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <select style={inputStyle} value={filters.status} onChange={(e) => handleFilter("status", e.target.value)}>
          <option value="">All Statuses</option>
          {statusOpts.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select style={inputStyle} value={filters.matter_id} onChange={(e) => handleFilter("matter_id", e.target.value)}>
          <option value="">All Matters</option>
          {matters.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={cardStyle}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: theme.text.faint, fontSize: 13 }}>Loading...</div>
        ) : error ? (
          <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
        ) : decisions.length === 0 ? (
          <EmptyState
            title="No decisions found"
            message="Adjust filters or create a new decision."
            actionLabel="New Decision"
            onAction={() => openDrawer("decision", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={decisions}
            onRowClick={(row) => openDrawer("decision", row, refetch)}
          />
        )}
      </div>
    </div>
  );
}
