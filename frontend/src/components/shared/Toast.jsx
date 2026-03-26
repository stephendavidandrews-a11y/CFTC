import React from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import theme from "../../styles/theme";

const TOAST_STYLES = {
  success: { background: "#14532d", borderColor: "#22c55e", iconColor: "#4ade80" },
  error:   { background: "#450a0a", borderColor: "#ef4444", iconColor: "#f87171" },
  warning: { background: "#422006", borderColor: "#f59e0b", iconColor: "#fbbf24" },
  info:    { background: "#172554", borderColor: "#3b82f6", iconColor: "#60a5fa" },
};

const ICONS    = { success: "\u2713", error: "\u2717", warning: "\u26a0", info: "\u2139" };
const DURATIONS = { success: 4000, error: 6000, warning: 5000, info: 4000 };

function ToastItem({ toast, onRemove }) {
  const colors = TOAST_STYLES[toast.type] || TOAST_STYLES.info;
  const icon   = ICONS[toast.type]    || ICONS.info;

  return (
    <ToastPrimitive.Root
      duration={DURATIONS[toast.type] || 4000}
      onOpenChange={(open) => { if (!open) onRemove(toast.id); }}
      style={{
        background: colors.background,
        border: `1px solid ${colors.borderColor}40`,
        borderRadius: 8,
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        minWidth: 280,
        maxWidth: 420,
      }}
    >
      <span style={{ fontSize: 16, color: colors.iconColor, flexShrink: 0 }}>{icon}</span>
      <ToastPrimitive.Title
        style={{
          flex: 1,
          fontSize: 13,
          fontWeight: 500,
          color: theme.text.primary,
          lineHeight: 1.4,
        }}
      >
        {toast.message}
      </ToastPrimitive.Title>
      <ToastPrimitive.Close
        style={{
          background: "none",
          border: "none",
          color: theme.text.faint,
          cursor: "pointer",
          fontSize: 14,
          padding: 2,
          flexShrink: 0,
        }}
      >
        x
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}

// Viewport exported so ToastContext can render it inside the provider
export function ToastViewport() {
  return (
    <ToastPrimitive.Viewport
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        width: 340,
        maxWidth: "90vw",
        listStyle: "none",
        margin: 0,
        padding: 0,
        outline: "none",
      }}
    />
  );
}

// ToastContainer renders the individual toasts; must be inside ToastProvider
export default function ToastContainer({ toasts, onRemove }) {
  return (
    <>
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={onRemove} />
      ))}
    </>
  );
}
