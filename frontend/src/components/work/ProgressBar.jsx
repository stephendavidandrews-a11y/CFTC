import React from "react";
import theme from "../../styles/theme";

export default function ProgressBar({ completed, total, width = 80 }) {
  if (total === 0) return null;
  const pct = Math.round((completed / total) * 100);
  const color = pct === 100 ? theme.accent.green : theme.accent.blue;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width, height: 6, background: "#1f2937",
        borderRadius: 3, overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`, height: "100%",
          background: color, borderRadius: 3,
          transition: "width 0.3s ease",
        }} />
      </div>
      <span style={{ fontSize: 11, color: theme.text.dim, whiteSpace: "nowrap" }}>
        {completed}/{total}
      </span>
    </div>
  );
}
