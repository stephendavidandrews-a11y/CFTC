import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import KanbanBoard from "../components/shared/KanbanBoard";
import DataTable from "../components/shared/DataTable";
import Modal from "../components/shared/Modal";
import Badge from "../components/shared/Badge";
import PriorityBadge from "../components/shared/PriorityBadge";
import theme from "../styles/theme";
import { useApi } from "../hooks/useApi";
import { useToastContext } from "../contexts/ToastContext";
import { getKanban, createItem, listItems, listTeam } from "../api/pipeline";

const ACTION_TYPES = [
  { value: "no_action_letter", label: "No-Action Letter" },
  { value: "exemptive_order", label: "Exemptive Order" },
  { value: "interpretive_guidance", label: "Interpretive Guidance" },
  { value: "advisory_opinion", label: "Advisory Opinion" },
  { value: "petition", label: "Petition" },
  { value: "staff_letter", label: "Staff Letter" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "withdrawn", label: "Withdrawn" },
];

const inputStyle = {
  width: "100%", padding: "8px 12px", borderRadius: 6,
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  color: theme.text.secondary, fontSize: 13, outline: "none",
  fontFamily: theme.font.family,
};

const TABLE_COLUMNS = [
  { key: "title", label: "Title", width: "30%" },
  { key: "requesting_party", label: "Requesting Party", width: "15%" },
  {
    key: "item_type", label: "Type", width: "14%",
    render: (v) => {
      const t = ACTION_TYPES.find((t) => t.value === v);
      return <Badge bg="#1e1b4b" text={theme.accent.purple} label={t ? t.label : v || "—"} />;
    },
  },
  {
    key: "status", label: "Status", width: "10%",
    render: (v) => {
      const s = theme.status[v] || theme.status.active;
      return <Badge bg={s.bg} text={s.text} label={s.label} />;
    },
  },
  {
    key: "priority_score", label: "Priority", width: "10%",
    render: (v, row) => <PriorityBadge score={v} label={row.priority_label} />,
  },
  { key: "current_stage", label: "Stage", width: "12%" },
  { key: "lead_attorney_name", label: "Lead", width: "9%" },
];

const EMPTY_FORM = {
  title: "", item_type: "no_action_letter", requesting_party: "", description: "",
  related_rulemaking_id: "", lead_attorney_id: "", backup_attorney_id: "",
};

export default function RegActionsPage() {
  const navigate = useNavigate();
  const toast = useToastContext();
  const [actionType, setActionType] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("kanban");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [creating, setCreating] = useState(false);

  const { data: kanban, loading: kanbanLoading, refetch: refetchKanban } = useApi(
    () => getKanban("regulatory_action", actionType),
    [actionType]
  );

  const { data: itemsResp, loading: itemsLoading, refetch: refetchItems } = useApi(
    () => listItems({ module: "regulatory_action", status: statusFilter || undefined, page_size: 500 }),
    [statusFilter]
  );

  const { data: team } = useApi(() => listTeam(), []);

  // Fetch rulemakings for the "related rulemaking" dropdown
  const { data: rulemakingsResp } = useApi(
    () => listItems({ module: "rulemaking", page_size: 200 }),
    []
  );

  const items = itemsResp?.items || itemsResp || [];
  const rulemakings = rulemakingsResp?.items || rulemakingsResp || [];

  const filteredItems = useMemo(() => {
    let result = items;
    if (actionType) {
      result = result.filter((it) => it.item_type === actionType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (it) =>
          (it.title || "").toLowerCase().includes(q) ||
          (it.requesting_party || "").toLowerCase().includes(q) ||
          (it.docket_number || "").toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, actionType, searchQuery]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const payload = {
        module: "regulatory_action",
        title: form.title,
        item_type: form.item_type,
        requesting_party: form.requesting_party || undefined,
        description: form.description || undefined,
        related_rulemaking_id: form.related_rulemaking_id ? Number(form.related_rulemaking_id) : undefined,
        lead_attorney_id: form.lead_attorney_id ? Number(form.lead_attorney_id) : undefined,
        backup_attorney_id: form.backup_attorney_id ? Number(form.backup_attorney_id) : undefined,
      };
      const result = await createItem(payload);
      setShowCreate(false);
      setForm({ ...EMPTY_FORM });
      toast.success("Regulatory action created");
      refetchKanban();
      refetchItems();
      if (result?.id) navigate(`/regulatory/${result.id}`);
    } catch (err) {
      toast.error("Failed to create action: " + (err.message || "Unknown error"));
    } finally {
      setCreating(false);
    }
  };

  const teamMembers = team || [];
  const loading = viewMode === "kanban" ? kanbanLoading : itemsLoading;

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0, letterSpacing: "-0.02em" }}>
            Regulatory Actions
          </h2>
          <p style={{ fontSize: 13, color: theme.text.faint, marginTop: 4 }}>
            {viewMode === "kanban"
              ? kanban ? `${kanban.total_items} active items` : "Loading..."
              : `${filteredItems.length} items`}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          style={{
            padding: "8px 16px", borderRadius: 6, border: "none",
            background: theme.accent.blue, color: "#fff",
            fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
        >+ New Action</button>
      </div>

      {/* Toolbar */}
      <div style={{
        display: "flex", gap: 10, alignItems: "center", marginBottom: 18, flexWrap: "wrap",
      }}>
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search actions..."
          style={{ ...inputStyle, width: 220 }}
        />

        <select
          value={actionType || ""}
          onChange={(e) => setActionType(e.target.value || null)}
          style={{ ...inputStyle, width: 180, cursor: "pointer" }}
        >
          <option value="">All Types</option>
          {ACTION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ ...inputStyle, width: 140, cursor: "pointer" }}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <div style={{ marginLeft: "auto", display: "flex", gap: 2 }}>
          {[
            { key: "kanban", label: "Kanban" },
            { key: "table", label: "Table" },
          ].map((v) => (
            <button
              key={v.key}
              onClick={() => setViewMode(v.key)}
              style={{
                padding: "6px 14px", borderRadius: 5, fontSize: 12, fontWeight: 600,
                border: `1px solid ${viewMode === v.key ? theme.accent.blue : theme.border.default}`,
                background: viewMode === v.key ? "rgba(59,130,246,0.15)" : "transparent",
                color: viewMode === v.key ? theme.accent.blueLight : theme.text.dim,
                cursor: "pointer",
              }}
            >{v.label}</button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.dim }}>Loading...</div>
      ) : viewMode === "kanban" ? (
        kanban ? (
          <KanbanBoard
            columns={kanban.columns}
            onCardClick={(item) => navigate(`/regulatory/${item.id}`)}
          />
        ) : null
      ) : (
        <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
          <DataTable
            columns={TABLE_COLUMNS}
            data={filteredItems}
            onRowClick={(row) => navigate(`/regulatory/${row.id}`)}
            pageSize={25}
            emptyMessage="No regulatory actions found"
          />
        </div>
      )}

      {/* Create Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="New Regulatory Action" width={620}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Action Type</label>
            <select
              value={form.item_type}
              onChange={(e) => setForm({ ...form, item_type: e.target.value })}
              style={{ ...inputStyle, cursor: "pointer" }}
            >
              {ACTION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Title *</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g., FCM Position Limit No-Action Relief"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Requesting Party</label>
            <input
              value={form.requesting_party}
              onChange={(e) => setForm({ ...form, requesting_party: e.target.value })}
              placeholder="e.g., ICE Futures U.S."
              style={inputStyle}
            />
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Related Rulemaking</label>
            <select
              value={form.related_rulemaking_id}
              onChange={(e) => setForm({ ...form, related_rulemaking_id: e.target.value })}
              style={{ ...inputStyle, cursor: "pointer" }}
            >
              <option value="">— None —</option>
              {rulemakings.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.short_title || r.title}{r.docket_number ? ` (${r.docket_number})` : ""}
                </option>
              ))}
            </select>
          </div>

          {/* Row: Lead + Backup Attorney */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Lead Attorney</label>
              <select
                value={form.lead_attorney_id}
                onChange={(e) => setForm({ ...form, lead_attorney_id: e.target.value })}
                style={{ ...inputStyle, cursor: "pointer" }}
              >
                <option value="">— Unassigned —</option>
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Backup Attorney</label>
              <select
                value={form.backup_attorney_id}
                onChange={(e) => setForm({ ...form, backup_attorney_id: e.target.value })}
                style={{ ...inputStyle, cursor: "pointer" }}
              >
                <option value="">— Unassigned —</option>
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </div>

          <button
            onClick={handleCreate}
            disabled={!form.title || creating}
            style={{
              padding: "10px 20px", borderRadius: 6, border: "none",
              background: form.title && !creating ? theme.accent.blue : "#1f2937",
              color: form.title && !creating ? "#fff" : theme.text.dim,
              fontSize: 13, fontWeight: 600,
              cursor: form.title && !creating ? "pointer" : "not-allowed",
              marginTop: 6,
            }}
          >{creating ? "Creating..." : "Create Action"}</button>
        </div>
      </Modal>
    </div>
  );
}
