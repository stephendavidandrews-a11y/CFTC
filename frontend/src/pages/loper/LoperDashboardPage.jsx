import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import StatCard from "../../components/shared/StatCard";
import Badge from "../../components/shared/Badge";
import ScoreBar from "../../components/loper/ScoreBar";
import { getDashboard } from "../../api/loper";
import useApi from "../../hooks/useApi";
import useMediaQuery from "../../hooks/useMediaQuery";

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
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 20,
};

export default function LoperDashboardPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const { data, loading, error } = useApi(() => getDashboard(), []);

  const dimAvgs = useMemo(() => {
    if (!data?.dimension_averages) return [];
    const d = data.dimension_averages;
    return [
      { label: "Loper Bright", value: d.avg_d1 },
      { label: "Major Questions", value: d.avg_d2 },
      { label: "Policy Priority", value: d.avg_d3 },
      { label: "Procedural", value: d.avg_d4 },
      { label: "Nondelegation", value: d.avg_d5 },
    ];
  }, [data]);

  if (loading) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{
          padding: "12px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)", color: theme.accent.red, fontSize: 13,
        }}>
          {error}
        </div>
      </div>
    );
  }

  const d = data || {};

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          Loper Bright Vulnerability Analyzer
        </h1>
        <p style={{ fontSize: 12, color: theme.text.dim, margin: "4px 0 0" }}>
          Post-Loper Bright regulatory vulnerability assessment across CFTC rules and guidance
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5, 1fr)", gap: 14, marginBottom: 24 }}>
        <StatCard value={d.rules_total || 0} label="Rules Scored" accent={theme.accent.blue} />
        <StatCard value={d.guidance_total || 0} label="Guidance Docs" accent={theme.accent.purple} />
        <StatCard
          value={(d.rule_actions || []).find((a) => a.action_category === "Amend")?.cnt || 0}
          label="Amend Priority"
          accent={theme.accent.yellow}
        />
        <StatCard value={d.s2_confirmed || 0} label="AI Confirmed" accent={theme.accent.green} />
        <StatCard value={d.active_challenges || 0} label="Active Challenges" accent={theme.accent.red} />
      </div>

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {/* Rule Action Distribution */}
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
            Rule Action Distribution
          </div>
          {(d.rule_actions || []).map((a) => {
            const ac = ACTION_COLORS[a.action_category] || ACTION_COLORS["Manual review"];
            const pct = d.rules_total ? (a.cnt / d.rules_total) * 100 : 0;
            return (
              <div
                key={a.action_category}
                style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, cursor: "pointer" }}
                onClick={() => navigate(`/loper/rules?action_category=${encodeURIComponent(a.action_category)}`)}
              >
                <Badge bg={ac.bg} text={ac.text} label={a.action_category} />
                <div style={{ flex: 1, height: 8, borderRadius: 4, background: "rgba(255,255,255,0.06)" }}>
                  <div style={{
                    width: `${pct}%`, height: "100%", borderRadius: 4,
                    background: ac.text, opacity: 0.7,
                  }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, minWidth: 30, textAlign: "right" }}>
                  {a.cnt}
                </span>
              </div>
            );
          })}
        </div>

        {/* Dimension Averages */}
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
            Average Dimension Scores
          </div>
          {dimAvgs.map((d) => (
            <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <span style={{ fontSize: 12, color: theme.text.muted, width: 120 }}>{d.label}</span>
              <ScoreBar value={d.value} width={160} height={14} />
            </div>
          ))}
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${theme.border.subtle}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 12, color: theme.text.muted, width: 120 }}>Overall Avg</span>
              <ScoreBar value={data?.dimension_averages?.avg_composite} width={160} height={14} />
            </div>
          </div>
        </div>
      </div>

      {/* S2 Validation Summary */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
            Stage 2 AI Validation
          </div>
          <div style={{ display: "flex", gap: 20 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: theme.accent.green }}>{d.s2_confirmed || 0}</div>
              <div style={{ fontSize: 11, color: theme.text.dim }}>Confirmed/Upgraded</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: theme.accent.yellow }}>{d.s2_downgraded || 0}</div>
              <div style={{ fontSize: 11, color: theme.text.dim }}>Downgraded</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: theme.text.dim }}>{d.s2_false_positive || 0}</div>
              <div style={{ fontSize: 11, color: theme.text.dim }}>False Positive</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: theme.text.secondary }}>{d.s2_total || 0}</div>
              <div style={{ fontSize: 11, color: theme.text.dim }}>Total Assessments</div>
            </div>
          </div>
          {d.s2_total > 0 && (
            <div style={{ marginTop: 14, height: 8, borderRadius: 4, background: "rgba(255,255,255,0.06)", display: "flex", overflow: "hidden" }}>
              <div style={{ width: `${((d.s2_confirmed || 0) / d.s2_total) * 100}%`, background: theme.accent.green, height: "100%" }} />
              <div style={{ width: `${((d.s2_downgraded || 0) / d.s2_total) * 100}%`, background: theme.accent.yellow, height: "100%" }} />
              <div style={{ width: `${((d.s2_false_positive || 0) / d.s2_total) * 100}%`, background: "#4b5563", height: "100%" }} />
            </div>
          )}
        </div>

        {/* Guidance Action Distribution */}
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
            Guidance Action Distribution
          </div>
          {(d.guidance_actions || []).map((a) => {
            const ac = ACTION_COLORS[a.action_category] || ACTION_COLORS["Manual review"];
            const pct = d.guidance_total ? (a.cnt / d.guidance_total) * 100 : 0;
            return (
              <div
                key={a.action_category}
                style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, cursor: "pointer" }}
                onClick={() => navigate(`/loper/guidance?action_category=${encodeURIComponent(a.action_category)}`)}
              >
                <Badge bg={ac.bg} text={ac.text} label={a.action_category} />
                <div style={{ flex: 1, height: 8, borderRadius: 4, background: "rgba(255,255,255,0.06)" }}>
                  <div style={{
                    width: `${pct}%`, height: "100%", borderRadius: 4,
                    background: ac.text, opacity: 0.7,
                  }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, minWidth: 30, textAlign: "right" }}>
                  {a.cnt}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Active Challenges */}
      {(d.active_challenge_details || []).length > 0 && (
        <div style={cardStyle}>
          <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
            Active Legal Challenges ({d.active_challenge_details.length})
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 10 }}>
            {d.active_challenge_details.slice(0, 9).map((ch, i) => (
              <div
                key={ch.id || i}
                style={{
                  padding: 12, borderRadius: 8,
                  background: "rgba(239,68,68,0.06)",
                  border: "1px solid rgba(239,68,68,0.15)",
                  cursor: ch.fr_citation ? "pointer" : "default",
                }}
                onClick={() => ch.fr_citation && navigate(`/loper/rules/${encodeURIComponent(ch.fr_citation)}`)}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, marginBottom: 4 }}>
                  {ch.case_name}
                </div>
                <div style={{ fontSize: 11, color: theme.text.dim }}>
                  {ch.court} {ch.date_decided ? `(${ch.date_decided.substring(0, 4)})` : ""}
                </div>
                {ch.rule_title && (
                  <div style={{ fontSize: 11, color: theme.text.muted, marginTop: 4 }}>
                    Re: {ch.rule_title.substring(0, 60)}...
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
        <button
          onClick={() => navigate("/loper/rules")}
          style={{
            padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "rgba(59,130,246,0.12)", color: theme.accent.blueLight,
            border: `1px solid rgba(59,130,246,0.25)`, cursor: "pointer",
          }}
        >
          Explore Rules →
        </button>
        <button
          onClick={() => navigate("/loper/guidance")}
          style={{
            padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "rgba(167,139,250,0.12)", color: theme.accent.purple,
            border: `1px solid rgba(167,139,250,0.25)`, cursor: "pointer",
          }}
        >
          Explore Guidance →
        </button>
        <button
          onClick={() => navigate("/loper/analytics")}
          style={{
            padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "rgba(52,211,153,0.12)", color: theme.accent.teal,
            border: `1px solid rgba(52,211,153,0.25)`, cursor: "pointer",
          }}
        >
          Analytics →
        </button>
      </div>
    </div>
  );
}
