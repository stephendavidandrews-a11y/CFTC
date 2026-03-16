import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import Badge from "../../components/shared/Badge";
import ScoreBar from "../../components/loper/ScoreBar";
import SpiderChart from "../../components/loper/SpiderChart";
import SubScoreTable from "../../components/loper/SubScoreTable";
import ModuleAnalysisCard from "../../components/loper/ModuleAnalysisCard";
import { getRule } from "../../api/loper";
import useApi from "../../hooks/useApi";
import useMediaQuery from "../../hooks/useMediaQuery";

const ACTION_COLORS = {
  Rescind: { bg: "#450a0a", text: "#f87171" },
  Amend: { bg: "#422006", text: "#fbbf24" },
  Reinterpret: { bg: "#2e1065", text: "#a78bfa" },
  Defend: { bg: "#172554", text: "#60a5fa" },
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

export default function LoperRuleDetailPage() {
  const { frCitation } = useParams();
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { data, loading, error } = useApi(
    () => getRule(decodeURIComponent(frCitation)),
    [frCitation] // eslint-disable-line
  );

  if (loading) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>
        Loading rule detail...
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
          {error || "Rule not found."}
        </div>
        <button onClick={() => navigate("/loper/rules")} style={{ marginTop: 12, background: "none", border: "none", color: theme.accent.blueLight, cursor: "pointer", fontSize: 13 }}>
          &larr; Back to Explorer
        </button>
      </div>
    );
  }

  const r = data.rule;
  const assessments = data.s2_assessments || [];
  const challenges = data.challenges || [];
  const ceaProvisions = data.cea_provisions || [];
  const relatedRules = data.related_rules || [];
  const relatedGuidance = data.related_guidance || [];
  const ac = ACTION_COLORS[r.action_category] || ACTION_COLORS["Manual review"];

  // Dimensions for spider chart
  const dimensions = [
    { label: "Loper Bright", value: r.dim1_composite },
    { label: "Major Questions", value: r.dim2_composite },
    { label: "Policy Priority", value: r.dim3_composite },
    { label: "Procedural", value: r.dim4_composite },
    { label: "Nondelegation", value: r.dim5_composite },
  ];

  // Sub-score sections for table
  const subsections = [
    {
      label: "D1 — Loper Bright (Statutory Authority)",
      composite: r.dim1_composite,
      subsections: [
        { label: "Specificity of statutory text", key: "d1_1i", value: r.dim1_1i_score },
        { label: "Expressly delegated gap-filling", key: "d1_1ii", value: r.dim1_1ii_score },
        { label: "Historical deference reliance", key: "d1_1iii", value: r.dim1_1iii_score },
      ],
    },
    {
      label: "D2 — Major Questions Doctrine",
      composite: r.dim2_composite,
      subsections: [
        { label: "Economic significance", key: "d2_2a", value: r.dim2_2a_score },
        { label: "Political significance", key: "d2_2b", value: r.dim2_2b_score },
        { label: "Novel / transformative", key: "d2_2c", value: r.dim2_2c_score },
        { label: "Peripheral statutory provision", key: "d2_2d", value: r.dim2_2d_score },
        { label: "Congressional acquiescence gap", key: "d2_2e", value: r.dim2_2e_score },
        { label: "Federalism concerns", key: "d2_2f", value: r.dim2_2f_score },
      ],
    },
    {
      label: "D3 — Policy Priority",
      composite: r.dim3_composite,
      subsections: [
        { label: "Small entity impact", key: "d3_f1", value: r.dim3_flag1_small_entity },
        { label: "Innovation/technology barrier", key: "d3_f2", value: r.dim3_flag2_innovation },
        { label: "Duplicative / overlapping", key: "d3_f3", value: r.dim3_flag3_duplicative },
        { label: "Outdated provisions", key: "d3_f4", value: r.dim3_flag4_outdated },
        { label: "Excessive burden", key: "d3_f5", value: r.dim3_flag5_excessive_burden },
        { label: "Enforcement discretion", key: "d3_f6", value: r.dim3_flag6_enforcement },
        { label: "Cross-agency conflict", key: "d3_f7", value: r.dim3_flag7_cross_agency },
      ],
    },
    {
      label: "D4 — Procedural Adequacy",
      composite: r.dim4_composite,
      subsections: [
        { label: "Comment response adequacy", key: "d4_4a", value: r.dim4_4a_score },
        { label: "Cost-benefit analysis quality", key: "d4_4b", value: r.dim4_4b_score },
        { label: "Notice-and-comment compliance", key: "d4_4c", value: r.dim4_4c_score },
        { label: "Alternatives analysis", key: "d4_4d", value: r.dim4_4d_score },
      ],
    },
    {
      label: "D5 — Nondelegation",
      composite: r.dim5_composite,
      subsections: [
        { label: "Breadth of delegation", key: "d5_5i", value: r.dim5_5i_score },
        { label: "Scope relative to statute", key: "d5_5ii", value: r.dim5_5ii_score },
        { label: "Intelligible principle adequacy", key: "d5_5iii", value: r.dim5_5iii_score },
        { label: "Industrial significance", key: "d5_5iv", value: r.dim5_5iv_score },
      ],
    },
  ];

  const legalTags = r.legal_theory_tags || [];
  const cfrSections = r.cfr_sections || [];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1400 }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => navigate("/loper/rules")} style={{ background: "none", border: "none", color: theme.accent.blueLight, cursor: "pointer", fontSize: 12, padding: 0 }}>
          &larr; Back to Explorer
        </button>
      </div>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: theme.text.primary, margin: 0, lineHeight: 1.3 }}>
              {r.title}
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, color: theme.text.dim, fontFamily: theme.font.mono }}>
                {r.fr_citation}
              </span>
              {r.docket_number && (
                <span style={{ fontSize: 12, color: theme.text.ghost }}>
                  Docket: {r.docket_number}
                </span>
              )}
              {r.publication_date && (
                <span style={{ fontSize: 12, color: theme.text.ghost }}>
                  Published: {r.publication_date.substring(0, 10)}
                </span>
              )}
              {r.effective_date && (
                <span style={{ fontSize: 12, color: theme.text.ghost }}>
                  Effective: {r.effective_date.substring(0, 10)}
                </span>
              )}
            </div>
          </div>

          <div style={{ textAlign: "center" }}>
            <div style={{
              fontSize: 32, fontWeight: 800,
              color: scoreColor(r.composite_score || 0),
              lineHeight: 1,
            }}>
              {r.composite_score != null ? r.composite_score.toFixed(2) : "—"}
            </div>
            <div style={{ fontSize: 10, color: theme.text.ghost, marginTop: 2 }}>COMPOSITE</div>
          </div>
        </div>

        {/* Tags row */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <Badge bg={ac.bg} text={ac.text} label={r.action_category || "—"} />
          {r.flag_vagueness === 1 && <Badge bg="#422006" text="#fbbf24" label="Vagueness" />}
          {r.flag_first_amendment === 1 && <Badge bg="#450a0a" text="#f87171" label="1st Amend." />}
          {r.has_commissioner_dissent === 1 && <Badge bg="#1f2937" text="#9ca3af" label="Dissent" />}
          {r.compound_vulnerability === 1 && <Badge bg="#2e1065" text="#a78bfa" label="Compound" />}
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
                    <span style={{ fontSize: 12, color: theme.text.muted, width: 120 }}>{d.label}</span>
                    <ScoreBar value={d.value} width={120} height={14} />
                  </div>
                ))}
                <div style={{ borderTop: `1px solid ${theme.border.subtle}`, paddingTop: 8, marginTop: 4 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: theme.text.muted, width: 120 }}>Comment Mult.</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: theme.text.secondary }}>
                      {r.comment_multiplier != null ? `${r.comment_multiplier.toFixed(2)}x` : "—"}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 20, marginTop: 4, paddingTop: 8, borderTop: `1px solid ${theme.border.subtle}` }}>
                  <div>
                    <div style={{ fontSize: 10, color: theme.text.ghost }}>Legal Challenge</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: scoreColor(r.legal_challenge_subcomposite || 0) }}>
                      {r.legal_challenge_subcomposite != null ? r.legal_challenge_subcomposite.toFixed(2) : "—"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: theme.text.ghost }}>Policy Priority</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: scoreColor(r.policy_priority_subcomposite || 0) }}>
                      {r.policy_priority_subcomposite != null ? r.policy_priority_subcomposite.toFixed(2) : "—"}
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

          {/* Stage 2 AI Analysis */}
          {assessments.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>
                Stage 2 AI Validation ({assessments.filter(a => a.sonnet_validation_result === "confirmed" || a.sonnet_validation_result === "upgraded").length}/{assessments.length} confirmed)
              </div>
              {assessments.map((a) => (
                <ModuleAnalysisCard key={a.module} assessment={a} />
              ))}
            </div>
          )}

          {/* Comment Record */}
          {(r.total_comment_count > 0 || r.substantive_comment_count > 0) && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Comment Record</div>
              <div style={{ display: "flex", gap: 30 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.secondary }}>{r.total_comment_count || 0}</div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>Total Comments</div>
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.secondary }}>{r.substantive_comment_count || 0}</div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>Substantive</div>
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: theme.text.secondary }}>{r.form_letter_cluster_count || 0}</div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>Form Letter Clusters</div>
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: theme.accent.yellow }}>{r.comment_multiplier != null ? `${r.comment_multiplier.toFixed(2)}x` : "—"}</div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>Multiplier</div>
                </div>
              </div>
            </div>
          )}

          {/* Procedural Analysis */}
          {(r.has_full_rfa != null || r.has_separate_economic_analysis != null || r.has_pra_analysis != null) && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Procedural Analysis</div>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                {[
                  { label: "Full RFA", value: r.has_full_rfa },
                  { label: "Separate Economic Analysis", value: r.has_separate_economic_analysis },
                  { label: "PRA Analysis", value: r.has_pra_analysis },
                ].map((item) => (
                  <div key={item.label} style={{
                    padding: "6px 12px", borderRadius: 6, fontSize: 12,
                    background: item.value ? "rgba(74,222,128,0.1)" : "rgba(239,68,68,0.1)",
                    color: item.value ? theme.accent.green : theme.accent.red,
                    border: `1px solid ${item.value ? "rgba(74,222,128,0.2)" : "rgba(239,68,68,0.2)"}`,
                  }}>
                    {item.value ? "\u2713" : "\u2717"} {item.label}
                  </div>
                ))}
                {r.pra_total_burden_hours != null && (
                  <div style={{ fontSize: 12, color: theme.text.muted, alignSelf: "center" }}>
                    PRA Burden: {r.pra_total_burden_hours.toLocaleString()} hours
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* Status Panel */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Status</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {cfrSections.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>CFR Sections</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>
                    {cfrSections.join(", ")}
                  </div>
                </div>
              )}
              {r.primary_statutory_authority && r.primary_statutory_authority.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>Statutory Authority</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>
                    {(r.primary_statutory_authority || []).join(", ")}
                  </div>
                </div>
              )}
              {r.rin && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>RIN</div>
                  <div style={{ fontSize: 12, color: theme.text.muted, fontFamily: theme.font.mono }}>{r.rin}</div>
                </div>
              )}
              {r.document_subtype && (
                <div>
                  <div style={{ fontSize: 10, color: theme.text.ghost }}>Subtype</div>
                  <div style={{ fontSize: 12, color: theme.text.muted }}>{r.document_subtype}</div>
                </div>
              )}
              <div style={{ borderTop: `1px solid ${theme.border.subtle}`, paddingTop: 8, marginTop: 4 }}>
                <div style={{ fontSize: 10, color: theme.text.ghost }}>Scoring</div>
                <div style={{ fontSize: 11, color: theme.text.dim }}>
                  Version: {r.scoring_version || "—"} | {r.scored_at ? r.scored_at.substring(0, 10) : "—"}
                </div>
                {r.has_missing_data === 1 && (
                  <div style={{ fontSize: 11, color: theme.accent.yellow, marginTop: 2 }}>
                    Has missing data
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* CEA Provisions */}
          {ceaProvisions.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>CEA Provisions ({ceaProvisions.length})</div>
              {ceaProvisions.map((p) => (
                <div key={p.cea_section} style={{
                  padding: 10, borderRadius: 6, marginBottom: 6,
                  background: "rgba(255,255,255,0.02)",
                  border: `1px solid ${theme.border.subtle}`,
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, fontFamily: theme.font.mono }}>
                    {p.cea_section}
                  </div>
                  {p.provision_title && (
                    <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 2 }}>{p.provision_title}</div>
                  )}
                  <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                    {p.specificity_score != null && (
                      <span style={{ fontSize: 10, color: theme.text.dim }}>
                        Specificity: {p.specificity_score}
                      </span>
                    )}
                    {p.delegation_score != null && (
                      <span style={{ fontSize: 10, color: theme.text.dim }}>
                        Delegation: {p.delegation_score}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Challenge History */}
          {challenges.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Challenge History ({challenges.length})</div>
              {challenges.map((ch, i) => (
                <div key={ch.id || i} style={{
                  padding: 10, borderRadius: 6, marginBottom: 6,
                  background: "rgba(239,68,68,0.06)",
                  border: "1px solid rgba(239,68,68,0.15)",
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
                    {ch.case_name}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.dim, marginTop: 2 }}>
                    {ch.court} {ch.date_decided ? `(${ch.date_decided.substring(0, 4)})` : ""}
                  </div>
                  {ch.outcome && (
                    <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 4 }}>
                      Outcome: {ch.outcome}
                    </div>
                  )}
                  {ch.current_status && (
                    <Badge
                      bg={ch.current_status === "active" || ch.current_status === "pending" ? "#422006" : "#1f2937"}
                      text={ch.current_status === "active" || ch.current_status === "pending" ? "#fbbf24" : "#6b7280"}
                      label={ch.current_status}
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Commissioner Voting */}
          {r.voting_record && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Commissioner Voting</div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {r.voting_record}
              </div>
            </div>
          )}

          {/* Related Rules */}
          {relatedRules.length > 0 && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Related Rules ({relatedRules.length})</div>
              {relatedRules.slice(0, 8).map((rel) => {
                const relAc = ACTION_COLORS[rel.action_category] || ACTION_COLORS["Manual review"];
                return (
                  <div
                    key={rel.fr_citation}
                    onClick={() => navigate(`/loper/rules/${encodeURIComponent(rel.fr_citation)}`)}
                    style={{
                      padding: 8, borderRadius: 6, marginBottom: 4, cursor: "pointer",
                      background: "rgba(255,255,255,0.02)",
                      border: `1px solid ${theme.border.subtle}`,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Badge bg={relAc.bg} text={relAc.text} label={rel.action_category || "—"} />
                      <span style={{ fontSize: 11, color: theme.text.muted, fontFamily: theme.font.mono }}>
                        {rel.composite_score != null ? rel.composite_score.toFixed(2) : "—"}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 4, lineHeight: 1.4 }}>
                      {rel.title ? rel.title.substring(0, 80) : rel.fr_citation}
                      {rel.title && rel.title.length > 80 ? "..." : ""}
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
              {relatedGuidance.slice(0, 8).map((g) => (
                <div
                  key={g.doc_id}
                  onClick={() => navigate(`/loper/guidance/${encodeURIComponent(g.doc_id)}`)}
                  style={{
                    padding: 8, borderRadius: 6, marginBottom: 4, cursor: "pointer",
                    background: "rgba(255,255,255,0.02)",
                    border: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 10, color: theme.text.ghost }}>{g.document_type}</span>
                    <span style={{ fontSize: 11, color: theme.text.muted, fontFamily: theme.font.mono }}>
                      {g.composite_score != null ? g.composite_score.toFixed(2) : "—"}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 2 }}>
                    {g.title ? g.title.substring(0, 80) : g.doc_id}
                    {g.title && g.title.length > 80 ? "..." : ""}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Actions */}
          <div style={cardStyle}>
            <div style={sectionTitle}>Quick Actions</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {r.url && (
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: "8px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: "rgba(59,130,246,0.12)", color: theme.accent.blueLight,
                    border: `1px solid rgba(59,130,246,0.25)`, textDecoration: "none",
                    textAlign: "center",
                  }}
                >
                  View in Federal Register
                </a>
              )}
              <button
                onClick={() => navigate(`/loper/rules`)}
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
          {r.notes && (
            <div style={cardStyle}>
              <div style={sectionTitle}>Notes</div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {r.notes}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
