import React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import theme from "../../styles/theme";

const overlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(0, 0, 0, 0.7)",
  zIndex: 1000,
};

function Content({ children, width = 560, style, ...props }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay style={overlayStyle} />
      <DialogPrimitive.Content
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: theme.bg.card,
          borderRadius: 12,
          padding: 24,
          width,
          maxWidth: "90vw",
          maxHeight: "85vh",
          overflowY: "auto",
          zIndex: 1001,
          border: `1px solid ${theme.border.default}`,
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          ...style,
        }}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const Dialog = {
  Root: DialogPrimitive.Root,
  Trigger: DialogPrimitive.Trigger,
  Content,
  Title: DialogPrimitive.Title,
  Description: DialogPrimitive.Description,
  Close: DialogPrimitive.Close,
};
