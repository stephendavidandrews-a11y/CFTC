import React from "react";
import { Dialog } from "../radix/StyledDialog";
import theme from "../../styles/theme";

export default function Modal({ isOpen, onClose, title, children, width = 560 }) {
  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Content width={width}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <Dialog.Title style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
            {title}
          </Dialog.Title>
          <Dialog.Close style={{ background: "none", border: "none", color: theme.text.faint, cursor: "pointer", fontSize: 20 }}>
            ×
          </Dialog.Close>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Root>
  );
}
