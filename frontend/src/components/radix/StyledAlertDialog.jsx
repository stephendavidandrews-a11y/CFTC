import React from "react";
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import theme from "../../styles/theme";

const overlayStyle = {
  position: "fixed",
  inset: 0,
  background: "rgba(0, 0, 0, 0.7)",
  zIndex: 1000,
};

function Content({ children, width = 440, style, ...props }) {
  return (
    <AlertDialogPrimitive.Portal>
      <AlertDialogPrimitive.Overlay style={overlayStyle} />
      <AlertDialogPrimitive.Content
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
          zIndex: 1001,
          border: `1px solid ${theme.border.default}`,
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          ...style,
        }}
        {...props}
      >
        {children}
      </AlertDialogPrimitive.Content>
    </AlertDialogPrimitive.Portal>
  );
}

export const AlertDialog = {
  Root: AlertDialogPrimitive.Root,
  Content,
  Title: AlertDialogPrimitive.Title,
  Description: AlertDialogPrimitive.Description,
  Cancel: AlertDialogPrimitive.Cancel,
  Action: AlertDialogPrimitive.Action,
};
