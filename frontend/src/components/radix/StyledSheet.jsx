import React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import theme from "../../styles/theme";

const overlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(0, 0, 0, 0.45)",
  zIndex: 500,
};

function Content({ children, width = 520, style, ...props }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay style={overlayStyle} />
      <DialogPrimitive.Content
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width,
          maxWidth: "100vw",
          background: theme.bg.card,
          borderLeft: `1px solid ${theme.border.default}`,
          zIndex: 501,
          display: "flex",
          flexDirection: "column",
          outline: "none",
          animation: "var(--sheet-animation, sheet-slide-in 0.28s cubic-bezier(.4,0,.2,1) forwards)",
          ...style,
        }}
        onCloseAutoFocus={(e) => e.preventDefault()}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const Sheet = {
  Root: DialogPrimitive.Root,
  Trigger: DialogPrimitive.Trigger,
  Content,
  Title: DialogPrimitive.Title,
  Description: DialogPrimitive.Description,
  Close: DialogPrimitive.Close,
};
