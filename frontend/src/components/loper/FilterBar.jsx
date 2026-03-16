import React, { useState } from "react";
import theme from "../../styles/theme";

const RULE_ACTIONS = ["Amend", "Defend", "Reinterpret", "Manual review", "Deprioritize"];
const GUIDANCE_ACTIONS = ["Withdraw", "Codify", "Narrow", "Maintain", "Manual review", "Deprioritize"];
const LEGAL_THEORIES = [
  "Loper Bright", "Major Questions", "CBA Deficiency", "N&C Deficiency",
  "Alternatives", "Vagueness", "First Amendment", "Nondelegation",
];
const VALIDATION_OPTIONS = [
  { value: "confirmed", label: "Confirmed" },
  { value: "none", label: "No S2 Data" },
];

const chipStyle = (active) => ({
  padding: "4px 10px",
  borderRadius: 6,
  fontSize: 11,
  fontWeight: 600,
  cursor: "pointer",
  border: `1px solid ${active ? theme.accent.blue : theme.border.default}`,
  background: active ? "rgba(59,130,246,0.15)" : "transparent",
  color: active ? theme.accent.blueLight : theme.text.dim,
  transition: "all 0.15s",
  whiteSpace: "nowrap",
});

const inputStyle = {
  padding: "6px 10px",
  borderRadius: 6,
  background: theme.bg.input,
  border: `1px solid ${theme.border.default}`,
  color: theme.text.secondary,
  fontSize: 12,
  outline: "none",
  fontFamily: theme.font.family,
};

/**
 * FilterBar for Explorer page.
 *
 * Props:
 *  mode: "rules" | "guidance"
 *  filters: { action_category, vulnerability, min_score, max_score, search, validation, has_dissent, has_challenge }
 *  onChange: (newFilters) => void
 */
export default function FilterBar({ mode = "rules", filters = {}, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const actions = mode === "rules" ? RULE_ACTIONS : GUIDANCE_ACTIONS;

  const update = (key, value) => {
    const next = { ...filters, [key]: value };
    onChange(next);
  };

  const toggleChip = (key, value) => {
    update(key, filters[key] === value ? "" : value);
  };

  return (
    <div
      style={{
        background: theme.bg.card,
        borderRadius: 10,
        border: `1px solid ${theme.border.default}`,
        padding: "12px 16px",
        marginBottom: 16,
      }}
    >
      {/* Row 1: Search + action chips */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <input
          type="text"
          placeholder={mode === "rules" ? "Search rules..." : "Search guidance..."}
          value={filters.search || ""}
          onChange={(e) => update("search", e.target.value)}
          style={{ ...inputStyle, width: 200 }}
        />

        <div style={{ height: 20, width: 1, background: theme.border.default }} />

        <span style={{ fontSize: 10, color: theme.text.faint, fontWeight: 700, textTransform: "uppercase" }}>
          Action:
        </span>
        {actions.map((a) => (
          <button
            key={a}
            style={chipStyle(filters.action_category === a)}
            onClick={() => toggleChip("action_category", a)}
          >
            {a}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            ...chipStyle(expanded),
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          {expanded ? "Less" : "More"} Filters {expanded ? "▴" : "▾"}
        </button>

        {Object.values(filters).some((v) => v !== "" && v !== null && v !== undefined) && (
          <button
            onClick={() => onChange({})}
            style={{ ...chipStyle(false), color: theme.accent.red, borderColor: "rgba(239,68,68,0.3)" }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Row 2: Expanded filters */}
      {expanded && (
        <div
          style={{
            display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
            marginTop: 10, paddingTop: 10,
            borderTop: `1px solid ${theme.border.subtle}`,
          }}
        >
          <span style={{ fontSize: 10, color: theme.text.faint, fontWeight: 700, textTransform: "uppercase" }}>
            Theory:
          </span>
          {LEGAL_THEORIES.map((t) => (
            <button
              key={t}
              style={chipStyle(filters.vulnerability === t)}
              onClick={() => toggleChip("vulnerability", t)}
            >
              {t}
            </button>
          ))}

          <div style={{ height: 20, width: 1, background: theme.border.default }} />

          <span style={{ fontSize: 10, color: theme.text.faint, fontWeight: 700, textTransform: "uppercase" }}>
            Score:
          </span>
          <input
            type="number"
            placeholder="Min"
            value={filters.min_score ?? ""}
            onChange={(e) => update("min_score", e.target.value || null)}
            style={{ ...inputStyle, width: 60 }}
            min={0}
            max={10}
            step={0.5}
          />
          <span style={{ color: theme.text.faint, fontSize: 11 }}>–</span>
          <input
            type="number"
            placeholder="Max"
            value={filters.max_score ?? ""}
            onChange={(e) => update("max_score", e.target.value || null)}
            style={{ ...inputStyle, width: 60 }}
            min={0}
            max={10}
            step={0.5}
          />

          <div style={{ height: 20, width: 1, background: theme.border.default }} />

          <span style={{ fontSize: 10, color: theme.text.faint, fontWeight: 700, textTransform: "uppercase" }}>
            S2:
          </span>
          {VALIDATION_OPTIONS.map((o) => (
            <button
              key={o.value}
              style={chipStyle(filters.validation === o.value)}
              onClick={() => toggleChip("validation", o.value)}
            >
              {o.label}
            </button>
          ))}

          {mode === "rules" && (
            <>
              <div style={{ height: 20, width: 1, background: theme.border.default }} />
              <button
                style={chipStyle(filters.has_dissent)}
                onClick={() => update("has_dissent", !filters.has_dissent || null)}
              >
                Dissent
              </button>
              <button
                style={chipStyle(filters.has_challenge)}
                onClick={() => update("has_challenge", !filters.has_challenge || null)}
              >
                Challenged
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
