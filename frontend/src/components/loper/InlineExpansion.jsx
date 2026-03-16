import React from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import Badge from "../shared/Badge";
import ScoreBar from "./ScoreBar";

const MODULE_NAMES = {
  "2-1": "Loper Bright",
  "2-2": "Major Questions",
  "2-3": "Policy Priority",
  "2-4A": "Comment Response",
  "2-4B": "Cost-Benefit Analysis",
  "2-4C": "Notice & Comment",
  "2-4D": "Alternatives Analysis",
  "2-5": "Nondelegation",
  "2-V": "Vagueness",
  "2-FA": "First Amendment",
};

const VALIDATION_COLORS = {
  confirmed: { bg: "#14532d", text: "#4ade80" },
  upgraded: { bg: "#052e16", text: "#22c55e" },
  downgraded: { bg: "#422006", text: "#fbbf24" },
  false_positive: { bg: "#1f2937", text: "#6b7280" },
};

const ACTION_COLORS = {
  Rescind: { bg: "#450a0a", text: "#f87171" },
  Amend: { bg: "#422006", text: "#fbbf24" },
  Reinterpret: { bg: "#2e1065", text: "#a78bfa" },
  Defend: { bg: "#172554", text: "#60a5fa" },
  "Manual review": { bg: "#1f2937", text: "#9ca3af" },
  Deprioritize: { bg: "#1f2937", text: "#6b7280" },
  Withdraw: { bg: "#450a0a", text: "#f87171" },
  Codify: { bg: "#14532d", text: "#4ade80" },
  Narrow: { bg: "#422006", text: "#fbbf24" },
  Maintain: { bg: "#172554", text: "#60a5fa" },
};

const cardStyle = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: 8,
  border: `1px solid ${theme.border.subtle}`,
  padding: 14,
  marginBottom: 8,
};

/**
 * Inline expansion panel shown below a clicked row in the Explorer table.
 *
 * Props:
 *  rule: row data object from the rules list
 *  mode: "rules" | "guidance"
 *  colSpan: number of table columns to span
 */
export default function InlineExpansion({ rule, mode = "rules", colSpan = 12 }) {
  const navigate = useNavigate();
  const isRule = mode === "rules";

  const assessments = rule.s2_assessments || [];
  const confirmed = assessments.filter(
    (a) => a.sonnet_validation_result === "confirmed" || a.sonnet_validation_result === "upgraded"
  );

  const detailPath = isRule
    ? `/loper/rules/${encodeURIComponent(rule.fr_citation)}`
    : `/loper/guidance/${encodeURIComponent(rule.doc_id)}`;

  const ac = ACTION_COLORS[rule.action_category] || ACTION_COLORS["Manual review"];

  // Dimension data for mini chart
  const dimensions = isRule
    ? [
        { label: "Loper Bright", value: rule.dim1_composite },
        { label: "Major Questions", value: rule.dim2_composite },
        { label: "Policy Priority", value: rule.dim3_composite },
        { label: "Procedural", value: rule.dim4_composite },
        { label: "Nondelegation", value: rule.dim5_composite },
      ]
    : [
        { label: "Interpretive", value: rule.g1_composite },
        { label: "Scope", value: rule.g2_composite },
        { label: "Policy Priority", value: rule.g3_composite },
        { label: "Force of Law", value: rule.g4_composite },
        { label: "Delegation", value: rule.g5_composite },
      ];

  return (
    <tr>
      <td
        colSpan={colSpan}
        style={{
          padding: 0,
          borderBottom: `1px solid ${theme.border.default}`,
          background: "rgba(17,24,39,0.7)",
        }}
      >
        <div style={{ padding: "16px 20px" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <Badge bg={ac.bg} text={ac.text} label={rule.action_category || "—"} />
            <span style={{ fontSize: 14, fontWeight: 700, color: theme.text.primary, flex: 1 }}>
              {rule.title}
            </span>
            <span style={{ fontSize: 12, color: theme.text.dim, fontFamily: theme.font.mono }}>
              {isRule ? rule.fr_citation : rule.letter_number || rule.doc_id}
            </span>
            <span style={{
              fontSize: 18, fontWeight: 700,
              color: (rule.composite_score || 0) >= 7 ? "#ef4444"
                : (rule.composite_score || 0) >= 5 ? "#f59e0b"
                : (rule.composite_score || 0) >= 3 ? "#3b82f6" : "#475569",
            }}>
              {rule.composite_score != null ? rule.composite_score.toFixed(2) : "—"}
            </span>
          </div>

          <div style={{ display: "flex", gap: 16 }}>
            {/* Left: Dimension breakdown */}
            <div style={{ flex: 1, ...cardStyle }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 10 }}>
                Dimension Breakdown
              </div>
              {dimensions.map((d) => (
                <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: theme.text.muted, width: 110 }}>{d.label}</span>
                  <ScoreBar value={d.value} width={120} height={12} />
                </div>
              ))}
              {isRule && rule.comment_multiplier != null && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, paddingTop: 6, borderTop: `1px solid ${theme.border.subtle}` }}>
                  <span style={{ fontSize: 11, color: theme.text.muted, width: 110 }}>Comment Mult.</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
                    {rule.comment_multiplier.toFixed(2)}x
                  </span>
                </div>
              )}
            </div>

            {/* Right: S2 Analysis */}
            <div style={{ flex: 1.5 }}>
              {assessments.length === 0 ? (
                <div style={{ ...cardStyle, textAlign: "center", color: theme.text.faint, fontSize: 12, padding: 24 }}>
                  No Stage 2 AI validation data available for this {isRule ? "rule" : "document"}.
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", marginBottom: 8 }}>
                    AI Validation ({confirmed.length}/{assessments.length} confirmed)
                  </div>
                  <div style={{ maxHeight: 250, overflowY: "auto" }}>
                    {assessments.map((a) => {
                      const vc = VALIDATION_COLORS[a.sonnet_validation_result] || VALIDATION_COLORS.false_positive;
                      return (
                        <div key={a.module} style={{ ...cardStyle, padding: 10 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
                              {MODULE_NAMES[a.module] || a.module}
                            </span>
                            <Badge bg={vc.bg} text={vc.text} label={a.sonnet_validation_result || "—"} />
                            {a.sonnet_revised_score != null && (
                              <span style={{ fontSize: 11, color: theme.text.dim, marginLeft: "auto" }}>
                                Score: {a.sonnet_revised_score.toFixed(1)}
                              </span>
                            )}
                          </div>
                          {a.sonnet_validation_notes && (
                            <div style={{ fontSize: 11, color: theme.text.muted, lineHeight: 1.5, maxHeight: 60, overflow: "hidden" }}>
                              {a.sonnet_validation_notes.substring(0, 300)}
                              {a.sonnet_validation_notes.length > 300 && "..."}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Legal theory tags */}
          {rule.legal_theory_tags && rule.legal_theory_tags.length > 0 && (
            <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 10, color: theme.text.faint, fontWeight: 700, textTransform: "uppercase", alignSelf: "center" }}>
                Theories:
              </span>
              {rule.legal_theory_tags.map((t) => (
                <Badge key={t} bg="#172554" text={theme.accent.blueLight} label={t} />
              ))}
            </div>
          )}

          {/* Footer: Full Analysis link */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <button
              onClick={(e) => { e.stopPropagation(); navigate(detailPath); }}
              style={{
                padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: "rgba(59,130,246,0.12)", color: theme.accent.blueLight,
                border: `1px solid rgba(59,130,246,0.25)`, cursor: "pointer",
              }}
            >
              Full Analysis →
            </button>
          </div>
        </div>
      </td>
    </tr>
  );
}
