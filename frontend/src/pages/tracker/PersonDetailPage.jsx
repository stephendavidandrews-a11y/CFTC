import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getPerson, deletePerson } from "../../api/tracker";
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

function formatDate(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function PersonDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openDrawer } = useDrawer();
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: person, loading, error, refetch } = useApi(() => getPerson(id), [id]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deletePerson(id);
      navigate("/people");
    } catch (err) {
      alert("Failed to delete: " + (err.message || String(err)));
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  if (loading) {
    return <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>Loading person...</div>;
  }
  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{ color: theme.accent.red, fontSize: 13 }}>Error: {error.message || String(error)}</div>
      </div>
    );
  }
  if (!person) return null;

  const fullName = person.full_name || `${person.first_name || ""} ${person.last_name || ""}`.trim();
  const tasks = person.tasks || [];
  const personMatters = person.matters || [];
  const personMeetings = person.meetings || [];

  const infoItems = [
    { label: "Email", value: person.email },
    { label: "Phone", value: person.phone },
    { label: "Category", value: person.relationship_category },
    { label: "Lane", value: person.relationship_lane },
    { label: "Manager", value: person.manager_name },
    { label: "Organization", value: person.org_name },
    { label: "Team Workload", value: person.include_in_team_workload ? "Yes" : "No" },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button onClick={() => navigate("/people")} style={{ ...btnSecondary, padding: "5px 10px", fontSize: 11 }}>
          &larr; Back
        </button>
        <div style={{ flex: 1 }}>
          <div style={titleStyle}>{fullName}</div>
          <div style={{ fontSize: 13, color: theme.text.muted }}>
            {[person.title, person.org_name].filter(Boolean).join(" \u2022 ")}
          </div>
        </div>
        <button style={{ ...btnSecondary, color: "#ef4444", borderColor: "#7f1d1d" }} onClick={() => setShowDeleteConfirm(true)}>
          Delete
        </button>
        <button style={btnPrimary} onClick={() => openDrawer("person", person, refetch)}>
          Edit
        </button>
      </div>

      {/* Info Card */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {infoItems.map((item) => (
            <div key={item.label}>
              <div style={labelStyle}>{item.label}</div>
              <div style={valStyle}>{item.value || "\u2014"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Matters */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={sectionTitle}>Matters</div>
        {personMatters.length === 0 ? (
          <EmptyState title="No matters" message="This person is not linked to any matters." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Matter" },
              { key: "matter_role", label: "Role", width: 130 },
              { key: "engagement_level", label: "Engagement", width: 120 },
            ]}
            data={personMatters}
            onRowClick={(row) => (row.id || row.matter_id) && navigate(`/matters/${row.id || row.matter_id}`)}
          />
        )}
      </div>

      {/* Tasks */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={sectionTitle}>Tasks</div>
        {tasks.length === 0 ? (
          <EmptyState title="No tasks" message="No tasks assigned to this person." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              { key: "matter_title", label: "Matter", width: 180 },
              {
                key: "status", label: "Status", width: 110,
                render: (val) => {
                  const s = theme.status[val] || { bg: theme.bg.input, text: theme.text.faint, label: val };
                  return <Badge bg={s.bg} text={s.text} label={s.label || val || "\u2014"} />;
                },
              },
              { key: "due_date", label: "Due Date", width: 120, render: (v) => formatDate(v) },
            ]}
            data={tasks}
            onRowClick={(row) => openDrawer("task", row, refetch)}
          />
        )}
      </div>

      {/* Meetings */}
      <div style={cardStyle}>
        <div style={sectionTitle}>Meetings</div>
        {personMeetings.length === 0 ? (
          <EmptyState title="No meetings" message="No meetings found." />
        ) : (
          <DataTable
            columns={[
              { key: "title", label: "Title" },
              { key: "date_time_start", label: "Date", width: 140, render: (v) => formatDate(v) },
              { key: "meeting_type", label: "Type", width: 120 },
            ]}
            data={personMeetings}
            onRowClick={(row) => openDrawer("meeting", row, refetch)}
          />
        )}
      </div>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1000,
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={() => !deleting && setShowDeleteConfirm(false)}>
          <div style={{
            background: theme.bg.card, borderRadius: 12,
            border: `1px solid ${theme.border.default}`,
            padding: 28, maxWidth: 400, width: "90%",
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 16, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
              Delete Person
            </div>
            <div style={{ fontSize: 13, color: theme.text.muted, marginBottom: 20 }}>
              Are you sure you want to delete <strong style={{ color: theme.text.secondary }}>{fullName}</strong>?
              This will deactivate the person record.
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button style={btnSecondary} onClick={() => setShowDeleteConfirm(false)} disabled={deleting}>
                Cancel
              </button>
              <button
                style={{ ...btnPrimary, background: "#991b1b", opacity: deleting ? 0.6 : 1 }}
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
