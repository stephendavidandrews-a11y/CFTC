import React from "react";
import theme from "../../styles/theme";

export default function PriorityBadge({ label, score }) {
  const p = theme.priority[label] || theme.priority.low;

  return (
    <span
      title={score != null ? `Priority Score: ${Math.round(score)}/100` : undefined}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "3px 10px", borderRadius: 4,
        fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
        background: p.bg, color: p.text,
        border: `1px solid ${p.text}22`,
        cursor: score != null ? "help" : "default",
      }}
    >
      {label === "critical" && <span style={{ fontSize: 9 }}>●</span>}
      {p.label}
      {score != null && (
        <span style={{ fontSize: 10, opacity: 0.7 }}>{Math.round(score)}</span>
      )}
    </span>
  );
}
