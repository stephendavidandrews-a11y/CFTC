import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getDashboard } from "../../api/tracker";
import StatCard from "../../components/shared/StatCard";
import Badge from "../../components/shared/Badge";
import { formatDate } from "../../utils/dateUtils";

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 24 };
const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

function daysColor(days) {
  if (days < 3) return theme.accent.red;
  if (days < 7) return theme.accent.yellow;
  return theme.text.secondary;
}


function HBar({ label, value, max, color }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
      <span style={{ width: 110, fontSize: 12, color: theme.text.muted, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, background: theme.bg.input, borderRadius: 4, height: 18, position: "relative" }}>
        <div style={{
          width: `${pct}%`, height: "100%", borderRadius: 4,
          background: color || theme.accent.blue, transition: "width 0.3s ease",
        }} />
      </div>
      <span style={{ width: 30, textAlign: "right", fontSize: 12, fontWeight: 600, color: theme.text.secondary }}>
        {value}
      </span>
    </div>
  );
}

export default function TrackerDashboardPage() {
  useEffect(() => { document.title = "Dashboard | Command Center"; }, []);
  const navigate = useNavigate();
  const { data, loading, error } = useApi(() => getDashboard(), [], { refetchOnFocus: true });

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
        <div style={{ padding: "12px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)", color: theme.accent.red, fontSize: 13 }}>
          Error loading dashboard: {error.message || String(error)}
        </div>
      </div>
    );
  }

  const d = data || {};
  const stats = {
    open_matters: d.total_open_matters ?? d.stats?.open_matters ?? 0,
    open_tasks: d.total_open_tasks ?? d.stats?.open_tasks ?? 0,
    overdue_tasks: d.overdue_tasks ?? d.stats?.overdue_tasks ?? 0,
    pending_decisions: Array.isArray(d.pending_decisions) ? d.pending_decisions.length : (d.stats?.pending_decisions ?? 0),
  };
  const mattersByStatus = d.matters_by_status || {};
  const mattersByPriority = d.matters_by_priority || {};
  const deadlines = (d.upcoming_deadlines || []).slice(0, 5);
  const recentMatters = (d.recent_matters || []).slice(0, 5);
  const recentUpdates = (d.recent_updates || []).slice(0, 5);
  const tasksDue = (d.tasks_due_soon || []).slice(0, 5);

  const maxStatus = Math.max(1, ...Object.values(mattersByStatus));
  const maxPriority = Math.max(1, ...Object.values(mattersByPriority));

  const statusColors = {
    active: theme.accent.blue,
    in_progress: theme.accent.blue,
    paused: theme.accent.yellow,
    completed: theme.accent.green,
    withdrawn: theme.text.faint,
    archived: theme.text.ghost,
  };

  const priorityColors = {
    critical: theme.accent.red,
    high: theme.accent.yellow,
    medium: theme.accent.blue,
    low: theme.text.faint,
  };

  const overdueCount = stats.overdue_tasks || 0;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Operations Dashboard</div>
      <div style={subtitleStyle}>CFTC Regulatory Ops Tracker overview</div>

      {/* Row 1: Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard value={stats.open_matters ?? 0} label="Open Matters" accent={theme.accent.blue} />
        <StatCard value={stats.open_tasks ?? 0} label="Open Tasks" accent={theme.accent.teal} />
        <StatCard
          value={overdueCount}
          label="Overdue Tasks"
          accent={overdueCount > 0 ? theme.accent.red : theme.text.faint}
          pulse={overdueCount > 0}
        />
        <StatCard value={stats.pending_decisions ?? 0} label="Pending Decisions" accent={theme.accent.purple} />
      </div>

      {/* Row 2: Matters by Status + Priority */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={cardStyle}>
          <div style={sectionTitle}>Matters by Status</div>
          {Object.entries(mattersByStatus).map(([key, val]) => (
            <HBar key={key} label={key.replace(/_/g, " ")} value={val} max={maxStatus} color={statusColors[key] || theme.accent.blue} />
          ))}
          {Object.keys(mattersByStatus).length === 0 && (
            <div style={{ fontSize: 13, color: theme.text.faint }}>No data</div>
          )}
        </div>
        <div style={cardStyle}>
          <div style={sectionTitle}>Matters by Priority</div>
          {Object.entries(mattersByPriority).map(([key, val]) => (
            <HBar key={key} label={key} value={val} max={maxPriority} color={priorityColors[key] || theme.accent.blue} />
          ))}
          {Object.keys(mattersByPriority).length === 0 && (
            <div style={{ fontSize: 13, color: theme.text.faint }}>No data</div>
          )}
        </div>
      </div>

      {/* Row 3: Upcoming Deadlines */}
      <div style={{ ...cardStyle, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={sectionTitle}>Upcoming Deadlines</div><span onClick={() => navigate("/tasks")} style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}>View All &rarr;</span></div>
        {deadlines.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.text.faint }}>No upcoming deadlines</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Matter", "Deadline Type", "Date", "Days Until"].map((h) => (
                  <th key={h} style={{
                    textAlign: "left", padding: "8px 12px", fontSize: 11, fontWeight: 700,
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
                  <tr key={i} style={{ cursor: "pointer" }}
                    onClick={() => dl.matter_id && navigate(`/matters/${dl.matter_id}`)}
                    onMouseEnter={(e) => e.currentTarget.style.background = theme.bg.cardHover}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.secondary, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {dl.matter_title || dl.matter || "\u2014"}
                    </td>
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {dl.deadline_type || dl.type || "\u2014"}
                    </td>
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {formatDate(dl.date || dl.deadline_date)}
                    </td>
                    <td style={{ padding: "10px 12px", fontSize: 13, fontWeight: 600, color: daysColor(days), borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {days != null ? `${days}d` : "\u2014"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Row 4: Tasks Due Soon */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={sectionTitle}>Tasks Due Soon</div><span onClick={() => navigate("/tasks")} style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}>View All &rarr;</span></div>
        {tasksDue.length === 0 ? (
          <div style={{ fontSize: 13, color: theme.text.faint }}>No tasks due soon</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Title", "Assignee", "Due Date", "Status"].map((h) => (
                  <th key={h} style={{
                    textAlign: "left", padding: "8px 12px", fontSize: 11, fontWeight: 700,
                    color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em",
                    borderBottom: `1px solid ${theme.border.default}`,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tasksDue.map((t, i) => {
                const st = theme.status[t.status] || { bg: theme.bg.input, text: theme.text.faint, label: t.status };
                return (
                  <tr key={t.id || i}
                    onMouseEnter={(e) => e.currentTarget.style.background = theme.bg.cardHover}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.secondary, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {t.title}
                    </td>
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {t.assignee_name || t.assigned_to_name || "\u2014"}
                    </td>
                    <td style={{ padding: "10px 12px", fontSize: 13, color: theme.text.muted, borderBottom: `1px solid ${theme.border.subtle}` }}>
                      {formatDate(t.due_date)}
                    </td>
                    <td style={{ padding: "10px 12px", borderBottom: `1px solid ${theme.border.subtle}` }}>
                      <Badge bg={st.bg} text={st.text} label={st.label || t.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
{/* Row 5: Recent Matters + Recent Updates */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><div style={sectionTitle}>Recent Matters</div><span onClick={() => navigate("/matters")} style={{ fontSize: 12, color: theme.accent.blueLight, cursor: "pointer" }}>View All &rarr;</span></div>
          {recentMatters.length === 0 ? (
            <div style={{ fontSize: 13, color: theme.text.faint }}>No recent matters</div>
          ) : (
            recentMatters.map((m, i) => {
              const st = theme.status[m.status] || { bg: theme.bg.input, text: theme.text.faint, label: m.status };
              return (
                <div key={m.id || i}
                  onClick={() => m.id && navigate(`/matters/${m.id}`)}
                  onMouseEnter={(e) => e.currentTarget.style.background = theme.bg.cardHover}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "10px 0", borderBottom: `1px solid ${theme.border.subtle}`, cursor: "pointer",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, color: theme.text.secondary, fontWeight: 500 }}>{m.title}</div>
                    <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 2 }}>{formatDate(m.opened_date || m.created_at)}</div>
                  </div>
                  <Badge bg={st.bg} text={st.text} label={st.label || m.status} />
                </div>
              );
            })
          )}
        </div>

        <div style={cardStyle}>
          <div style={sectionTitle}>Recent Updates</div>
          {recentUpdates.length === 0 ? (
            <div style={{ fontSize: 13, color: theme.text.faint }}>No recent updates</div>
          ) : (
            recentUpdates.map((u, i) => (
              <div key={i} style={{
                padding: "10px 0", borderBottom: `1px solid ${theme.border.subtle}`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: theme.text.secondary, fontWeight: 500 }}>
                    {u.matter_title || u.matter || "Matter"}
                  </span>
                  {u.update_type && (
                    <span style={{
                      fontSize: 10, fontWeight: 600, color: theme.accent.blue,
                      background: "rgba(59,130,246,0.12)", padding: "2px 7px", borderRadius: 3,
                    }}>{u.update_type}</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: theme.text.muted, lineHeight: 1.4 }}>
                  {u.summary ? (u.summary.length > 120 ? u.summary.slice(0, 120) + "..." : u.summary) : "\u2014"}
                </div>
                <div style={{ fontSize: 11, color: theme.text.faint, marginTop: 3 }}>{formatDate(u.created_at || u.date)}</div>
              </div>
            ))
          )}
        </div>
      </div>

          </div>
  );
}
