import React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import theme from "../../styles/theme";

// CSS-in-JS style tag for data-state="active" since inline styles cannot target data attributes
const tabActiveCSS = `
  [data-radix-tabs-trigger][data-state="active"] {
    color: ${theme.accent.blue} !important;
    border-bottom-color: ${theme.accent.blue} !important;
  }
  [data-radix-tabs-trigger]:hover {
    color: ${theme.text.muted} !important;
  }
`;

function List({ children, style, ...props }) {
  return (
    <TabsPrimitive.List
      style={{
        display: "flex",
        gap: 0,
        borderBottom: `1px solid ${theme.border.default}`,
        marginBottom: 20,
        ...style,
      }}
      {...props}
    >
      <style>{tabActiveCSS}</style>
      {children}
    </TabsPrimitive.List>
  );
}

function Trigger({ children, style, ...props }) {
  return (
    <TabsPrimitive.Trigger
      style={{
        padding: "10px 18px",
        fontSize: 13,
        fontWeight: 600,
        color: theme.text.faint,
        background: "none",
        border: "none",
        borderBottom: "2px solid transparent",
        cursor: "pointer",
        transition: "color 0.15s, border-color 0.15s",
        ...style,
      }}
      {...props}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

export const Tabs = {
  Root: TabsPrimitive.Root,
  List,
  Trigger,
  Content: TabsPrimitive.Content,
};
