import React from "react";
import Modal from "./Modal";
import theme from "../../styles/theme";

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
}) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} width={420}>
      <p style={{ color: theme.text.muted, fontSize: 14, lineHeight: 1.6, margin: "0 0 24px" }}>
        {message}
      </p>
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <button
          onClick={onClose}
          style={{
            padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: theme.bg.input, color: theme.text.muted,
            border: `1px solid ${theme.border.default}`, cursor: "pointer",
          }}
        >
          {cancelLabel}
        </button>
        <button
          onClick={() => { onConfirm(); onClose(); }}
          style={{
            padding: "9px 18px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: danger ? theme.accent.red : theme.accent.blue,
            color: "#fff", border: "none", cursor: "pointer",
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
