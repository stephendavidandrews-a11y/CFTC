import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getOrganization } from "../../api/tracker";
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
const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };
const labelStyle = { fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em" };
const valStyle = { fontSize: 13, color: theme.text.secondary, marginTop: 2 };

const btnPrimary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: theme.accent.blue, color: "#fff", border: "none", cursor: "pointer",
};

const btnSecondary = {
  padding: "7px 16px", borderRadius: 6, fontSize: 12, fontWeight: 600,
  background: "transparent", color: theme.text.muted,
  border: `1px solid ${theme.border.default}`, cursor: "pointer",
};

export default function OrgDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();

  const { data: org, loading, error, refetch } = useApi(() => getOrganization(id), [id]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading organization...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
      </div>
    );
  }
  if (!org) return null;

  const people = org.people || [];
  const matters = org.matters || [];
  const children = org.children || org.child_organizations || [];

  const typeStyle = org.organization_type
    ? { bg: "rgba(59,130,246,0.12)", text: theme.accent.blue, label: org.organization_type }
    : null;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button onClick={() => navigate("/organizations")} style={{ ...btnSecondary, padding: "5px 10px", fontSize: 11 }}>
          &larr; Back
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={titleStyle}>{org.name}</span>
            {org.short_name && (
              <span style={{ fontSize: 14, color: theme.text.muted, fontWeight: 400 }}>({org.short_name})</span>
            )}
            {typeStyle && <Badge bg={typeStyle.bg} text={typeStyle.text} label={typeStyle.label} />}
            {org.is_active === false ? (
              <Badge bg="rgba(239,68,68,0.12)" text="#ef4444" label="Inactive" />
            ) : (
              <Badge bg="rgba(34,197,94,0.12)" text="#22c55e" label="Active" />
            )}
          </div>
          {org.parent_org_name && (
            <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 2 }}>
              Parent: {org.parent_org_name}
            </div>
          )}
        </div>
        <button style={btnPrimary} onClick={() => openDrawer("organization", org, refetch)}>
          Edit
        </button>
      </div>

      {/* Info */}
      {(org.jurisdiction || org.notes) && (
        <div style={{ ...cardStyle, marginBottom: 24 }}>
          {org.jurisdiction && (
            <div style={{ marginBottom: org.notes ? 12 : 0 }}>
              <div style={labelStyle}>Jurisdiction</div>
              <div style={valStyle}>{org.jurisdiction}</div>
            </div>
          )}
          {org.notes && (
            <div>
              <div style={labelStyle}>Notes</div>
              <div style={{ ...valStyle, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{org.notes}</div>
            </div>
          )}
        </div>
      )}

      {/* People */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={sectionTitle}>People</div>
        {people.length === 0 ? (
          <EmptyState title="No people" message="No people in this organization." />
        ) : (
          <DataTable
            columns={[
              {
                key: "name", label: "Name",
                render: (v, row) => row.full_name || `${row.first_name || ""} ${row.last_name || ""}`.trim() || "\u2014",
              },
              { key: "title", label: "Title", width: 180 },
              { key: "category", label: "Category", width: 120 },
              { key: "lane", label: "Lane", width: 100 },
            ]}
            data={people}
            onRowClick={(row) => navigate(`/people/${row.id}`)}
          />
        )}
      </div>

      {/* Matters */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={sectionTitle}>Matters</div>
        {matters.length === 0 ? (
          <EmptyState title="No matters" message="No matters linked to this organization." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              { key: "role", label: "Role", width: 150 },
              {
                key: "status", label: "Status", width: 120,
                render: (val) => {
                  const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                  return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
                },
              },
            ]}
            data={matters}
            onRowClick={(row) => row.matter_id && navigate(`/matters/${row.matter_id}`)}
          />
        )}
      </div>

      {/* Child Organizations */}
      {children.length > 0 && (
        <div style={cardStyle}>
          <div style={sectionTitle}>Child Organizations</div>
          <DataTable
            columns={[
              { key: "name", label: "Name" },
              { key: "short_name", label: "Short Name", width: 120 },
              { key: "organization_type", label: "Type", width: 130 },
            ]}
            data={children}
            onRowClick={(row) => navigate(`/organizations/${row.id}`)}
          />
        </div>
      )}
    </div>
  );
}
