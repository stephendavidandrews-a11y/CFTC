import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listPeople, listOrganizations } from "../../api/tracker";
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

export default function PeoplePage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [filters, setFilters] = useState({ organization_id: "", search: "" });

  const { data: orgsData } = useApi(() => listOrganizations({ limit: 500 }), []);
  const { data, loading, error, refetch } = useApi(
    () => listPeople(filters),
    [filters.organization_id, filters.search]
  );

  const handleFilter = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const people = data?.items || data || [];
  const orgs = orgsData?.items || orgsData || [];

  const columns = [
    {
      key: "name", label: "Name",
      render: (v, row) => row.full_name || `${row.first_name || ""} ${row.last_name || ""}`.trim() || "\u2014",
    },
    { key: "title", label: "Title", width: 180 },
    { key: "organization_name", label: "Organization", width: 180 },
    { key: "relationship_category", label: "Category", width: 110 },
    { key: "relationship_lane", label: "Lane", width: 100 },
    { key: "phone", label: "Phone", width: 130 },
    {
      key: "is_active", label: "Active", width: 70,
      render: (val) => (
        <span style={{ color: val ? theme.accent.green : theme.text.faint, fontSize: 12, fontWeight: 600 }}>
          {val ? "Yes" : "No"}
        </span>
      ),
    },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>People</div>
        <button style={btnPrimary} onClick={() => openDrawer("person", null, refetch)}>
          + New Person
        </button>
      </div>
      <div style={subtitleStyle}>People directory</div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <select style={inputStyle} value={filters.organization_id} onChange={(e) => handleFilter("organization_id", e.target.value)}>
          <option value="">All Organizations</option>
          {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
        <input
          style={{ ...inputStyle, minWidth: 200 }}
          placeholder="Search people..."
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
        ) : people.length === 0 ? (
          <EmptyState
            title="No people found"
            message="Adjust filters or add a new person."
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
    </div>
  );
}
