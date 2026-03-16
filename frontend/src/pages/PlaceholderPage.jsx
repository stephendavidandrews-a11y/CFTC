import React from "react";
import theme from "../styles/theme";

export default function PlaceholderPage({ title, description, icon }) {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 8, letterSpacing: "-0.02em" }}>
        {title}
      </h2>
      <p style={{ fontSize: 13, color: theme.text.dim, marginBottom: 24 }}>{description}</p>
      <div style={{
        background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`,
        padding: 60, textAlign: "center",
      }}>
        <div style={{ fontSize: 36, marginBottom: 16, opacity: 0.2 }}>{icon}</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: theme.text.faint }}>Coming Soon</div>
        <div style={{ fontSize: 12, color: theme.text.ghost, marginTop: 8 }}>
          This module will connect to your data pipeline
        </div>
      </div>
    </div>
  );
}
