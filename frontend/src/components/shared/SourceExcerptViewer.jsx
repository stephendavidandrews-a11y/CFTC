import React, { useState } from "react";
import theme from "../../styles/theme";

/**
 * Renders evidence for a bundle item with a collapsible "See evidence" toggle.
 *
 * Supports both:
 *  - New multi-evidence format: locator.evidence[] array
 *  - Legacy single-evidence format: single excerpt + time range
 *
 * Props:
 *  excerpt: string — primary excerpt text (legacy compat)
 *  locator: { type, evidence[], segments, ... } — source locator metadata
 *  startTime: number|null — start time in seconds (legacy)
 *  endTime: number|null — end time in seconds (legacy)
 *  audioRef: React ref to audio element (optional, for play buttons)
 */
export default function SourceExcerptViewer({ excerpt, locator, startTime, endTime, audioRef }) {
  const [expanded, setExpanded] = useState(false);

  // Parse locator if it's a JSON string
  let parsedLocator = locator;
  if (typeof locator === "string") {
    try { parsedLocator = JSON.parse(locator); } catch { parsedLocator = null; }
  }

  // Build evidence list from new format or fall back to legacy
  const evidenceList = buildEvidenceList(excerpt, parsedLocator, startTime, endTime);

  if (!evidenceList.length) return null;

  const count = evidenceList.length;

  return (
    <div style={{ margin: "8px 0" }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: "4px 0",
          display: "flex",
          alignItems: "center",
          gap: 6,
          color: theme.accent.blue,
          fontSize: 12,
          fontFamily: theme.font.family,
          fontWeight: 500,
        }}
      >
        <span style={{
          display: "inline-block",
          transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform 0.15s ease",
          fontSize: 10,
        }}>
          &#9654;
        </span>
        {expanded ? "Hide evidence" : `See evidence (${count})`}
      </button>

      {expanded && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 8 }}>
          {evidenceList.map((ev, idx) => (
            <EvidenceItem
              key={idx}
              evidence={ev}
              index={idx}
              total={count}
              locatorType={parsedLocator?.type}
              audioRef={audioRef}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function EvidenceItem({ evidence, index, total, locatorType, audioRef }) {
  const { excerpt, timeRange, speaker } = evidence;

  const formatTime = (seconds) => {
    if (seconds == null) return null;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  const startStr = formatTime(timeRange?.start);
  const endStr = formatTime(timeRange?.end);
  const timeStr = startStr && endStr ? `${startStr} \u2013 ${endStr}` : startStr || endStr || null;

  const handlePlay = () => {
    if (audioRef?.current && timeRange?.start != null) {
      audioRef.current.currentTime = timeRange.start;
      audioRef.current.play();
    }
  };

  return (
    <div style={{
      borderLeft: `3px solid ${theme.accent.blue}`,
      paddingLeft: 12,
    }}>
      <div style={{
        fontSize: 10,
        fontWeight: 600,
        color: theme.text.faint,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        marginBottom: 3,
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}>
        {total > 1 && (
          <span style={{ color: theme.text.dim, fontWeight: 400 }}>
            {index + 1}/{total}
          </span>
        )}
        {speaker && (
          <span style={{
            textTransform: "none",
            fontWeight: 500,
            color: theme.text.muted,
          }}>
            {speaker}
          </span>
        )}
        {!speaker && locatorType && (
          <span style={{ textTransform: "none", fontWeight: 400 }}>
            ({locatorType})
          </span>
        )}
        {timeStr && (
          <span style={{
            fontFamily: theme.font.mono,
            fontSize: 10,
            color: theme.text.dim,
            fontWeight: 400,
          }}>
            {timeStr}
          </span>
        )}
        {audioRef && timeRange?.start != null && (
          <button
            onClick={handlePlay}
            title="Play from this point"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: theme.accent.blue,
              fontSize: 11,
              padding: "0 2px",
              lineHeight: 1,
            }}
          >
            &#9654;
          </button>
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


/**
 * Build a normalized evidence list from either the new or legacy format.
 */
function buildEvidenceList(excerpt, locator, startTime, endTime) {
  // New format: locator has evidence[] array
  if (locator?.evidence && Array.isArray(locator.evidence) && locator.evidence.length > 0) {
    return locator.evidence.map((ev) => ({
      excerpt: ev.excerpt || "",
      timeRange: ev.time_range || null,
      speaker: ev.speaker || null,
      segments: ev.segments || [],
    }));
  }

  // Legacy format: single excerpt
  if (excerpt) {
    return [{
      excerpt,
      timeRange: (startTime != null && endTime != null)
        ? { start: startTime, end: endTime }
        : null,
      speaker: locator?.speaker_name || null,
      segments: locator?.segments || [],
    }];
  }

  return [];
}
