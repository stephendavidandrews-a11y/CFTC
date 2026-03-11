import React from "react";
import LiveFeed from "../components/shared/LiveFeed";
import StatCard from "../components/shared/StatCard";
import Pulse from "../components/shared/Pulse";
import Badge from "../components/shared/Badge";
import theme from "../styles/theme";
import { useApi } from "../hooks/useApi";
import { getExecutiveSummary, getEOActions } from "../api/pipeline";

export default function IntelligencePage() {
  const { data: summary } = useApi(() => getExecutiveSummary(), []);
  const { data: eoActions } = useApi(() => getEOActions(), []);

  const s = summary || {
    active_rulemakings: 0, active_reg_actions: 0,
    total_overdue_deadlines: 0, recent_activity: [],
    pipeline_distribution: {},
  };

  const actions = eoActions || [];

  // EO actions with upcoming deadlines (next 90 days)
  const now = new Date();
  const upcomingEO = actions
    .filter((a) => a.deadline && a.status !== "completed" && a.status !== "superseded")
    .map((a) => {
      const dl = new Date(a.deadline);
      const daysUntil = Math.ceil((dl - now) / (1000 * 60 * 60 * 24));
      return { ...a, daysUntil };
    })
    .filter((a) => a.daysUntil <= 90 && a.daysUntil >= -30)
    .sort((a, b) => a.daysUntil - b.daysUntil);

  // Pipeline distribution
  const dist = s.pipeline_distribution || {};
  const distEntries = Object.entries(dist).filter(([_, v]) => v > 0);
  const distTotal = distEntries.reduce((sum, [_, v]) => sum + v, 0);
  const DIST_COLORS = [theme.accent.blue, theme.accent.purple, theme.accent.green, theme.accent.yellow, theme.accent.teal, theme.accent.red];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0, letterSpacing: "-0.02em" }}>
          Intelligence
        </h2>
        <Pulse color={theme.accent.green} />
        <span style={{ fontSize: 11, color: theme.text.faint }}>Real-time</span>
      </div>

      {/* Stat cards — wired to real data */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
        <StatCard value={s.active_rulemakings} label="Active Rulemakings" accent={theme.accent.purple} />
        <StatCard value={s.active_reg_actions} label="Reg Actions" accent={theme.accent.blue} />
        <StatCard value={s.total_overdue_deadlines} label="Overdue Deadlines" accent={theme.accent.red} pulse={s.total_overdue_deadlines > 0} />
        <StatCard value={actions.length} label="EO Actions" accent={theme.accent.teal} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* EO Deadline Countdown */}
          {upcomingEO.length > 0 && (
            <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: "0 0 14px" }}>
                EO Deadline Countdown
              </h3>
              {upcomingEO.slice(0, 8).map((eo, i) => {
                const isOverdue = eo.daysUntil < 0;
                const isUrgent = eo.daysUntil <= 7 && !isOverdue;
                const color = isOverdue ? theme.accent.red : isUrgent ? theme.accent.yellow : theme.accent.blue;
                return (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                    borderBottom: `1px solid ${theme.border.default}`,
                  }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 8, flexShrink: 0,
                      background: `${color}15`, border: `1px solid ${color}30`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexDirection: "column",
                    }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color, lineHeight: 1 }}>
                        {isOverdue ? Math.abs(eo.daysUntil) : eo.daysUntil}
                      </div>
                      <div style={{ fontSize: 8, color, fontWeight: 600, textTransform: "uppercase" }}>
                        {isOverdue ? "overdue" : "days"}
                      </div>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 12, fontWeight: 500, color: theme.text.secondary,
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                      }}>
                        {eo.action_description || eo.title}
                      </div>
                      <div style={{ fontSize: 10, color: theme.text.faint, marginTop: 2 }}>
                        {eo.deadline} · {eo.cftc_role || "—"}
                      </div>
                    </div>
                    <Badge
                      bg={isOverdue ? "#450a0a" : isUrgent ? "#422006" : "#172554"}
                      text={isOverdue ? theme.accent.redLight : isUrgent ? theme.accent.yellowLight : theme.accent.blueLight}
                      label={eo.priority || "—"}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* Pipeline Distribution */}
          {distEntries.length > 0 && (
            <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: "0 0 14px" }}>
                Pipeline Stage Distribution
              </h3>
              {/* Stacked bar */}
              <div style={{ display: "flex", height: 24, borderRadius: 6, overflow: "hidden", marginBottom: 12 }}>
                {distEntries.map(([stage, count], i) => (
                  <div
                    key={stage}
                    style={{
                      width: `${(count / distTotal) * 100}%`,
                      background: DIST_COLORS[i % DIST_COLORS.length],
                      transition: "width 0.3s",
                    }}
                    title={`${stage}: ${count}`}
                  />
                ))}
              </div>
              {/* Legend */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                {distEntries.map(([stage, count], i) => (
                  <div key={stage} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: 2,
                      background: DIST_COLORS[i % DIST_COLORS.length],
                    }} />
                    <span style={{ fontSize: 11, color: theme.text.dim }}>
                      {stage} ({count})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Live Feed — wired to real data */}
        <LiveFeed items={s.recent_activity.length > 0 ? s.recent_activity : undefined} />
      </div>
    </div>
  );
}
