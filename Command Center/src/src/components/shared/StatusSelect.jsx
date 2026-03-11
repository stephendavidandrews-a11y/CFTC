import React from "react";
import theme from "../../styles/theme";

const STATUS_OPTIONS = [
  { value: "active", label: "Active", color: "#60a5fa" },
  { value: "paused", label: "Paused", color: "#fbbf24" },
  { value: "completed", label: "Completed", color: "#4ade80" },
  { value: "withdrawn", label: "Withdrawn", color: "#9ca3af" },
  { value: "archived", label: "Archived", color: "#6b7280" },
];

export default function StatusSelect({ value, onChange, disabled = false }) {
  const current = STATUS_OPTIONS.find((o) => o.value === value) || STATUS_OPTIONS[0];

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          appearance: "none", WebkitAppearance: "none",
          padding: "5px 28px 5px 10px",
          borderRadius: 6, fontSize: 12, fontWeight: 600,
          background: theme.bg.input,
          color: current.color,
          border: `1px solid ${current.color}30`,
          cursor: disabled ? "default" : "pointer",
          outline: "none",
          fontFamily: theme.font.family,
        }}
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <span style={{
        position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", fontSize: 10, color: theme.text.faint,
      }}>▾</span>
    </div>
  );
}
