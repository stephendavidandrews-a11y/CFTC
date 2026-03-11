import React, { useState } from "react";
import DataTable from "../components/shared/DataTable";
import Badge from "../components/shared/Badge";
import Modal from "../components/shared/Modal";
import theme from "../styles/theme";
import { useApi } from "../hooks/useApi";
import { useToastContext } from "../contexts/ToastContext";
import { getEOActions, listItems, updateItem } from "../api/pipeline";

const STATUS_COLORS = {
  in_progress: { bg: "#1e3a5f", text: "#60a5fa", label: "In Progress" },
  completed: { bg: "#14532d", text: "#4ade80", label: "Completed" },
  superseded: { bg: "#422006", text: "#fbbf24", label: "Superseded" },
  not_started: { bg: "#1f2937", text: "#9ca3af", label: "Not Started" },
  pending: { bg: "#1e3a5f", text: "#60a5fa", label: "Pending" },
};

const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "not_started", label: "Not Started" },
  { value: "superseded", label: "Superseded" },
];

const inputStyle = {
  width: "100%", padding: "8px 12px", borderRadius: 6,
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  color: theme.text.secondary, fontSize: 13, outline: "none",
  fontFamily: theme.font.family,
};

const TABLE_COLUMNS = [
  {
    key: "action_description", label: "Action", width: "35%",
    render: (v, row) => v || row.title || `Action #${row.id}`,
  },
  {
    key: "status", label: "Status", width: "12%",
    render: (v) => {
      const s = STATUS_COLORS[v] || STATUS_COLORS.not_started;
      return <Badge bg={s.bg} text={s.text} label={s.label} />;
    },
  },
  {
    key: "deadline", label: "Deadline", width: "12%",
    render: (v) => (
      <span style={{ fontFamily: theme.font.mono, fontSize: 12, color: theme.text.dim }}>
        {v || "—"}
      </span>
    ),
  },
  { key: "cftc_role", label: "CFTC Role", width: "14%" },
  { key: "priority", label: "Priority", width: "10%" },
  {
    key: "_link", label: "", width: "7%", sortable: false,
    render: (_, row) => (
      <span style={{ fontSize: 11, color: theme.accent.blueLight, fontWeight: 600 }}>Link</span>
    ),
  },
];

export default function EOPage() {
  const toast = useToastContext();
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [showLinkModal, setShowLinkModal] = useState(null); // EO action or null
  const [searchQuery, setSearchQuery] = useState("");
  const [linking, setLinking] = useState(false);

  const { data: actions, loading, error, refetch } = useApi(() => getEOActions(), []);

  // Search pipeline items for linking
  const { data: searchResults } = useApi(
    () => (searchQuery.length >= 2 ? listItems({ search: searchQuery, page_size: 20 }) : Promise.resolve(null)),
    [searchQuery]
  );

  const allActions = actions || [];

  // Get unique CFTC roles for filter
  const roles = [...new Set(allActions.map((a) => a.cftc_role).filter(Boolean))];

  // Apply filters
  const filteredActions = allActions.filter((a) => {
    if (statusFilter && a.status !== statusFilter) return false;
    if (roleFilter && a.cftc_role !== roleFilter) return false;
    return true;
  });

  const handleRowClick = (row) => {
    setShowLinkModal(row);
    setSearchQuery("");
  };

  const handleLink = async (pipelineItem) => {
    if (!showLinkModal) return;
    setLinking(true);
    try {
      await updateItem(pipelineItem.id, { eo_action_item_id: showLinkModal.id });
      toast.success(`Linked "${pipelineItem.title}" to EO action`);
      setShowLinkModal(null);
      setSearchQuery("");
      refetch();
    } catch (err) {
      toast.error("Failed to link: " + (err.message || "Unknown error"));
    } finally {
      setLinking(false);
    }
  };

  const pipelineItems = searchResults?.items || searchResults || [];

  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 6, letterSpacing: "-0.02em" }}>
        Executive Order Tracker
      </h2>
      <p style={{ fontSize: 13, color: theme.text.faint, marginBottom: 20 }}>
        {filteredActions.length} action items
      </p>

      {error && (
        <div style={{
          background: "#111827", borderRadius: 10, border: "1px solid #1f2937",
          padding: 40, textAlign: "center",
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.muted }}>
            EO Tracker database not connected
          </div>
          <div style={{ fontSize: 12, color: theme.text.faint, marginTop: 8 }}>
            Connect eo_tracker.db to see executive order data
          </div>
        </div>
      )}

      {!error && (
        <>
          {/* Filters */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ ...inputStyle, width: 160, cursor: "pointer" }}
            >
              {STATUS_FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              style={{ ...inputStyle, width: 200, cursor: "pointer" }}
            >
              <option value="">All CFTC Roles</option>
              {roles.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>

          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
            {loading ? (
              <div style={{ padding: 30, textAlign: "center", color: theme.text.dim }}>Loading...</div>
            ) : (
              <DataTable
                columns={TABLE_COLUMNS}
                data={filteredActions}
                onRowClick={handleRowClick}
                pageSize={25}
                emptyMessage="No EO action items found"
              />
            )}
          </div>
        </>
      )}

      {/* Link to Pipeline Item Modal */}
      <Modal isOpen={!!showLinkModal} onClose={() => setShowLinkModal(null)} title="Link to Pipeline Item" width={560}>
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, color: theme.text.faint, marginBottom: 8 }}>
            Linking EO action: <strong style={{ color: theme.text.secondary }}>
              {showLinkModal?.action_description || showLinkModal?.title || ""}
            </strong>
          </div>
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search pipeline items by title..."
            style={inputStyle}
            autoFocus
          />
        </div>

        {searchQuery.length >= 2 && (
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {pipelineItems.length === 0 ? (
              <div style={{ padding: 20, textAlign: "center", color: theme.text.faint, fontSize: 12 }}>
                No items found
              </div>
            ) : (
              pipelineItems.map((item) => (
                <div
                  key={item.id}
                  onClick={() => !linking && handleLink(item)}
                  style={{
                    padding: "10px 14px", marginBottom: 4, borderRadius: 6,
                    background: theme.bg.cardHover, border: `1px solid ${theme.border.default}`,
                    cursor: linking ? "wait" : "pointer", fontSize: 13,
                    transition: "border-color 0.15s",
                  }}
                >
                  <div style={{ fontWeight: 600, color: theme.text.secondary }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>
                    {item.module || ""} · {item.item_type || ""} · {item.docket_number || "No docket"}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {searchQuery.length > 0 && searchQuery.length < 2 && (
          <div style={{ padding: 12, textAlign: "center", color: theme.text.faint, fontSize: 12 }}>
            Type at least 2 characters to search
          </div>
        )}
      </Modal>
    </div>
  );
}
