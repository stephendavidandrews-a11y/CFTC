import React from "react";
import { Sheet } from "../radix/StyledSheet";
import theme from "../../styles/theme";

export default function DrawerShell({ isOpen, onClose, title, width = 520, children }) {
  return (
    <Sheet.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Sheet.Content width={width}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: `1px solid ${theme.border.default}`,
            flexShrink: 0,
          }}
        >
          <Sheet.Title
            style={{ fontSize: 16, fontWeight: 700, color: theme.text.primary, margin: 0 }}
          >
            {title}
          </Sheet.Title>
          <Sheet.Close
            style={{
              background: "none",
              border: "none",
              color: theme.text.dim,
              fontSize: 20,
              cursor: "pointer",
              padding: "2px 6px",
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            &#x2715;
          </Sheet.Close>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {children}
        </div>
      </Sheet.Content>
    </Sheet.Root>
  );
}
