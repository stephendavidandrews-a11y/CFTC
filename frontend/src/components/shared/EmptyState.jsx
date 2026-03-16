import React from "react";
import theme from "../../styles/theme";

export default function EmptyState({ icon = "∅", title, message, actionLabel, onAction }) {
  return (
    <div style={{
      textAlign: "center", padding: "60px 20px",
      display: "flex", flexDirection: "column", alignItems: "center", gap: 12,
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 14,
        background: theme.bg.card, border: `1px solid ${theme.border.subtle}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 24, color: theme.text.ghost,
      }}>
        {icon}
      </div>
      {title && (
        <div style={{ fontSize: 15, fontWeight: 600, color: theme.text.muted }}>{title}</div>
      )}
      {message && (
        <div style={{ fontSize: 13, color: theme.text.faint, maxWidth: 320, lineHeight: 1.5 }}>
          {message}
        </div>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: 8, padding: "8px 20px", borderRadius: 8,
            fontSize: 13, fontWeight: 600,
            background: "#1e40af", color: "#fff",
            border: "none", cursor: "pointer",
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
