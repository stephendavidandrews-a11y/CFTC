import React from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { listOrganizations } from "../../api/tracker";
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

export default function OrganizationsPage() {
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const { data, loading, error, refetch } = useApi(() => listOrganizations({}), []);

  const orgs = data?.items || data || [];

  const columns = [
    { key: "name", label: "Name" },
    { key: "short_name", label: "Short Name", width: 120 },
    { key: "organization_type", label: "Type", width: 130 },
    { key: "parent_org_name", label: "Parent Org", width: 180 },
    { key: "people_count", label: "People", width: 80 },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Organizations</div>
        <button style={btnPrimary} onClick={() => openDrawer("organization", null, refetch)}>
          + New Organization
        </button>
      </div>
      <div style={subtitleStyle}>All organizations</div>

      <div style={cardStyle}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: theme.text.faint, fontSize: 13 }}>Loading...</div>
        ) : error ? (
          <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
        ) : orgs.length === 0 ? (
          <EmptyState
            title="No organizations"
            message="Add your first organization."
            actionLabel="New Organization"
            onAction={() => openDrawer("organization", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={orgs}
            onRowClick={(row) => navigate(`/organizations/${row.id}`)}
          />
        )}
      </div>
    </div>
  );
}
