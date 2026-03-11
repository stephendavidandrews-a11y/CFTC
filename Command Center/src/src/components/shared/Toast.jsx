import React from "react";
import theme from "../../styles/theme";

const TOAST_STYLES = {
  success: { bg: "#14532d", border: "#22c55e", icon: "\u2713", color: "#4ade80" },
  error:   { bg: "#450a0a", border: "#ef4444", icon: "\u2717", color: "#f87171" },
  warning: { bg: "#422006", border: "#f59e0b", icon: "\u26a0", color: "#fbbf24" },
  info:    { bg: "#172554", border: "#3b82f6", icon: "\u2139", color: "#60a5fa" },
};

function ToastItem({ toast, onRemove }) {
  const s = TOAST_STYLES[toast.type] || TOAST_STYLES.info;

  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 16px", borderRadius: 8,
        background: s.bg, border: `1px solid ${s.border}40`,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        minWidth: 280, maxWidth: 420,
        opacity: toast.entering || toast.leaving ? 0 : 1,
        transform: toast.entering || toast.leaving ? "translateX(40px)" : "translateX(0)",
        transition: "all 0.3s ease",
        cursor: "pointer",
      }}
      onClick={() => onRemove(toast.id)}
    >
      <span style={{ fontSize: 16, color: s.color, flexShrink: 0 }}>{s.icon}</span>
      <span style={{
        fontSize: 13, color: theme.text.primary, fontWeight: 500, flex: 1, lineHeight: 1.4,
      }}>
        {toast.message}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(toast.id); }}
        style={{
          background: "transparent", border: "none", color: theme.text.faint,
          fontSize: 14, cursor: "pointer", padding: 2, flexShrink: 0,
        }}
      >x</button>
    </div>
  );
}

export default function ToastContainer({ toasts, onRemove }) {
  if (!toasts.length) return null;

  return (
    <div style={{
      position: "fixed", top: 20, right: 20, zIndex: 9999,
      display: "flex", flexDirection: "column", gap: 8,
    }}>
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={onRemove} />
      ))}
    </div>
  );
}
