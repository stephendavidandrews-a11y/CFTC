import React, { useState } from "react";
import theme from "../../styles/theme";
import Badge from "../shared/Badge";

const MODULE_NAMES = {
  "2-1": "Loper Bright Deep Analysis",
  "2-2": "Major Questions Deep Analysis",
  "2-3": "EO / Policy Priority",
  "2-4A": "Comment Response Adequacy",
  "2-4B": "Cost-Benefit Analysis Quality",
  "2-4C": "Notice-and-Comment Compliance",
  "2-4D": "Alternatives Analysis",
  "2-5": "Nondelegation Deep Analysis",
  "2-V": "Vagueness Analysis",
  "2-FA": "First Amendment Analysis",
};

const VALIDATION_COLORS = {
  confirmed: { bg: "#14532d", text: "#4ade80" },
  upgraded: { bg: "#052e16", text: "#22c55e" },
  downgraded: { bg: "#422006", text: "#fbbf24" },
  false_positive: { bg: "#1f2937", text: "#6b7280" },
};

/**
 * Card showing a single Stage 2 module assessment.
 *
 * Props:
 *  assessment: dict from stage2_assessments
 */
export default function ModuleAnalysisCard({ assessment }) {
  const [expanded, setExpanded] = useState(false);
  const a = assessment;
  const vc = VALIDATION_COLORS[a.sonnet_validation_result] || VALIDATION_COLORS.false_positive;

  return (
    <div style={{
      background: theme.bg.card,
      borderRadius: 10,
      border: `1px solid ${theme.border.default}`,
      marginBottom: 10,
      overflow: "hidden",
    }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 16px", cursor: "pointer",
          borderBottom: expanded ? `1px solid ${theme.border.subtle}` : "none",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, flex: 1 }}>
          {MODULE_NAMES[a.module] || a.module}
        </span>
        <Badge bg={vc.bg} text={vc.text} label={a.sonnet_validation_result || "—"} />
        {a.sonnet_revised_score != null && (
          <span style={{ fontSize: 12, color: theme.text.dim, fontFamily: theme.font.mono }}>
            {a.sonnet_revised_score.toFixed(1)}
          </span>
        )}
        {a.stage1_score_triggering != null && (
          <span style={{ fontSize: 11, color: theme.text.ghost }}>
            (S1: {a.stage1_score_triggering.toFixed(1)})
          </span>
        )}
        <span style={{ fontSize: 12, color: theme.text.faint }}>
          {expanded ? "▾" : "▸"}
        </span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: "12px 16px" }}>
          {/* Sonnet analysis */}
          {a.sonnet_validation_notes && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 6 }}>
                Sonnet Analysis
              </div>
              <div style={{
                fontSize: 12, color: theme.text.muted, lineHeight: 1.6,
                whiteSpace: "pre-wrap", maxHeight: 300, overflowY: "auto",
                padding: 12, borderRadius: 6,
                background: "rgba(255,255,255,0.02)",
                border: `1px solid ${theme.border.subtle}`,
              }}>
                {a.sonnet_validation_notes}
              </div>
            </div>
          )}

          {/* Opus analysis (if available) */}
          {a.opus_analysis_run === 1 && (
            <>
              {a.vulnerability_rating && (
                <div style={{ display: "flex", gap: 16, marginBottom: 10 }}>
                  <div>
                    <span style={{ fontSize: 11, color: theme.text.faint }}>Vulnerability: </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
                      {a.vulnerability_rating}
                    </span>
                  </div>
                  {a.confidence_level && (
                    <div>
                      <span style={{ fontSize: 11, color: theme.text.faint }}>Confidence: </span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
                        {a.confidence_level}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {a.strongest_challenge_argument && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: theme.accent.red, marginBottom: 4 }}>
                    Strongest Challenge
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>
                    {a.strongest_challenge_argument}
                  </div>
                </div>
              )}

              {a.strongest_defense_argument && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: theme.accent.green, marginBottom: 4 }}>
                    Strongest Defense
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>
                    {a.strongest_defense_argument}
                  </div>
                </div>
              )}

              {a.recommended_action && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: theme.accent.blueLight, marginBottom: 4 }}>
                    Recommended Action
                  </div>
                  <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5 }}>
                    {a.recommended_action}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Metadata */}
          <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${theme.border.subtle}`, fontSize: 11, color: theme.text.ghost }}>
            Module: {a.module} | Analyzed: {a.analyzed_at ? a.analyzed_at.substring(0, 10) : "—"}
            {a.opus_analysis_run === 1 ? " | Opus: Complete" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
