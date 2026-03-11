import React, { useState } from "react";
import theme from "../../styles/theme";
import ScoreBar from "./ScoreBar";

/**
 * Expandable sub-score breakdown table.
 *
 * Props:
 *  sections: [{ label, composite, subsections: [{ label, key, value }] }]
 */
export default function SubScoreTable({ sections = [] }) {
  const [expanded, setExpanded] = useState({});

  const toggle = (label) => {
    setExpanded((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <div style={{ borderRadius: 8, overflow: "hidden", border: `1px solid ${theme.border.subtle}` }}>
      {sections.map((sec) => (
        <div key={sec.label}>
          {/* Dimension header */}
          <div
            onClick={() => toggle(sec.label)}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 14px", cursor: "pointer",
              background: expanded[sec.label] ? "rgba(59,130,246,0.06)" : "rgba(255,255,255,0.02)",
              borderBottom: `1px solid ${theme.border.subtle}`,
            }}
          >
            <span style={{ fontSize: 12, color: theme.text.faint, width: 14 }}>
              {expanded[sec.label] ? "▾" : "▸"}
            </span>
            <span style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, flex: 1 }}>
              {sec.label}
            </span>
            <ScoreBar value={sec.composite} width={100} height={12} />
          </div>

          {/* Sub-components */}
          {expanded[sec.label] && sec.subsections && sec.subsections.map((sub) => (
            <div
              key={sub.key}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 14px 8px 40px",
                borderBottom: `1px solid ${theme.border.subtle}`,
                background: "rgba(255,255,255,0.01)",
              }}
            >
              <span style={{ fontSize: 12, color: theme.text.muted, flex: 1 }}>
                {sub.label}
              </span>
              <ScoreBar value={sub.value} width={80} height={10} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
