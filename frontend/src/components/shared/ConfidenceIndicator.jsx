import React from "react";
import theme from "../../styles/theme";

/**
 * Shared confidence indicator — dot or bar variant.
 * UI Spec Section 10B:
 *   Green (#4ade80): 0.8–1.0
 *   Amber (#fbbf24): 0.5–0.8
 *   Red (#f87171): below 0.5
 */

function getColor(score) {
  if (score >= 0.8) return "#4ade80";
  if (score >= 0.5) return "#fbbf24";
  return "#f87171";
}

function getLabel(score) {
  if (score >= 0.8) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

export default function ConfidenceIndicator({
  score,
  size = "bar",        // "dot" | "bar"
  showLabel = false,
  label = null,         // optional override label (e.g. "Strong match")
  width = 60,           // bar width in px
}) {
  if (score == null) return null;

  const color = getColor(score);
  const pct = Math.round(score * 100);
  const displayLabel = label || getLabel(score);

  if (size === "dot") {
    return (
      <span
        title={`${pct}% confidence — ${displayLabel}`}
        style={{
          display: "inline-block",
          width: 8, height: 8, borderRadius: "50%",
          background: color,
        }}
      />
    );
  }

  // Bar variant
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{
        width, height: 6, borderRadius: 3,
        background: "rgba(255,255,255,0.08)",
      }}>
        <div style={{
          width: `${pct}%`, height: "100%", borderRadius: 3,
          background: color, transition: "width 0.3s",
        }} />
      </div>
      <span style={{
        fontSize: 11, color, fontWeight: 600,
        fontFamily: theme.font.mono,
      }}>
        {pct}%
      </span>
      {showLabel && (
        <span style={{ fontSize: 10, color: theme.text.faint }}>
          {displayLabel}
        </span>
      )}
    </div>
  );
}
