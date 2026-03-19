import React from "react";
import theme from "../../styles/theme";

/**
 * Thin banner showing SSE event stream connection state.
 * - Connected: hidden (no visual noise when healthy)
 * - Disconnected: amber bar with pulsing dot and "Reconnecting..." message
 *
 * Usage: <SSEBanner connected={connected} />
 */
export default function SSEBanner({ connected }) {
  if (connected) return null;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "6px 16px",
      background: "rgba(245,158,11,0.1)",
      borderRadius: 8,
      border: "1px solid rgba(245,158,11,0.25)",
      marginBottom: 16,
      fontSize: 12,
      color: theme.accent.yellowLight,
    }}>
      <span style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: theme.accent.yellow,
        animation: "sse-pulse 1.5s ease-in-out infinite",
        flexShrink: 0,
      }} />
      <span>Real-time updates disconnected &mdash; reconnecting...</span>
      <style>{`
        @keyframes sse-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
