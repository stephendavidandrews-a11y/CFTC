import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import { getOrganization, deleteOrganization } from "../../api/tracker";
import Badge from "../../components/shared/Badge";
import { useDrawer } from "../../contexts/DrawerContext";
import EmptyState from "../../components/shared/EmptyState";

/* ── Styles ─────────────────────────────────────────────────────── */

const btnEdit = {
  padding: "8px 16px", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer",
  background: theme.bg.input, color: theme.text.secondary,
  border: `1px solid ${theme.border.default}`,
};

const btnDelete = {
  padding: "8px 16px", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer",
  background: "rgba(239,68,68,0.1)", color: "#f87171",
  border: "1px solid rgba(239,68,68,0.25)",
};

const btnSmall = {
  background: theme.accent.blue, color: "#fff", border: "none",
  borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 600, cursor: "pointer",
};

const thStyle = {
  textAlign: "left", padding: "6px 8px", color: theme.text.dim, fontWeight: 600,
  fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", borderBottom: `1px solid ${theme.border.subtle}`,
};

const tdStyle = { padding: "8px 8px" };

/* ── Badge color maps ───────────────────────────────────────────── */

const CATEGORY_COLORS = {
  "Internal client":     { bg: "#1e3a5f", text: "#60a5fa" },
  "OGC peer":            { bg: "#1a4731", text: "#34d399" },
  "Leadership":          { bg: "#3b1f6e", text: "#a78bfa" },
  "Hill contact":        { bg: "#4a2832", text: "#f87171" },
  "External stakeholder":{ bg: "#4a3728", text: "#fbbf24" },
};

const ROLE_COLORS = {
  "client office":     { bg: "#1e3a5f", text: "#60a5fa" },
  "requesting office": { bg: "#3b1f6e", text: "#a78bfa" },
  "reviewing office":  { bg: "#1a4731", text: "#34d399" },
  "lead office":       { bg: "#4a3728", text: "#fbbf24" },
  "partner agency":    { bg: "#1a3a4a", text: "#38bdf8" },
  "counterparty":      { bg: "#4a2832", text: "#f87171" },
  "Hill office":       { bg: "#4a2832", text: "#f87171" },
};

/* ── Helpers ────────────────────────────────────────────────────── */

function formatDate(d) {
  if (!d) return "\u2014";
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  return new Date(val).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function SmallBadge({ label, colors }) {
  const c = colors || { bg: theme.bg.input, text: theme.text.faint };
  return (
    <span style={{
      background: c.bg, color: c.text, padding: "2px 8px",
      borderRadius: 10, fontSize: 11, fontWeight: 500, whiteSpace: "nowrap",
    }}>
      {label || "\u2014"}
    </span>
  );
}

function SectionCard({ title, count, action, children }) {
  return (
    <div style={{
      background: theme.bg.card, borderRadius: 8,
      border: `1px solid ${theme.border.default}`, marginBottom: 16,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "12px 16px", borderBottom: `1px solid ${theme.border.subtle}`,
      }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: theme.text.secondary }}>
          {title}{count != null ? ` (${count})` : ""}
        </h3>
        {action}
      </div>
      <div style={{ padding: "12px 16px" }}>
        {children}
      </div>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────────── */

export default function OrgDetailPage() {
  const { id } = useParams();
  const toast = useToastContext();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();

  const { data: org, loading, error, refetch } = useApi(() => getOrganization(id), [id]);

  React.useEffect(() => { if (org?.name) document.title = org?.name + " | Command Center"; }, [org?.name]);

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading organization...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <EmptyState
          icon="⚠"
          title="Organization not found"
          message="This organization may have been archived or deleted, or the ID may be invalid."
          actionLabel="Go to Organizations"
          onAction={() => navigate("/organizations")}
        />
      </div>
    );
  }
  if (!org) return null;

  const people = org.people || [];
  const matters = org.matters || [];
  const children = org.children || [];
  const meetings = org.meetings || [];
  const typeColors = theme.orgType[org.organization_type] || theme.orgType["Other"] || { bg: theme.bg.input, text: theme.text.faint };
  const isActive = org.is_active !== 0 && org.is_active !== false;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Breadcrumb */}
      <div style={{ fontSize: 12, color: theme.text.dim, marginBottom: 12 }}>
        <span
          style={{ cursor: "pointer", color: theme.accent.blueLight }}
          onClick={() => navigate("/organizations")}
        >Organizations</span>
        <span style={{ margin: "0 6px" }}>/</span>
        <span>{org.name}</span>
      </div>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: theme.text.primary }}>{org.name}</h1>
            {org.short_name && <span style={{ color: theme.text.dim, fontSize: 14 }}>({org.short_name})</span>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
            <SmallBadge label={org.organization_type} colors={typeColors} />
            {org.parent_org_name && (
              <>
                <span style={{ color: theme.text.dim }}>Parent:</span>
                <span
                  style={{ color: theme.accent.blueLight, cursor: org.parent_organization_id ? "pointer" : "default" }}
                  onClick={() => org.parent_organization_id && navigate(`/organizations/${org.parent_organization_id}`)}
                >{org.parent_org_name}</span>
              </>
            )}
            <SmallBadge
              label={isActive ? "Active" : "Inactive"}
              colors={isActive ? { bg: "#1a4731", text: "#34d399" } : { bg: "#1f2937", text: "#6b7280" }}
            />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={btnEdit} onClick={() => openDrawer("organization", org, refetch)}>
            Edit Organization
          </button>
          <button style={btnDelete} onClick={async () => {
            if (!window.confirm(`Deactivate "${org.name}"? This will mark the organization as inactive.`)) return;
            try {
              await deleteOrganization(id);
              navigate("/organizations");
            } catch (e) { toast.error(e.message || "Operation failed"); }
          }}>
            Delete
          </button>
        </div>
      </div>

      {/* Notes */}
      {org.notes && (
        <div style={{
          background: theme.bg.card, borderRadius: 8, border: `1px solid ${theme.border.default}`,
          padding: "12px 16px", marginBottom: 20, fontSize: 13, color: theme.text.muted, lineHeight: 1.6,
        }}>
          {org.notes}
        </div>
      )}

      {/* Jurisdiction (if present and no notes, show standalone; if notes shown, show inline) */}
      {org.jurisdiction && !org.notes && (
        <div style={{
          background: theme.bg.card, borderRadius: 8, border: `1px solid ${theme.border.default}`,
          padding: "12px 16px", marginBottom: 20,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Jurisdiction
          </span>
          <div style={{ fontSize: 13, color: theme.text.secondary, marginTop: 2 }}>{org.jurisdiction}</div>
        </div>
      )}

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* ── Left column ── */}
        <div>
          {/* Key People */}
          <SectionCard
            title="Key People"
            count={people.length}
            action={
              <button style={btnSmall} onClick={() => openDrawer("person", { organization_id: id }, refetch)}>
                + Add Person
              </button>
            }
          >
            {people.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint }}>No people in this organization.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Name", "Title", "Category", "Last Contact", "Next Needed"].map((col) => (
                      <th key={col} style={thStyle}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {people.map((p) => (
                    <tr
                      key={p.id}
                      style={{ borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer" }}
                      onClick={() => navigate(`/people/${p.id}`)}
                    >
                      <td style={{ ...tdStyle, color: theme.accent.blueLight, fontWeight: 500 }}>{p.full_name}</td>
                      <td style={{ ...tdStyle, color: theme.text.muted }}>{p.title || "\u2014"}</td>
                      <td style={tdStyle}>
                        <SmallBadge label={p.relationship_category} colors={CATEGORY_COLORS[p.relationship_category]} />
                      </td>
                      <td style={{ ...tdStyle, color: theme.text.muted }}>{formatDate(p.last_interaction_date)}</td>
                      <td style={{ ...tdStyle, color: p.next_interaction_needed_date ? theme.accent.yellowLight : theme.text.dim }}>
                        {formatDate(p.next_interaction_needed_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>

          {/* Child Organizations */}
          {children.length > 0 && (
            <SectionCard title="Child Organizations" count={children.length}>
              {children.map((child) => (
                <div
                  key={child.id}
                  onClick={() => navigate(`/organizations/${child.id}`)}
                  style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "6px 0",
                    borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer",
                  }}
                >
                  <span style={{ color: theme.accent.blueLight, fontSize: 13, fontWeight: 500 }}>{child.name}</span>
                  {child.short_name && <span style={{ color: theme.text.dim, fontSize: 12 }}>({child.short_name})</span>}
                  <SmallBadge
                    label={child.organization_type}
                    colors={theme.orgType[child.organization_type] || theme.orgType["Other"]}
                  />
                </div>
              ))}
            </SectionCard>
          )}
        </div>

        {/* ── Right column ── */}
        <div>
          {/* Active Matters */}
          <SectionCard title="Active Matters" count={matters.length}>
            {matters.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint }}>No active matters linked to this organization.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Matter", "Org Role", "Status", "Priority", "Next Step"].map((col) => (
                      <th key={col} style={thStyle}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matters.map((m) => {
                    const st = theme.status[m.status] || { bg: theme.bg.input, text: theme.text.faint };
                    const pr = theme.priority[m.priority] || { bg: theme.bg.input, text: theme.text.faint };
                    return (
                      <tr
                        key={m.id}
                        style={{ borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer" }}
                        onClick={() => navigate(`/matters/${m.id}`)}
                      >
                        <td style={tdStyle}>
                          <div style={{ color: theme.accent.blueLight, fontWeight: 500 }}>{m.title}</div>
                          {m.matter_number && <div style={{ color: theme.text.dim, fontSize: 10 }}>{m.matter_number}</div>}
                        </td>
                        <td style={tdStyle}>
                          <SmallBadge label={m.organization_role} colors={ROLE_COLORS[m.organization_role]} />
                        </td>
                        <td style={tdStyle}>
                          <Badge bg={st.bg} text={st.text} label={st.label || m.status || "\u2014"} />
                        </td>
                        <td style={tdStyle}>
                          <Badge bg={pr.bg} text={pr.text} label={pr.label || m.priority || "\u2014"} />
                        </td>
                        <td style={{ ...tdStyle, color: theme.text.muted, fontSize: 11, maxWidth: 180 }}>
                          {m.next_step || "\u2014"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </SectionCard>

          {/* Recent Meetings */}
          <SectionCard title="Recent Meetings" count={meetings.length}>
            {meetings.length === 0 ? (
              <div style={{ fontSize: 13, color: theme.text.faint }}>No recent meetings found.</div>
            ) : (
              meetings.map((mtg) => (
                <div
                  key={mtg.id}
                  style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px 0", borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer",
                  }}
                  onClick={() => {/* future: navigate to meeting detail */}}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: theme.text.secondary }}>{mtg.title}</div>
                    <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>
                      {formatDate(mtg.date_time_start)}
                      {mtg.meeting_type && (
                        <> &middot; <span style={{ color: theme.text.muted }}>{mtg.meeting_type}</span></>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
