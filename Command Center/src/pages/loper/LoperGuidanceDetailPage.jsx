import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import Badge from "../../components/shared/Badge";
import ScoreBar from "../../components/loper/ScoreBar";
import SpiderChart from "../../components/loper/SpiderChart";
import SubScoreTable from "../../components/loper/SubScoreTable";
import { getGuidance } from "../../api/loper";
import useApi from "../../hooks/useApi";
import useMediaQuery from "../../hooks/useMediaQuery";

const ACTION_COLORS = {
  Withdraw: { bg: "#450a0a", text: "#f87171" },
  Codify: { bg: "#14532d", text: "#4ade80" },
  Narrow: { bg: "#422006", text: "#fbbf24" },
  Maintain: { bg: "#172554", text: "#60a5fa" },
  "Manual review": { bg: "#1f2937", text: "#9ca3af" },
  Deprioritize: { bg: "#1f2937", text: "#6b7280" },
};

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 20,
  marginBottom: 16,
};

const sectionTitle = {
  fontSize: 11, fontWeight: 700, color: theme.text.faint,
  textTransform: "uppercase", marginBottom: 10,
};

function scoreColor(v) {
  if (v >= 7) return "#ef4444";
  if (v >= 5) return "#f59e0b";
  if (v >= 3) return "#3b82f6";
  return "#475569";
}

export default function LoperGuidanceDetailPage() {
  const { docId } = useParams();
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { data, loading, error } = useApi(
    () => getGuidance(decodeURIComponent(docId)),
    [docId] // eslint-disable-line
  );

  if (loading) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>
        Loading guidance detail...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{
          padding: "12px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)", color: theme.accent.red, fontSize: 13,
        }}>
          {error || "Guidance document not found."}
        </div>
        <button onClick={() => navigate("/loper/guidance")} style={{ marginTop: 12, background: "none", border: "none", color: theme.accent.blueLight, cursor: "pointer", fontSize: 13 }}>
          &larr; Back to Explorer
        </button>
      </div>
    );
  }

  const g = data.guidance;
  const parentRules = data.parent_rules || [];
  const relatedGuidance = data.related_guidance || [];
  const ac = ACTION_COLORS[g.action_category] || ACTION_COLORS["Manual review"];

  const dimensions = [
    { label: "Interpretive", value: g.g1_composite },
    { label: "Scope", value: g.g2_composite },
    { label: "Policy Priority", value: g.g3_composite },
    { label: "Force of Law", value: g.g4_composite },
    { label: "Delegation", value: g.g5_composite },
  ];

  const subsections = [
    {
      label: "G1 — Interpretive Vulnerability",
      composite: g.g1_composite,
      subsections: [
        { label: "Specificity of statutory text", key: "g1_spec", value: g.g1_specificity_score },
        { label: "Linguistic indicators", key: "g1_ling", value: g.g1_linguistic_score },
        { label: "Base vulnerability", key: "g1_base", value: g.g1_base_vulnerability },
      ],
    },
    {
      label: "G2 — Scope & Significance",
      composite: g.g2_composite,
      subsections: [
        { label: "Economic impact", key: "g2_econ", value: g.g2_economic_impact },
        { label: "Novel jurisdiction", key: "g2_novel", value: g.g2_novel_jurisdiction },
        { label: "Scope breadth", key: "g2_scope", value: g.g2_scope_breadth },
      ],
    },
    {
      label: "G3 — Policy Priority",
      composite: g.g3_composite,
      subsections: [
        { label: "Small entity impact", key: "g3_f1", value: g.g3_flag1_small_entity },
        { label: "Innovation barrier", key: "g3_f2", value: g.g3_flag2_innovation },
        { label: "Duplicative", key: "g3_f3", value: g.g3_flag3_duplicative },
        { label: "Outdated", key: "g3_f4", value: g.g3_flag4_outdated },
        { label: "Excessive burden", key: "g3_f5", value: g.g3_flag5_excessive_burden },
        { label: "Enforcement discretion", key: "g3_f6", value: g.g3_flag6_enforcement },
        { label: "Cross-agency conflict", key: "g3_f7", value: g.g3_flag7_cross_agency },
      ],
    },
    {
      label: "G4 — Force of Law",
      composite: g.g4_composite,
      subsections: [
        { label: "Binding language", key: "g4_bind", value: g.g4_binding_language },
        { label: "Conditional language", key: "g4_cond", value: g.g4_conditional_language },
        { label: "Enforcement language", key: "g4_enf", value: g.g4_enforcement_language },
      ],
    },
    {
      label: "G5 — Delegation Breadth",
      composite: g.g5_composite,
      subsections: [
        { label: "Delegation breadth", key: "g5_deleg", value: g.g5_delegation_breadth },
        { label: "Scope ratio", key: "g5_ratio", value: g.g5_scope_ratio },
      ],
    },
  ];

  const legalTags = g.legal_theory_tags || [];
  const ceaSections = g.mapped_cea_sections || [];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1400 }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => navigate("/loper/guidance")} style={{ background: "none", border: "none", color: theme.accent.blueLight, cursor: "pointer", fontSize: 12, padding: 0 }}>
          &larr; Back to Explorer
        </button>
      </div>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0, lineHeight: 1.3 }}>
              {g.title}
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: theme.accent.purple, fontWeight: 600 }}>
                {g.document_type}
              </span>
              {g.letter_number && (
                <span style={{ fontSize: 13, color: theme.text.dim, fontFamily: theme.font.mono }}>
                  {g.letter_number}
                </span>
              )}
              {g.division && (
                <span style={{ fontSize: 12, color: theme.text.ghost }}>
                  {g.division}
                </span>
              )}
              {g.publication_date && (
                <span style={{ fontSize: 12, color: theme.text.ghost }}>
                  Published: {g.publication_date.substring(0, 10)}
                </span>
              )}
            </div>
          </div>

          <div style={{ textAlign: "center" }}>
            <div style={{
              fontSize: 32, fontWeight: 800,
              color: scoreColor(g.composite_score || 0),
              lineHeight: 1,
            }}>
              {g.composite_score != null ? g.composite_score.toFixed(2) : "—"}
            </div>
            <div style={{ fontSize: 10, color: theme.text.ghost, marginTop: 2 }}>COMPOSITE</div>
          </div>
        </div>

        {/* Tags */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <Badge bg={ac.bg} text={ac.text} label={g.action_category || "—"} />
          {g.flag_vagueness === 1 && <Badge bg="#422006" text="#fbbf24" label="Vagueness" />}
          {g.flag_first_amendment === 1 && <Badge bg="#450a0a" text="#f87171" label="1st Amend." />}
          {g.compound_vulnerability === 1 && <Badge bg="#2e1065" text="#a78bfa" label="Compound" />}
          {g.still_in_effect === 0 && <Badge bg="#1f2937" text="#6b7280" label="No Longer in Effect" />}
          {g.withdrawal_status && <Badge bg="#422006" text="#fbbf24" label={`Withdrawn: ${g.withdrawal_status}`} />}
          {legalTags.map((t) => (
            <Badge key={t} bg="#172554" text={theme.accent.blueLight} label={t} />
          ))}
        </div>
      </div>

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "2fr 1fr", gap: 20, alignItems: "start" }}>
        {/* LEFT COLUMN */}
        <div>
          {/* Spider Chart + Key Scores */}
          <div style={{ ...cardStyle, display: "flex", flexDirection: isMobile ? "column" : "row", gap: 20 }}>
            <div style={{ flex: 1 }}>
              <div style={sectionTitle}>Dimension Profile</div>
              <SpiderChart dimensions={dimensions} size={isMobile ? 220 : 260} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={sectionTitle}>Key Scores</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {dimensions.map((d) => (
                  <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: theme.text.muted, width: 110 }}>{d.label}</span>
                    <ScoreBar value={d.value} width={120} height={14} />
                  </div>
                ))}
                <div style={{ display: "flex", gap: 20, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${theme.border.subtle}` }}>
                  <div>
                    <div style={{ fontSize: 10, color: theme.text.ghost }}>Legal Challenge</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: scoreColor(g.legal_challenge_subcomposite || 0) }}>
                      {g.legal_challenge_subcomposite != null ? g.legal_challenge_subcomposite.toFixed(2) : "—"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: theme.text.ghost }}>Policy Priority</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: scoreColor(g.policy_priority_subcomposite || 0) }}>
                      {g.policy_priority_subcomposite != null ? g.policy_priority_subcomposite.toFixed(2) : "—"}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sub-Score Breakdown */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Sub-Score Breakdown</div>
            <SubScoreTable sections={subsections} />
          </div>

          {/* Force of Law Detail */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Force of Law Analysis</div>
            <div style={{ display: "flex", gap: 20, marginBottom: 12 }}>
              {[
                { label: "Binding Language", value: g.g4_binding_language, color: "#ef4444" },
                { label: "Conditional Language", value: g.g4_conditional_language, color: "#f59e0b" },
                { label: "Enforcement Language", value: g.g4_enforcement_language, color: "#3b82f6" },
              ].map((item) => (
                <div key={item.label} style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: 24, fontWeight: 700,
                    color: (item.value || 0) >= 5 ? item.color : theme.text.dim,
                  }}>
                    {item.value != null ? item.value.toFixed(1) : "—"}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>{item.label}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, padding: 10, borderRadius: 6, background: "rgba(255,255,255,0.02)", border: `1px solid ${theme.border.subtle}` }}>
              {g.g4_composite >= 7
                ? "This guidance document exhibits strong force-of-law characteristics, functioning as de facto rulemaking. Post-Loper Bright, such documents receive zero judicial deference and face heightened vulnerability."
                : g.g4_composite >= 4
                ? "Moderate binding characteristics detected. Some enforcement-like language present but not at the level of de facto rulemaking."
                : "Low binding language. This document operates primarily in an advisory capacity."}
            </div>
          </div>

          {/* Description if available */}
          {g.description && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Description</div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {g.description}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* Status Panel */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Details</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div>
                <div style={{ fontSize: 10, color: theme.text.ghost }}>Document ID</div>
                <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>{g.doc_id}</div>
              </div>
              {g.document_type && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>Type</div>
                  <div style={{ fontSize: 12, color: theme.text.muted }}>{g.document_type}</div>
                </div>
              )}
              {g.division && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>Division</div>
                  <div style={{ fontSize: 12, color: theme.text.muted }}>{g.division}</div>
                </div>
              )}
              {g.cfr_authority && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>CFR Authority</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>{g.cfr_authority}</div>
                </div>
              )}
              {ceaSections.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>Mapped CEA Sections</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>
                    {ceaSections.join(", ")}
                  </div>
                </div>
              )}
              <div style={{ borderTop: `1px solid ${theme.border.subtle}`, paddingTop: 8, marginTop: 4 }}>
                <div style={{ fontSize: 10, color: theme.text.ghost }}>Scoring</div>
                <div style={{ fontSize: 11, color: theme.text.dim }}>
                  Version: {g.scoring_version || "—"} | {g.scored_at ? g.scored_at.substring(0, 10) : "—"}
                </div>
                {g.has_missing_data === 1 && (
                  <div style={{ fontSize: 11, color: theme.accent.yellow, marginTop: 2 }}>
                    Has missing data
                  </div>
                )}
                {g.has_full_text === 0 && (
                  <div style={{ fontSize: 11, color: theme.accent.yellow, marginTop: 2 }}>
                    No full text available
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Parent Rules */}
          {parentRules.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Parent Rules ({parentRules.length})</div>
              {parentRules.map((pr) => {
                const pAc = ACTION_COLORS[pr.action_category] || ACTION_COLORS["Manual review"] || { bg: "#1f2937", text: "#9ca3af" };
                return (
                  <div
                    key={pr.fr_citation}
                    onClick={() => navigate(`/loper/rules/${encodeURIComponent(pr.fr_citation)}`)}
                    style={{
                      padding: 10, borderRadius: 6, marginBottom: 6, cursor: "pointer",
                      background: "rgba(59,130,246,0.06)",
                      border: "1px solid rgba(59,130,246,0.15)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Badge bg={pAc.bg} text={pAc.text} label={pr.action_category || "—"} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: scoreColor(pr.composite_score || 0) }}>
                        {pr.composite_score != null ? pr.composite_score.toFixed(2) : "—"}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: theme.text.muted, marginTop: 4, lineHeight: 1.4 }}>
                      {pr.title ? pr.title.substring(0, 100) : pr.fr_citation}
                      {pr.title && pr.title.length > 100 ? "..." : ""}
                    </div>
                    <div style={{ fontSize: 11, color: theme.text.dim, fontFamily: theme.font.mono, marginTop: 2 }}>
                      {pr.fr_citation}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Related Guidance */}
          {relatedGuidance.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Related Guidance ({relatedGuidance.length})</div>
              {relatedGuidance.slice(0, 8).map((rg) => (
                <div
                  key={rg.doc_id}
                  onClick={() => navigate(`/loper/guidance/${encodeURIComponent(rg.doc_id)}`)}
                  style={{
                    padding: 8, borderRadius: 6, marginBottom: 4, cursor: "pointer",
                    background: "rgba(255,255,255,0.02)",
                    border: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 10, color: theme.text.ghost }}>{rg.document_type}</span>
                    <span style={{ fontSize: 11, color: theme.text.muted, fontFamily: theme.font.mono }}>
                      {rg.composite_score != null ? rg.composite_score.toFixed(2) : "—"}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 2 }}>
                    {rg.title ? rg.title.substring(0, 80) : rg.doc_id}
                    {rg.title && rg.title.length > 80 ? "..." : ""}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Actions */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Quick Actions</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {g.url && (
                <a
                  href={g.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "8px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: "rgba(59,130,246,0.12)", color: theme.accent.blueLight,
                    border: `1px solid rgba(59,130,246,0.25)`, textDecoration: "none",
                    textAlign: "center",
                  }}
                >
                  View Source Document
                </a>
              )}
              <button
                onClick={() => navigate("/loper/guidance")}
                style={{
                  padding: "8px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                  background: "rgba(167,139,250,0.12)", color: theme.accent.purple,
                  border: `1px solid rgba(167,139,250,0.25)`, cursor: "pointer",
                }}
              >
                Back to Explorer
              </button>
            </div>
          </div>

          {/* Notes */}
          {g.notes && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Notes</div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {g.notes}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
