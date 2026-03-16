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

const ITEM_TYPES = [
  { value: "NPRM", label: "NPRM" },
  { value: "IFR", label: "Interim Final Rule" },
  { value: "ANPRM", label: "Advance NPRM" },
  { value: "DFR", label: "Direct Final Rule" },
  { value: "final_rule", label: "Final Rule" },
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
  { key: "title", label: "Title", width: "26%" },
  {
    key: "fr_citation", label: "FR Citation", width: "12%",
    render: (v, row) => {
      if (!v && !row.fr_url) return <span style={{ color: theme.text.ghost }}>—</span>;
      const label = v || row.fr_doc_number || "View";
      if (row.fr_url) {
        return (
          <a
            href={row.fr_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              color: theme.accent.blueLight, textDecoration: "none",
              fontSize: 12, fontFamily: theme.font.mono,
            }}
            onMouseEnter={(e) => (e.target.style.textDecoration = "underline")}
            onMouseLeave={(e) => (e.target.style.textDecoration = "none")}
          >{label}</a>
        );
      }
      return <span style={{ fontSize: 12, color: theme.text.secondary, fontFamily: theme.font.mono }}>{label}</span>;
    },
  },
  { key: "docket_number", label: "Docket", width: "12%" },
  {
    key: "item_type", label: "Type", width: "10%",
    render: (v) => {
      const t = ITEM_TYPES.find((t) => t.value === v);
      return <Badge bg="#172554" text={theme.accent.blueLight} label={t ? t.label : v || "—"} />;
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
  { key: "lead_attorney_name", label: "Lead", width: "8%" },
];

const EMPTY_FORM = {
  title: "", short_title: "", item_type: "NPRM", docket_number: "",
  rin: "", fr_citation: "", description: "",
  chairman_priority: false, lead_attorney_id: "", backup_attorney_id: "",
};

export default function PipelinePage() {
  const navigate = useNavigate();
  const toast = useToastContext();
  const [itemType, setItemType] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("kanban"); // "kanban" | "table"
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [creating, setCreating] = useState(false);

  const { data: kanban, loading: kanbanLoading, refetch: refetchKanban } = useApi(
    () => getKanban("rulemaking", itemType),
    [itemType]
  );

  const { data: itemsResp, loading: itemsLoading, refetch: refetchItems } = useApi(
    () => listItems({ module: "rulemaking", status: statusFilter || undefined, page_size: 500 }),
    [statusFilter]
  );

  const { data: team } = useApi(() => listTeam(), []);

  const { data: withdrawnResp } = useApi(
    () => listItems({ module: "rulemaking", status: "withdrawn", page_size: 50 }),
    []
  );
  const withdrawnItems = withdrawnResp?.items || withdrawnResp || [];

  const items = itemsResp?.items || itemsResp || [];

  const filteredItems = useMemo(() => {
    let result = items;
    if (itemType) {
      result = result.filter((it) => it.item_type === itemType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (it) =>
          (it.title || "").toLowerCase().includes(q) ||
          (it.docket_number || "").toLowerCase().includes(q) ||
          (it.short_title || "").toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, itemType, searchQuery]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const payload = {
        module: "rulemaking",
        title: form.title,
        short_title: form.short_title || undefined,
        item_type: form.item_type,
        docket_number: form.docket_number || undefined,
        rin: form.rin || undefined,
        fr_citation: form.fr_citation || undefined,
        description: form.description || undefined,
        chairman_priority: form.chairman_priority || undefined,
        lead_attorney_id: form.lead_attorney_id ? Number(form.lead_attorney_id) : undefined,
        backup_attorney_id: form.backup_attorney_id ? Number(form.backup_attorney_id) : undefined,
      };
      const result = await createItem(payload);
      setShowCreate(false);
      setForm({ ...EMPTY_FORM });
      toast.success("Rulemaking item created");
      refetchKanban();
      refetchItems();
      if (result?.id) navigate(`/pipeline/${result.id}`);
    } catch (err) {
      toast.error("Failed to create item: " + (err.message || "Unknown error"));
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
            Rulemaking Pipeline
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
        >+ New Item</button>
      </div>

      {/* Toolbar */}
      <div style={{
        display: "flex", gap: 10, alignItems: "center", marginBottom: 18, flexWrap: "wrap",
      }}>
        {/* Search */}
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search items..."
          style={{ ...inputStyle, width: 220 }}
        />

        {/* Item type filter */}
        <select
          value={itemType || ""}
          onChange={(e) => setItemType(e.target.value || null)}
          style={{ ...inputStyle, width: 160, cursor: "pointer" }}
        >
          <option value="">All Types</option>
          {ITEM_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ ...inputStyle, width: 140, cursor: "pointer" }}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* View toggle */}
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
        <div style={{ padding: 40, textAlign: "center", color: theme.text.dim }}>Loading pipeline...</div>
      ) : viewMode === "kanban" ? (
        kanban ? (
          <KanbanBoard
            columns={kanban.columns}
            onCardClick={(item) => navigate(`/pipeline/${item.id}`)}
          />
        ) : null
      ) : (
        <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 16 }}>
          <DataTable
            columns={TABLE_COLUMNS}
            data={filteredItems}
            onRowClick={(row) => navigate(`/pipeline/${row.id}`)}
            pageSize={25}
            emptyMessage="No rulemaking items found"
          />
        </div>
      )}

      {/* Withdrawn Rulemakings */}
      {withdrawnItems.length > 0 && (
        <div style={{
          background: theme.bg.card, borderRadius: 10,
          border: `1px solid ${theme.border.default}`,
          borderLeft: `3px solid ${theme.accent.red}`,
          padding: 20, marginTop: 24,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: theme.accent.red, margin: 0 }}>
              Withdrawn Rulemakings
            </h3>
            <span style={{
              padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 700,
              background: "rgba(239,68,68,0.15)", color: theme.accent.red,
            }}>{withdrawnItems.length}</span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${theme.border.default}` }}>
                {["Title", "RIN", "FR Citation", "Type"].map((h) => (
                  <th key={h} style={{
                    textAlign: "left", padding: "8px 12px", fontSize: 10,
                    fontWeight: 700, color: theme.text.faint, textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {withdrawnItems.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => navigate(`/pipeline/${item.id}`)}
                  style={{ borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer" }}
                >
                  <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.secondary, fontWeight: 500 }}>
                    {item.title}
                  </td>
                  <td style={{ padding: "10px 12px", fontSize: 12, color: theme.text.dim, fontFamily: theme.font.mono }}>
                    {item.rin || "—"}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {item.fr_url ? (
                      <a
                        href={item.fr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          fontSize: 12, color: theme.accent.blueLight,
                          textDecoration: "none", fontFamily: theme.font.mono,
                        }}
                        onMouseEnter={(e) => (e.target.style.textDecoration = "underline")}
                        onMouseLeave={(e) => (e.target.style.textDecoration = "none")}
                      >{item.fr_citation || item.fr_doc_number || "View"} ↗</a>
                    ) : (
                      <span style={{ fontSize: 12, color: theme.text.dim, fontFamily: theme.font.mono }}>
                        {item.fr_citation || "—"}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{
                      padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                      background: "rgba(239,68,68,0.12)", color: theme.accent.red,
                    }}>Withdrawn</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="New Rulemaking Item" width={620}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Row: Type + Chairman Priority */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 14, alignItems: "end" }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Item Type</label>
              <select
                value={form.item_type}
                onChange={(e) => setForm({ ...form, item_type: e.target.value })}
                style={{ ...inputStyle, cursor: "pointer" }}
              >
                {ITEM_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <label style={{
              display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
              padding: "8px 14px", borderRadius: 6,
              background: form.chairman_priority ? "rgba(245,158,11,0.12)" : theme.bg.input,
              border: `1px solid ${form.chairman_priority ? theme.accent.yellow : theme.border.default}`,
            }}>
              <input
                type="checkbox"
                checked={form.chairman_priority}
                onChange={(e) => setForm({ ...form, chairman_priority: e.target.checked })}
                style={{ accentColor: theme.accent.yellow }}
              />
              <span style={{ fontSize: 12, fontWeight: 600, color: form.chairman_priority ? theme.accent.yellowLight : theme.text.dim }}>
                Chairman Priority
              </span>
            </label>
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Title *</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g., Event Contracts Rulemaking"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Short Title</label>
            <input
              value={form.short_title}
              onChange={(e) => setForm({ ...form, short_title: e.target.value })}
              placeholder="e.g., Event Contracts"
              style={inputStyle}
            />
          </div>

          {/* Row: Docket + RIN + FR Citation */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>Docket Number</label>
              <input
                value={form.docket_number}
                onChange={(e) => setForm({ ...form, docket_number: e.target.value })}
                placeholder="CFTC-2025-0001"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>RIN</label>
              <input
                value={form.rin}
                onChange={(e) => setForm({ ...form, rin: e.target.value })}
                placeholder="3038-AF12"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: theme.text.dim, display: "block", marginBottom: 4 }}>FR Citation</label>
              <input
                value={form.fr_citation}
                onChange={(e) => setForm({ ...form, fr_citation: e.target.value })}
                placeholder="90 FR 12345"
                style={inputStyle}
              />
            </div>
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
          >{creating ? "Creating..." : "Create Item"}</button>
        </div>
      </Modal>
    </div>
  );
}
