import React from "react";
import { AlertDialog } from "../radix/StyledAlertDialog";
import theme from "../../styles/theme";

export default function ConfirmDialog({
  isOpen, onClose, onConfirm,
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  confirmLabel = "Confirm", cancelLabel = "Cancel",
  danger = false,
}) {
  return (
    <AlertDialog.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <AlertDialog.Content width={440}>
        <AlertDialog.Title style={{ fontSize: 16, fontWeight: 700, color: theme.text.primary, marginBottom: 8 }}>
          {title}
        </AlertDialog.Title>
        <AlertDialog.Description style={{ fontSize: 14, color: theme.text.secondary, lineHeight: 1.5, marginBottom: 20 }}>
          {message}
        </AlertDialog.Description>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <AlertDialog.Cancel asChild>
            <button style={{
              padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: theme.bg.input, color: theme.text.secondary,
              border: `1px solid ${theme.border.default}`, cursor: "pointer",
            }}>
              {cancelLabel}
            </button>
          </AlertDialog.Cancel>
          <AlertDialog.Action asChild>
            <button
              onClick={async () => { if (onConfirm) await onConfirm(); }}
              style={{
                padding: "8px 18px", borderRadius: 6, fontSize: 13, fontWeight: 600,
                background: danger ? theme.accent.red : theme.accent.blue,
                color: "#fff", border: "none", cursor: "pointer",
              }}
            >
              {confirmLabel}
            </button>
          </AlertDialog.Action>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
