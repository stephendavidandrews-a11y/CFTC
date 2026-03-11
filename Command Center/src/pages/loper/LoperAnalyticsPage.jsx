import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ScatterChart, Scatter, Cell,
  LineChart, Line, Legend,
} from "recharts";
import theme from "../../styles/theme";
import Badge from "../../components/shared/Badge";
import { getAnalytics } from "../../api/loper";
import useApi from "../../hooks/useApi";

const ACTION_COLORS = {
  Rescind: "#f87171", Amend: "#fbbf24", Reinterpret: "#a78bfa",
  Defend: "#60a5fa", "Manual review": "#9ca3af", Deprioritize: "#6b7280",
  Withdraw: "#f87171", Codify: "#4ade80", Narrow: "#fbbf24", Maintain: "#60a5fa",
};

const TABS = [
  { key: "by_theory", label: "By Legal Theory" },
  { key: "by_provision", label: "By CEA Provision" },
  { key: "by_era", label: "By Era" },
  { key: "dimension_correlation", label: "Dimension Correlation" },
  { key: "compound_vulnerability", label: "Compound Vulnerability" },
];

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 20,
};

const tooltipStyle = {
  contentStyle: {
    background: "#1e293b", border: `1px solid ${theme.border.default}`,
    borderRadius: 6, fontSize: 12, color: theme.text.secondary,
  },
};

export default function LoperAnalyticsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("by_theory");

  const { data, loading, error } = useApi(
    () => getAnalytics(tab),
    [tab] // eslint-disable-line
  );

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0 }}>
          Vulnerability Analytics
        </h1>
        <p style={{ fontSize: 12, color: theme.text.dim, margin: "4px 0 0" }}>
          Pattern analysis across CFTC regulatory portfolio
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
              cursor: "pointer",
              border: `1px solid ${tab === t.key ? theme.accent.blue : theme.border.default}`,
              background: tab === t.key ? "rgba(59,130,246,0.15)" : "transparent",
              color: tab === t.key ? theme.accent.blueLight : theme.text.dim,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading && (
        <div style={{ padding: 40, textAlign: "center", color: theme.text.faint }}>
          Loading analytics...
        </div>
      )}

      {error && (
        <div style={{
          padding: "12px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)", color: theme.accent.red, fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {!loading && !error && data && (
        <div style={cardStyle}>
          {tab === "by_theory" && <ByTheory data={data.data || data} navigate={navigate} />}
          {tab === "by_provision" && <ByProvision data={data.data || data} />}
          {tab === "by_era" && <ByEra data={data.data || data} />}
          {tab === "dimension_correlation" && <DimensionCorrelation data={data.data || data} navigate={navigate} />}
          {tab === "compound_vulnerability" && <CompoundVuln data={data.data || data} navigate={navigate} />}
        </div>
      )}

      {/* Quick links */}
      <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
        <button
          onClick={() => navigate("/loper")}
          style={{
            padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "rgba(59,130,246,0.12)", color: theme.accent.blueLight,
            border: `1px solid rgba(59,130,246,0.25)`, cursor: "pointer",
          }}
        >
          &larr; Dashboard
        </button>
        <button
          onClick={() => navigate("/loper/rules")}
          style={{
            padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: "rgba(167,139,250,0.12)", color: theme.accent.purple,
            border: `1px solid rgba(167,139,250,0.25)`, cursor: "pointer",
          }}
        >
          Explore Rules
        </button>
      </div>
    </div>
  );
}


/* ── Sub-components ─────────────────────────────────────────────── */

function ByTheory({ data, navigate }) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
        Rules by Legal Theory
      </div>
      <ResponsiveContainer width="100%" height={Math.max(300, data.length * 36)}>
        <BarChart data={data} layout="vertical" margin={{ left: 140 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.border.subtle} />
          <XAxis type="number" tick={{ fontSize: 11, fill: theme.text.dim }} />
          <YAxis
            type="category" dataKey="theory" width={130}
            tick={{ fontSize: 11, fill: theme.text.muted }}
          />
          <Tooltip {...tooltipStyle} />
          <Bar
            dataKey="count" fill={theme.accent.blue} radius={[0, 4, 4, 0]}
            cursor="pointer"
            onClick={(entry) => navigate(`/loper/rules?vulnerability=${encodeURIComponent(entry.theory)}`)}
          />
        </BarChart>
      </ResponsiveContainer>
      <div style={{ fontSize: 11, color: theme.text.ghost, marginTop: 10 }}>
        Click a bar to filter the Explorer by that theory.
      </div>
    </>
  );
}

function ByProvision({ data }) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
        Top CEA Provisions by Rule Count
      </div>
      <ResponsiveContainer width="100%" height={Math.max(400, data.length * 36)}>
        <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.border.subtle} />
          <XAxis type="number" tick={{ fontSize: 11, fill: theme.text.dim }} />
          <YAxis
            type="category" dataKey="provision" width={90}
            tick={{ fontSize: 10, fill: theme.text.muted }}
          />
          <Tooltip
            {...tooltipStyle}
            formatter={(v, name) => [
              name === "rule_count" ? v : v.toFixed(2),
              name === "rule_count" ? "Rules" : "Avg Composite",
            ]}
          />
          <Bar dataKey="rule_count" fill={theme.accent.purple} radius={[0, 4, 4, 0]} name="rule_count" />
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

function ByEra({ data }) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 14 }}>
        Vulnerability by Publication Era
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data} margin={{ left: 10, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.border.subtle} />
          <XAxis dataKey="year" tick={{ fontSize: 11, fill: theme.text.dim }} />
          <YAxis domain={[0, 10]} tick={{ fontSize: 11, fill: theme.text.dim }} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="avg_composite" stroke={theme.accent.blue} name="Avg Composite" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="avg_loper" stroke="#ef4444" name="Avg Loper Bright" strokeWidth={1.5} dot={{ r: 2 }} />
          <Line type="monotone" dataKey="avg_mq" stroke="#a78bfa" name="Avg Major Questions" strokeWidth={1.5} dot={{ r: 2 }} />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: 20, marginTop: 14, paddingTop: 10, borderTop: `1px solid ${theme.border.subtle}` }}>
        {data.map((d) => (
          <div key={d.year} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 11, color: theme.text.ghost }}>{d.year}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: theme.text.secondary }}>{d.count}</div>
            <div style={{ fontSize: 9, color: theme.text.ghost }}>rules</div>
          </div>
        ))}
      </div>
    </>
  );
}

function DimensionCorrelation({ data, navigate }) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 6 }}>
        Loper Bright (D1) vs Nondelegation (D5)
      </div>
      <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 14 }}>
        Each dot is a rule. Color = action category. Click to view detail.
      </div>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ bottom: 20, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.border.subtle} />
          <XAxis
            type="number" dataKey="dim1_composite" domain={[0, 10]}
            name="Loper Bright" tick={{ fontSize: 11, fill: theme.text.dim }}
            label={{ value: "D1 Loper Bright", position: "bottom", offset: 0, style: { fontSize: 11, fill: theme.text.faint } }}
          />
          <YAxis
            type="number" dataKey="dim5_composite" domain={[0, 10]}
            name="Nondelegation" tick={{ fontSize: 11, fill: theme.text.dim }}
            label={{ value: "D5 Nondelegation", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: theme.text.faint } }}
          />
          <Tooltip
            {...tooltipStyle}
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const d = payload[0].payload;
              return (
                <div style={{ background: "#1e293b", border: `1px solid ${theme.border.default}`, borderRadius: 6, padding: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.text.secondary, marginBottom: 4 }}>
                    {d.title ? d.title.substring(0, 60) : d.fr_citation}
                  </div>
                  <div style={{ fontSize: 11, color: theme.text.dim }}>
                    D1: {d.dim1_composite?.toFixed(1)} | D5: {d.dim5_composite?.toFixed(1)} | Composite: {d.composite_score?.toFixed(2)}
                  </div>
                </div>
              );
            }}
          />
          <Scatter
            data={data}
            cursor="pointer"
            onClick={(entry) => navigate(`/loper/rules/${encodeURIComponent(entry.fr_citation)}`)}
          >
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={ACTION_COLORS[entry.action_category] || "#6b7280"}
                opacity={0.7}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </>
  );
}

function CompoundVuln({ data, navigate }) {
  return (
    <>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, marginBottom: 6 }}>
        Compound Vulnerability (3+ Legal Theories)
      </div>
      <div style={{ fontSize: 11, color: theme.text.dim, marginBottom: 14 }}>
        {data.length} rules have 3 or more independent legal vulnerability theories.
      </div>
      <div style={{ maxHeight: 500, overflowY: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["FR Citation", "Title", "Score", "Action", "Theories", "#"].map((h) => (
                <th key={h} style={{
                  textAlign: "left", padding: "8px 10px", fontSize: 10, fontWeight: 700,
                  color: theme.text.faint, textTransform: "uppercase",
                  borderBottom: `1px solid ${theme.border.default}`,
                  position: "sticky", top: 0, background: theme.bg.card,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr
                key={r.fr_citation}
                onClick={() => navigate(`/loper/rules/${encodeURIComponent(r.fr_citation)}`)}
                style={{ cursor: "pointer" }}
              >
                <td style={{ padding: "8px 10px", fontSize: 12, color: theme.text.dim, fontFamily: theme.font.mono, borderBottom: `1px solid ${theme.border.subtle}` }}>
                  {r.fr_citation}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 12, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}`, maxWidth: 300 }}>
                  {r.title ? r.title.substring(0, 70) : "—"}
                  {r.title && r.title.length > 70 ? "..." : ""}
                </td>
                <td style={{ padding: "8px 10px", fontSize: 13, fontWeight: 700, borderBottom: `1px solid ${theme.border.subtle}`, color: (r.composite_score || 0) >= 7 ? "#ef4444" : (r.composite_score || 0) >= 5 ? "#f59e0b" : "#3b82f6" }}>
                  {r.composite_score != null ? r.composite_score.toFixed(2) : "—"}
                </td>
                <td style={{ padding: "8px 10px", borderBottom: `1px solid ${theme.border.subtle}` }}>
                  <Badge
                    bg={ACTION_COLORS[r.action_category] ? undefined : "#1f2937"}
                    text={ACTION_COLORS[r.action_category] || "#9ca3af"}
                    label={r.action_category || "—"}
                  />
                </td>
                <td style={{ padding: "8px 10px", borderBottom: `1px solid ${theme.border.subtle}` }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {(r.legal_theory_tags || []).map((t) => (
                      <Badge key={t} bg="#172554" text={theme.accent.blueLight} label={t} />
                    ))}
                  </div>
                </td>
                <td style={{ padding: "8px 10px", fontSize: 14, fontWeight: 700, color: theme.accent.red, borderBottom: `1px solid ${theme.border.subtle}` }}>
                  {r.tag_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
