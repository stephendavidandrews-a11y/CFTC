import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { useToastContext } from "../../contexts/ToastContext";
import useApi from "../../hooks/useApi";
import { listMeetings, listMatters, updateMeeting, deleteMeeting } from "../../api/tracker";
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

const actionBtnStyle = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: "4px 6px",
  borderRadius: 4,
  fontSize: 14,
  lineHeight: 1,
  transition: "background 0.15s",
};

function formatDateTime(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

export default function MeetingsPage() {
  const navigate = useNavigate();
  const toast = useToastContext();
  const { openDrawer } = useDrawer();
  const [filters, setFilters] = useState({ search: "", date_from: "", date_to: "", matter_id: "" });
  const [confirmAction, setConfirmAction] = useState(null); // { id, action, title }
  const [actionBusy, setActionBusy] = useState({});

  const { data: mattersData } = useApi(() => listMatters({ limit: 500 }), []);
  const { data, loading, error, refetch } = useApi(
    () => listMeetings(filters),
    [filters.search, filters.date_from, filters.date_to, filters.matter_id]
  );

  const handleFilter = useCallback((key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val }));
  }, []);

  const handleMeetingAction = useCallback(
    async (id, action) => {
      setActionBusy((prev) => ({ ...prev, [id]: true }));
      try {
        if (action === "archive") {
          await updateMeeting(id, { status: "archived" });
        } else if (action === "delete") {
          await deleteMeeting(id);
        }
        setConfirmAction(null);
        refetch();
      } catch (err) {
        console.error(`Meeting ${action} failed:`, err);
        toast.error(`Failed to ${action} meeting: ${err.message || err}`);
      } finally {
        setActionBusy((prev) => ({ ...prev, [id]: false }));
      }
    },
    [refetch]
  );

  const meetings = data?.items || data || [];
  const matters = mattersData?.items || mattersData || [];

  const columns = [
    { key: "title", label: "Title" },
    { key: "meeting_type", label: "Type", width: 120 },
    {
      key: "date_time_start", label: "Date/Time", width: 180,
      render: (v) => formatDateTime(v),
    },
    {
      key: "duration", label: "Duration", width: 90,
      render: (v, row) => {
        if (row.date_time_start && row.date_time_end) {
          const mins = Math.round((new Date(row.date_time_end) - new Date(row.date_time_start)) / 60000);
          return mins > 0 ? `${mins} min` : "\u2014";
        }
        return "\u2014";
      },
    },
    { key: "location_or_link", label: "Location", width: 150 },
    { key: "matter_title", label: "Matter", width: 180 },
    {
      key: "_actions",
      label: "",
      width: 70,
      sortable: false,
      render: (_val, row) => (
        <div
          style={{ display: "flex", gap: 2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            title="Archive meeting"
            style={{ ...actionBtnStyle, color: theme.text.muted }}
            disabled={actionBusy[row.id]}
            onClick={() =>
              setConfirmAction({
                id: row.id,
                action: "archive",
                title: row.title,
              })
            }
            onMouseEnter={(e) => (e.target.style.background = theme.bg.input)}
            onMouseLeave={(e) => (e.target.style.background = "transparent")}
          >
            ✓
          </button>
          <button
            title="Delete meeting"
            style={{ ...actionBtnStyle, color: theme.accent.red }}
            disabled={actionBusy[row.id]}
            onClick={() =>
              setConfirmAction({
                id: row.id,
                action: "delete",
                title: row.title,
              })
            }
            onMouseEnter={(e) =>
              (e.target.style.background = `${theme.accent.red}22`)
            }
            onMouseLeave={(e) => (e.target.style.background = "transparent")}
          >
            ✕
          </button>
        </div>
      ),
    },
  ];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={titleStyle}>Meetings</div>
        <button style={btnPrimary} onClick={() => openDrawer("meeting", null, refetch)}>
          + New Meeting
        </button>
      </div>
      <div style={subtitleStyle}>All scheduled meetings</div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 20 }}>
        <input
          style={{ ...inputStyle, minWidth: 280 }}
          placeholder="Search meetings by title or purpose..."
          value={filters.search}
          onChange={(e) => handleFilter("search", e.target.value)}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: theme.text.faint }}>From</span>
          <input
            type="date"
            style={inputStyle}
            value={filters.date_from}
            onChange={(e) => handleFilter("date_from", e.target.value)}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: theme.text.faint }}>To</span>
          <input
            type="date"
            style={inputStyle}
            value={filters.date_to}
            onChange={(e) => handleFilter("date_to", e.target.value)}
          />
        </div>
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
        ) : meetings.length === 0 ? (
          <EmptyState
            title="No meetings found"
            message="Adjust filters or schedule a new meeting."
            actionLabel="New Meeting"
            onAction={() => openDrawer("meeting", null, refetch)}
          />
        ) : (
          <DataTable
            columns={columns}
            data={meetings}
            onRowClick={(row) => navigate(`/meetings/${row.id}`)}
          />
        )}
      </div>

      {/* Confirm dialog */}
      {confirmAction && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
          onClick={() => setConfirmAction(null)}
        >
          <div
            style={{
              background: theme.bg.card,
              border: `1px solid ${theme.border.default}`,
              borderRadius: 10,
              padding: 24,
              minWidth: 340,
              maxWidth: 440,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                color: theme.text.primary,
                marginBottom: 12,
              }}
            >
              {confirmAction.action === "archive"
                ? "Archive Meeting?"
                : "Delete Meeting?"}
            </div>
            <div
              style={{
                fontSize: 13,
                color: theme.text.muted,
                marginBottom: 20,
                lineHeight: 1.5,
              }}
            >
              {confirmAction.action === "archive" ? (
                <>
                  This will archive{" "}
                  <strong style={{ color: theme.text.secondary }}>
                    {confirmAction.title}
                  </strong>
                  . It will be hidden from the main list but can be restored later.
                </>
              ) : (
                <>
                  This will permanently delete{" "}
                  <strong style={{ color: theme.text.secondary }}>
                    {confirmAction.title}
                  </strong>
                  . This cannot be undone.
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                style={{
                  ...btnPrimary,
                  background: theme.bg.input,
                  color: theme.text.muted,
                }}
                onClick={() => setConfirmAction(null)}
              >
                Cancel
              </button>
              <button
                style={{
                  ...btnPrimary,
                  background:
                    confirmAction.action === "delete"
                      ? theme.accent.red
                      : theme.accent.blue,
                }}
                disabled={actionBusy[confirmAction.id]}
                onClick={() =>
                  handleMeetingAction(confirmAction.id, confirmAction.action)
                }
              >
                {actionBusy[confirmAction.id]
                  ? "..."
                  : confirmAction.action === "archive"
                    ? "Archive"
                    : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
