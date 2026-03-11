import React from "react";

/**
 * Horizontal score bar (0-10 scale) with color coding.
 *
 * Props:
 *  value: number (0-10)
 *  width: number (px, default 90)
 *  height: number (px, default 14)
 *  showValue: boolean (default true)
 */
export default function ScoreBar({ value, width = 90, height = 14, showValue = true }) {
  const v = value == null ? 0 : Math.max(0, Math.min(10, value));
  const pct = (v / 10) * 100;

  let color;
  if (v >= 7) color = "#ef4444";
  else if (v >= 5) color = "#f59e0b";
  else if (v >= 3) color = "#3b82f6";
  else color = "#475569";

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width,
          height,
          borderRadius: 3,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
          position: "relative",
        }}
        title={value != null ? `${value.toFixed(1)} / 10` : "N/A"}
      >
        {value != null && (
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: color,
              borderRadius: 3,
              transition: "width 0.3s ease",
            }}
          />
        )}
      </div>
      {showValue && (
        <span style={{ fontSize: 11, fontWeight: 600, color, minWidth: 24, fontVariantNumeric: "tabular-nums" }}>
          {value != null ? value.toFixed(1) : "—"}
        </span>
      )}
    </div>
  );
}
