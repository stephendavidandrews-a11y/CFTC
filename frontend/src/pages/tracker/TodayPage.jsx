import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import { cardStyle, titleStyle, subtitleStyle } from "../../styles/pageStyles";
import useApi from "../../hooks/useApi";
import { getDashboard, listMatters } from "../../api/tracker";
import { fetchJSON } from "../../api/client";
import StatCard from "../../components/shared/StatCard";
import Badge from "../../components/shared/Badge";
import { formatDate } from "../../utils/dateUtils";
import { matterRankScore } from "../../utils/ranking";

const TAG_COLORS = {
  BOSS:     { bg: "#7f1d1d", text: "#fca5a5" },
  DEADLINE: { bg: "#78350f", text: "#fbbf24" },
  BLOCKED:  { bg: "#450a0a", text: "#f87171" },
  OVERDUE:  { bg: "#431407", text: "#fb923c" },
  REVIEW:   { bg: "#1e3a5f", text: "#60a5fa" },
};

const sectionTitle = {
  fontSize: 14,
  fontWeight: 700,
  color: theme.text.secondary,
  marginBottom: 14,
};

function daysColor(days) {
  if (days == null) return theme.text.faint;
  if (days < 3) return theme.accent.red;
  if (days < 7) return theme.accent.yellow;
  return theme.text.secondary;
}

function formatShortDate(d) {
  if (!d) return null;
  const val = typeof d === "string" && d.length === 10 ? d + "T12:00:00" : d;
  const date = new Date(val);
  const daysUntil = (date - Date.now()) / (1000 * 60 * 60 * 24);
  const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  let color = theme.text.muted;
  if (daysUntil < 0) color = theme.accent.red;
  else if (daysUntil <= 3) color = theme.accent.red;
  else if (daysUntil <= 7) color = theme.accent.yellow;
  return { label, color };
}

export default function TodayPage() {
  useEffect(() => { document.title = "Today | Command Center"; }, []);
  const navigate = useNavigate();

  // Dashboard stats
  const { data: dashboard, loading } = useApi(() => getDashboard(), [], { refetchOnFocus: true });

  // Open matters for priority ranking
  const { data: mattersData } = useApi(() => listMatters({ limit: 100 }), []);

  // Today's brief (optional — fails silently if not generated yet)
  const [brief, setBrief] = useState(null);
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    fetchJSON(`/ai/api/intelligence/briefs/by-date/daily/${today}`)
      .then((r) => {
        if (r && !r.error) {
          const content = typeof r.content === "string" ? JSON.parse(r.content) : r.content;
          setBrief(content);
        }
      })
      .catch(() => setBrief(null));
  }, []);

  if (loading) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>
        Loading...
      </div>
    );
  }

  const d = dashboard || {};
  const stats = {
    open_matters:      d.total_open_matters ?? d.stats?.open_matters ?? 0,
    open_tasks:        d.total_open_tasks ?? d.stats?.open_tasks ?? 0,
    overdue_tasks:     d.overdue_tasks ?? d.stats?.overdue_tasks ?? 0,
    pending_decisions: Array.isArray(d.pending_decisions)
      ? d.pending_decisions.length
      : (d.stats?.pending_decisions ?? 0),
  };
  const overdueCount  = stats.overdue_tasks || 0;
  const deadlines     = (d.upcoming_deadlines || []).slice(0, 7);
  const recentUpdates = (d.recent_updates    || []).slice(0, 8);

  // Priority actions: top 7 non-closed matters by composite rank score
  const rawMatters = mattersData?.items || mattersData || [];
  const priorityMatters = [...rawMatters]
    .filter((m) => m.status !== "closed")
    .sort((a, b) => matterRankScore(b) - matterRankScore(a))
    .slice(0, 7);

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Today</div>
      <div style={subtitleStyle}>What needs your attention right now</div>

      {/* Section 1: Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard value={stats.open_matters}     label="Open Matters"     accent={theme.accent.blue} />
        <StatCard value={stats.open_tasks}        label="Open Tasks"        accent={theme.accent.teal} />
        <StatCard
          value={overdueCount}
          label="Overdue Tasks"
          accent={overdueCount > 0 ? theme.accent.red : theme.text.faint}
          pulse={overdueCount > 0}
        />
        <StatCard value={stats.pending_decisions} label="Pending Decisions" accent={theme.accent.purple} />
      </div>

      {/* Section 2: Priority Actions */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={sectionTitle}>Priority Actions</div>
          <span
            onClick={() => navigate("/matters")}
            style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}
          >
            View All &rarr;
          </span>
        </div>
        {priorityMatters.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.text.faint }}>No open matters.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {priorityMatters.map((m, i) => {
                const p   = theme.priority[m.priority] || { bg: theme.bg.input, text: theme.text.faint, label: m.priority };
                const dl  = m.work_deadline || m.external_deadline || m.decision_deadline;
                const fmt = dl ? formatShortDate(dl) : null;
                return (
                  <tr
                    key={m.id || i}
                    onClick={() => navigate(`/matters/${m.id}`)}
                    onMouseEnter={(e) => (e.currentTarget.style.background = theme.bg.cardHover)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    style={{ cursor: "pointer" }}
                  >
                    <td style={{ padding: "10px 12px 10px 0", width: 170, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      <Badge bg={p.bg} text={p.text} label={p.label || m.priority || "\u2014"} />
                    </td>
                    <td style={{ padding: "10px 12px", borderBottom: `1px solid ${theme.border.subtle}` }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: theme.accent.blueLight }}>
                        {m.title}
                      </div>
                      {m.next_step && (
                        <div style={{
                          fontSize: 11, color: theme.text.faint, marginTop: 2,
                          maxWidth: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                          {m.next_step}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "10px 12px", width: 100, textAlign: "right", borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {fmt ? (
                        <span style={{ fontSize: 12, fontWeight: 600, color: fmt.color }}>
                          {fmt.label}
                        </span>
                      ) : (
                        <span style={{ fontSize: 12, color: theme.text.faint }}>{"\u2014"}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Section 3 + 4: Deadlines | Brief */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>

        {/* Upcoming Deadlines */}
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={sectionTitle}>Upcoming Deadlines</div>
            <span
              onClick={() => navigate("/tasks")}
              style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}
            >
              View All &rarr;
            </span>
          </div>
          {deadlines.length === 0 ? (
            <div style={{ fontSize: 13, color: theme.text.faint }}>No upcoming deadlines.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Matter", "Type", "Date", "Days"].map((h) => (
                    <th key={h} style={{
                      textAlign: "left", padding: "6px 8px", fontSize: 10, fontWeight: 700,
                      color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em",
                      borderBottom: `1px solid ${theme.border.default}`,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {deadlines.map((dl, i) => {
                  const days = dl.days_until ?? dl.days;
                  return (
                    <tr
                      key={i}
                      style={{ cursor: "pointer" }}
                      onClick={() => dl.matter_id && navigate(`/matters/${dl.matter_id}`)}
                      onMouseEnter={(e) => (e.currentTarget.style.background = theme.bg.cardHover)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ padding: "8px", fontSize: 12, color: theme.text.secondary, borderBottom: `1px solid ${theme.border.subtle}` }}>
                        {dl.matter_title || dl.matter || "\u2014"}
                      </td>
                      <td style={{ padding: "8px", fontSize: 12, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                        {dl.deadline_type || dl.type || "\u2014"}
                      </td>
                      <td style={{ padding: "8px", fontSize: 12, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                        {formatDate(dl.date || dl.deadline_date)}
                      </td>
                      <td style={{ padding: "8px", fontSize: 12, fontWeight: 600, color: daysColor(days), borderBottom: `1px solid ${theme.border.subtle}` }}>
                        {days != null ? `${days}d` : "\u2014"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* AI Daily Brief Preview */}
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={sectionTitle}>Today's Brief</div>
            <span
              onClick={() => navigate("/intelligence/daily")}
              style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}
            >
              View Full Brief &rarr;
            </span>
          </div>

          {brief == null ? (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{ fontSize: 13, color: theme.text.faint, marginBottom: 12 }}>
                No daily brief generated yet.
              </div>
              <button
                onClick={() => navigate("/intelligence/daily")}
                style={{
                  background: theme.accent.blue, color: "#fff", border: "none",
                  borderRadius: 6, padding: "7px 14px", fontSize: 13, cursor: "pointer",
                }}
              >
                Generate Brief
              </button>
            </div>
          ) : (
            <>
              {(brief.action_list || []).slice(0, 5).map((a, i) => {
                const tc = TAG_COLORS[a.tag] || { bg: "#1f2937", text: "#9ca3af" };
                return (
                  <div
                    key={i}
                    style={{
                      padding: "7px 0",
                      borderBottom: `1px solid ${theme.border.subtle}`,
                      cursor: a.entity_type && a.entity_id ? "pointer" : "default",
                    }}
                    onClick={() => {
                      if (a.entity_type === "matter") navigate(`/matters/${a.entity_id}`);
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <span style={{
                        display: "inline-block", padding: "2px 7px", borderRadius: 3,
                        fontSize: 9, fontWeight: 700, background: tc.bg, color: tc.text,
                        textTransform: "uppercase", letterSpacing: "0.04em", flexShrink: 0,
                      }}>
                        {a.tag}
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 500, color: theme.text.secondary }}>
                        {a.title}
                      </span>
                    </div>
                  </div>
                );
              })}

              {(brief.meetings || []).length > 0 && (
                <>
                  <div style={{ fontSize: 11, fontWeight: 700, color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 12, marginBottom: 6 }}>
                    Meetings
                  </div>
                  {brief.meetings.map((m, i) => (
                    <div
                      key={i}
                      style={{ padding: "5px 0", borderBottom: `1px solid ${theme.border.subtle}`, cursor: m.id ? "pointer" : "default" }}
                      onClick={() => m.id && navigate(`/meetings/${m.id}`)}
                    >
                      <div style={{ fontSize: 12, fontWeight: 500, color: theme.text.secondary }}>{m.title}</div>
                      {m.start_time && (
                        <div style={{ fontSize: 11, color: theme.text.faint }}>{m.start_time.slice(0, 5)}</div>
                      )}
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Section 5: Recent Activity */}
      <div style={cardStyle}>
        <div style={sectionTitle}>Recent Activity</div>
        {recentUpdates.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.text.faint }}>No recent updates.</div>
        ) : (
          recentUpdates.map((u, i) => (
            <div key={i} style={{ padding: "10px 0", borderBottom: `1px solid ${theme.border.subtle}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 13, color: theme.text.secondary, fontWeight: 500 }}>
                  {u.matter_title || u.matter || "Matter"}
                </span>
                {u.update_type && (
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: theme.accent.blue,
                    background: "rgba(59,130,246,0.12)", padding: "2px 7px", borderRadius: 3,
                  }}>
                    {u.update_type}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.4 }}>
                {u.summary
                  ? u.summary.length > 120 ? u.summary.slice(0, 120) + "..." : u.summary
                  : "\u2014"}
              </div>
              <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 3 }}>
                {formatDate(u.created_at || u.date)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
