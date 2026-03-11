import React from "react";
import theme from "../../styles/theme";

const chipStyle = (active) => ({
  padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500,
  border: `1px solid ${active ? theme.accent.blue : "#1f2937"}`,
  background: active ? "rgba(59,130,246,0.12)" : "transparent",
  color: active ? theme.accent.blueLight : theme.text.dim,
  cursor: "pointer", transition: "all 0.15s",
});

const selectStyle = {
  background: theme.bg.input, border: `1px solid ${theme.border.default}`,
  borderRadius: 6, padding: "5px 8px", color: theme.text.primary,
  fontSize: 11, outline: "none", minWidth: 120,
};

const inputStyle = {
  ...selectStyle,
  minWidth: 160,
};

export default function FilterBar({
  filters, setFilters, types = [], team = [],
  showStatus = true, showPriority = true, showType = true, showSearch = true,
  statusOptions,
}) {
  const statuses = statusOptions || ["active", "paused", "completed", "archived"];
  const priorities = ["critical", "high", "medium", "low"];

  const toggle = (key, val) => {
    setFilters((prev) => ({
      ...prev,
      [key]: prev[key] === val ? undefined : val,
    }));
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
      {showStatus && statuses.map((s) => (
        <button
          key={s}
          onClick={() => toggle("status", s)}
          style={chipStyle(filters.status === s)}
        >
          {s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}
        </button>
      ))}

      {showPriority && (
        <select
          value={filters.priority_label || ""}
          onChange={(e) => setFilters((f) => ({ ...f, priority_label: e.target.value || undefined }))}
          style={selectStyle}
        >
          <option value="">All priorities</option>
          {priorities.map((p) => (
            <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
          ))}
        </select>
      )}

      {showType && types.length > 0 && (
        <select
          value={filters.project_type || ""}
          onChange={(e) => setFilters((f) => ({ ...f, project_type: e.target.value || undefined }))}
          style={selectStyle}
        >
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t.type_key} value={t.type_key}>{t.label}</option>
          ))}
        </select>
      )}

      {team.length > 0 && (
        <select
          value={filters.lead_attorney_id || ""}
          onChange={(e) => setFilters((f) => ({ ...f, lead_attorney_id: e.target.value || undefined }))}
          style={selectStyle}
        >
          <option value="">All attorneys</option>
          {team.map((m) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
      )}

      {showSearch && (
        <input
          type="text"
          placeholder="Search..."
          value={filters.search || ""}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value || undefined }))}
          style={inputStyle}
        />
      )}
    </div>
  );
}
