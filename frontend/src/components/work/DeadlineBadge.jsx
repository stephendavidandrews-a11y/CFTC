import React from "react";
import theme from "../../styles/theme";

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr + "T00:00:00");
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.ceil((d - now) / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function DeadlineBadge({ date }) {
  if (!date) return null;
  const days = daysUntil(date);
  let color = theme.text.dim;
  if (days !== null) {
    if (days < 0) color = theme.accent.red;
    else if (days <= 3) color = theme.accent.red;
    else if (days <= 7) color = theme.accent.yellow;
  }

  return (
    <span style={{
      fontSize: 11, color, whiteSpace: "nowrap",
      display: "flex", alignItems: "center", gap: 3,
    }}>
      <span style={{ fontSize: 10 }}>{"\u2691"}</span>
      {formatDate(date)}
    </span>
  );
}
