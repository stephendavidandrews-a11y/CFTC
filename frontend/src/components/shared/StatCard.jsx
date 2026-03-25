import React from "react";
import Pulse from "./Pulse";
import theme from "../../styles/theme";

export default function StatCard({ value, label, accent, pulse }) {
  return (
    <div style={{
      background: theme.bg.card,
      borderRadius: 10, padding: "20px 24px",
      border: `1px solid ${theme.border.default}`,
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: accent || theme.accent.blue }} />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: theme.text.primary, letterSpacing: "-0.03em" }}>{value}</div>
        {pulse && <Pulse color={accent || theme.accent.blue} />}
      </div>
      <div style={{ fontSize: 12, color: theme.text.dim, marginTop: 4, fontWeight: 500 }}>{label}</div>
    </div>
  );
}
