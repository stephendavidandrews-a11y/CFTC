import React from "react";
import theme from "../../styles/theme";

/**
 * Renders a source excerpt with provenance metadata.
 *
 * Props:
 *  excerpt: string — the quoted text
 *  locator: { type, segments, ... } — source locator metadata
 *  startTime: number|null — start time in seconds
 *  endTime: number|null — end time in seconds
 */
export default function SourceExcerptViewer({ excerpt, locator, startTime, endTime }) {
  if (!excerpt) return null;

  const formatTime = (seconds) => {
    if (seconds == null) return null;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  const startStr = formatTime(startTime);
  const endStr = formatTime(endTime);
  const timeRange = startStr && endStr ? `${startStr} \u2013 ${endStr}` : startStr || endStr || null;

  return (
    <div style={{
      borderLeft: `3px solid ${theme.accent.blue}`,
      paddingLeft: 12,
      margin: "8px 0",
    }}>
      <div style={{
        fontSize: 10,
        fontWeight: 600,
        color: theme.text.faint,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        marginBottom: 4,
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}>
        <span>Source</span>
        {locator?.type && (
          <span style={{ textTransform: "none", fontWeight: 400 }}>
            ({locator.type})
          </span>
        )}
        {timeRange && (
          <span style={{
            fontFamily: theme.font.mono,
            fontSize: 10,
            color: theme.text.dim,
            fontWeight: 400,
          }}>
            {timeRange}
          </span>
        )}
      </div>
      <div style={{
        fontFamily: theme.font.mono,
        fontSize: 12,
        lineHeight: 1.6,
        color: theme.text.muted,
        fontStyle: "italic",
      }}>
        &ldquo;{excerpt}&rdquo;
      </div>
    </div>
  );
}
