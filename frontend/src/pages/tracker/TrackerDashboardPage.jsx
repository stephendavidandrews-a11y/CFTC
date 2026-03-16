import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import theme from "../../styles/theme";
import useApi from "../../hooks/useApi";
import { getDashboard, listMeetings, listPeople, listTasks } from "../../api/tracker";
import StatCard from "../../components/shared/StatCard";
import Badge from "../../components/shared/Badge";

/* ── shared styles ─────────────────────────────────────────────────────── */

const cardStyle = {
  background: theme.bg.card,
  borderRadius: 10,
  border: `1px solid ${theme.border.default}`,
  padding: 24,
};

const titleStyle = { fontSize: 22, fontWeight: 700, color: theme.text.primary, marginBottom: 4 };
const subtitleStyle = { fontSize: 13, color: theme.text.dim, marginBottom: 24 };
const sectionTitle = { fontSize: 14, fontWeight: 700, color: theme.text.secondary, marginBottom: 14 };

const thStyle = {
  textAlign: "left", padding: "8px 12px", fontSize: 11, fontWeight: 700,
  color: theme.text.faint, textTransform: "uppercase", letterSpacing: "0.05em",
  borderBottom: `1px solid ${theme.border.default}`,
};
const tdStyle = {
  padding: "10px 12px", fontSize: 13, color: theme.text.secondary,
  borderBottom: `1px solid ${theme.border.subtle}`,
};

/* ── helpers ───────────────────────────────────────────────────────────── */

function formatDate(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatDateTime(d) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function daysUntil(d) {
  if (!d) return Infinity;
  const diff = (new Date(d).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000;
  return Math.round(diff);
}

function overdueLabel(d) {
  const days = daysUntil(d);
  if (days >= 0) return null;
  const abs = Math.abs(days);
  return abs === 1 ? "1 day overdue" : `${abs} days overdue`;
}

function dueLabel(d) {
  const days = daysUntil(d);
  if (days < 0) return overdueLabel(d);
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `Due in ${days} days`;
}

function SectionCard({ title, borderColor, children, style }) {
  return (
    <div style={{
      ...cardStyle,
      borderLeft: `3px solid ${borderColor}`,
      ...style,
    }}>
      <div style={{ ...sectionTitle, color: borderColor, marginBottom: 16 }}>{title}</div>
      {children}
    </div>
  );
}

function EmptyState({ text }) {
  return <div style={{ fontSize: 13, color: theme.text.faint, padding: "12px 0" }}>{text}</div>;
}

function HoverRow({ children, onClick, style }) {
  return (
    <tr
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default", ...style }}
      onMouseEnter={(e) => (e.currentTarget.style.background = theme.bg.cardHover)}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      {children}
    </tr>
  );
}

/* ── main component ────────────────────────────────────────────────────── */

export default function TrackerDashboardPage() {
  const navigate = useNavigate();

  const { data: dashData, loading: loadDash, error: errDash } = useApi(() => getDashboard(), []);
  const { data: meetingsData, loading: loadMeet } = useApi(
    () => listMeetings({ limit: 5 }), []
  );
  const { data: peopleData, loading: loadPeople } = useApi(
    () => listPeople({ limit: 100 }), []
  );
  const { data: allTasksData, loading: loadTasks } = useApi(
    () => listTasks({ limit: 500 }), []
  );

  const loading = loadDash;


  const now = new Date();
  /* ── Derived: team workload ── */
  const allTasks = allTasksData?.items || allTasksData || [];
  const team = (peopleData?.items || peopleData || []).filter((p) => p.include_in_team_workload);
  const teamRows = useMemo(() => {
    return team
      .map((person) => {
        const personTasks = allTasks.filter(
          (t) =>
            t.assigned_to_person_id === person.id &&
            t.status !== "done" &&
            t.status !== "deferred"
        );
        const overdue = personTasks.filter((t) => t.due_date && new Date(t.due_date) < now);
        return {
          id: person.id,
          name:
            person.full_name ||
            `${person.first_name || ""} ${person.last_name || ""}`.trim(),
          active: personTasks.length,
          overdue: overdue.length,
        };
      })
      .sort((a, b) => b.overdue - a.overdue || b.active - a.active);
  }, [peopleData, allTasksData]);

  if (loading) {
    return (
      <div style={{ padding: "60px 32px", textAlign: "center", color: theme.text.faint }}>
        Loading dashboard\u2026
      </div>
    );
  }

  if (errDash) {
    return (
      <div style={{ padding: "24px 32px" }}>
        <div style={{
          padding: "12px 16px", borderRadius: 8,
          background: "rgba(239,68,68,0.1)", color: theme.accent.red, fontSize: 13,
        }}>
          Error loading dashboard: {errDash.message || String(errDash)}
        </div>
      </div>
    );
  }

  const d = dashData || {};
  const mattersByStatus = d.matters_by_status || {};
  const mattersByPriority = d.matters_by_priority || {};
  const deadlines = d.upcoming_deadlines || [];
  const recentMatters = d.recent_matters || [];
  const recentUpdates = d.recent_updates || [];
  const tasksDue = d.tasks_due_soon || [];
  const pendingDecisions = d.pending_decisions || [];
  const overdueCount = d.overdue_tasks || 0;


  /* ── Derived: immediate attention items ── */
  const overdueTasks = tasksDue.filter((t) => t.due_date && new Date(t.due_date) < now);
  const overdueDecisions = pendingDecisions.filter(
    (pd) => pd.decision_due_date && new Date(pd.decision_due_date) < now
  );
  const immediateItems = [
    ...overdueTasks.map((t) => ({
      type: "task", label: "Overdue Task",
      title: t.title, matter: t.matter_title,
      owner: t.owner_name, overdue: overdueLabel(t.due_date),
      onClick: () => t.matter_id && navigate(`/matters/${t.matter_id}`),
    })),
    ...overdueDecisions.map((pd) => ({
      type: "decision", label: "Overdue Decision",
      title: pd.title, matter: pd.matter_title,
      owner: pd.owner_name, overdue: overdueLabel(pd.decision_due_date),
      onClick: () => pd.matter_id && navigate(`/matters/${pd.matter_id}`),
    })),
  ];

  /* ── Derived: critical matters ── */
  const criticalMatters = recentMatters
    .filter((m) => {
      const p = (m.priority || "").toLowerCase();
      return p === "critical" || p === "critical this week" || p === "high";
    })
    .slice(0, 5);

  /* ── Derived: meetings ── */
  const meetings = (meetingsData?.items || meetingsData || []).slice(0, 5);

  /* ── Derived: bottlenecks ── */
  const awaitingDecisionCount = mattersByStatus["awaiting decision"] || mattersByStatus["awaiting comments"] || 0;
  const waitingTasks = tasksDue.filter((t) => (t.status || "").toLowerCase() === "waiting on others");

  /* ── Derived: deadlines this week ── */
  const deadlinesThisWeek = deadlines.filter((dl) => {
    const date = dl.deadline || dl.external_deadline || dl.decision_deadline || dl.work_deadline;
    return date && daysUntil(date) >= 0 && daysUntil(date) <= 7;
  });

  /* ── Derived: urgent deadlines (within 3 days) for GC brief ── */
  const urgentDeadlineCount = deadlinesThisWeek.filter((dl) => {
    const date = dl.deadline || dl.external_deadline || dl.decision_deadline || dl.work_deadline;
    return daysUntil(date) <= 3;
  }).length;


  return (
    <div style={{ padding: "24px 32px", maxWidth: 1200 }}>
      <div style={titleStyle}>Operations Command</div>
      <div style={subtitleStyle}>
        CFTC Regulatory Ops Tracker &mdash; management dashboard
      </div>

      {/* ── Row 1: Stat cards ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <StatCard
          value={d.total_open_matters ?? 0}
          label="Open Matters"
          accent={theme.accent.blue}
        />
        <StatCard
          value={d.total_open_tasks ?? 0}
          label="Open Tasks"
          accent={theme.accent.teal}
        />
        <StatCard
          value={overdueCount}
          label="Overdue Tasks"
          accent={overdueCount > 0 ? theme.accent.red : theme.text.faint}
          pulse={overdueCount > 0}
        />
        <StatCard
          value={pendingDecisions.length}
          label="Pending Decisions"
          accent={theme.accent.purple}
        />
      </div>

      {/* ── Row 2: Immediate Attention ── */}
      {immediateItems.length > 0 && (
        <SectionCard
          title="Immediate Attention"
          borderColor="#f59e0b"
          style={{ marginBottom: 24 }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Type", "Title", "Matter", "Owner", "Status"].map((h) => (
                  <th key={h} style={thStyle}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {immediateItems.map((item, i) => (
                <HoverRow key={i} onClick={item.onClick}>
                  <td style={tdStyle}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 3,
                        background:
                          item.type === "task"
                            ? "rgba(245,158,11,0.15)"
                            : "rgba(239,68,68,0.15)",
                        color:
                          item.type === "task"
                            ? theme.accent.yellow
                            : theme.accent.red,
                      }}
                    >
                      {item.label}
                    </span>
                  </td>
                  <td style={tdStyle}>{item.title || "\u2014"}</td>
                  <td style={{ ...tdStyle, color: theme.text.muted }}>
                    {item.matter || "\u2014"}
                  </td>
                  <td style={{ ...tdStyle, color: theme.text.muted }}>
                    {item.owner || "\u2014"}
                  </td>
                  <td
                    style={{
                      ...tdStyle,
                      color: theme.accent.red,
                      fontWeight: 600,
                      fontSize: 12,
                    }}
                  >
                    {item.overdue}
                  </td>
                </HoverRow>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* ── Row 3: Critical Matters + Meetings ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <SectionCard title="Critical Matters" borderColor="#ef4444">
          {criticalMatters.length === 0 ? (
            <EmptyState text="No critical or high-priority matters" />
          ) : (
            criticalMatters.map((m, i) => {
              const pr =
                theme.priority[(m.priority || "").toLowerCase()] || {};
              const st =
                theme.status[(m.status || "").toLowerCase()] || {};
              return (
                <div
                  key={m.id || i}
                  onClick={() => m.id && navigate(`/matters/${m.id}`)}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = theme.bg.cardHover)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 4px",
                    borderBottom: `1px solid ${theme.border.subtle}`,
                    cursor: "pointer",
                    borderRadius: 4,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        color: theme.text.secondary,
                        fontWeight: 500,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {m.title}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: theme.text.faint,
                        marginTop: 2,
                      }}
                    >
                      {m.matter_number || ""}
                      {m.owner_name ? ` \u00b7 ${m.owner_name}` : ""}
                    </div>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      flexShrink: 0,
                      marginLeft: 8,
                    }}
                  >
                    {pr.bg && (
                      <Badge
                        bg={pr.bg}
                        text={pr.text}
                        label={pr.label || m.priority}
                      />
                    )}
                    {st.bg && (
                      <Badge
                        bg={st.bg}
                        text={st.text}
                        label={st.label || m.status}
                      />
                    )}
                  </div>
                </div>
              );
            })
          )}
        </SectionCard>

        <SectionCard title="Upcoming Meetings" borderColor={theme.accent.purple}>
          {loadMeet ? (
            <EmptyState text="Loading meetings\u2026" />
          ) : meetings.length === 0 ? (
            <EmptyState text="No upcoming meetings" />
          ) : (
            meetings.map((m, i) => (
              <div
                key={m.id || i}
                onClick={() => m.id && navigate(`/meetings/${m.id}`)}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = theme.bg.cardHover)
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
                style={{
                  padding: "10px 4px",
                  borderBottom: `1px solid ${theme.border.subtle}`,
                  cursor: "pointer",
                  borderRadius: 4,
                }}
              >
                <div
                  style={{
                    fontSize: 13,
                    color: theme.text.secondary,
                    fontWeight: 500,
                  }}
                >
                  {m.title || "Meeting"}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: theme.text.faint,
                    marginTop: 2,
                  }}
                >
                  {formatDateTime(m.date_time_start || m.date_start)}
                  {m.meeting_type ? ` \u00b7 ${m.meeting_type}` : ""}
                </div>
              </div>
            ))
          )}
        </SectionCard>
      </div>

      {/* ── Row 4: Bottlenecks + Deadlines This Week ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <SectionCard title="Bottlenecks" borderColor="#f97316">
          {awaitingDecisionCount === 0 && waitingTasks.length === 0 ? (
            <EmptyState text="No bottlenecks detected" />
          ) : (
            <>
              {awaitingDecisionCount > 0 && (
                <div
                  style={{
                    padding: "8px 0",
                    borderBottom: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  <div style={{ fontSize: 13, color: theme.text.secondary }}>
                    <span
                      style={{
                        fontWeight: 700,
                        color: theme.accent.yellow,
                      }}
                    >
                      {awaitingDecisionCount}
                    </span>{" "}
                    matter
                    {awaitingDecisionCount !== 1 ? "s" : ""} awaiting
                    decisions/comments
                  </div>
                </div>
              )}
              {waitingTasks.length > 0 && (
                <div
                  style={{
                    padding: "8px 0",
                    borderBottom: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      color: theme.text.secondary,
                      marginBottom: 8,
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 700,
                        color: theme.accent.yellow,
                      }}
                    >
                      {waitingTasks.length}
                    </span>{" "}
                    task{waitingTasks.length !== 1 ? "s" : ""} waiting on others
                  </div>
                  {waitingTasks.slice(0, 4).map((t, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 12,
                        color: theme.text.muted,
                        padding: "3px 0",
                      }}
                    >
                      &bull; {t.title}
                      {t.owner_name ? ` (${t.owner_name})` : ""}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </SectionCard>

        <SectionCard title="Deadlines This Week" borderColor={theme.accent.blue}>
          {deadlinesThisWeek.length === 0 ? (
            <EmptyState text="No deadlines in the next 7 days" />
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Matter", "Deadline", ""].map((h) => (
                    <th key={h} style={thStyle}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {deadlinesThisWeek.slice(0, 8).map((dl, i) => {
                  const date =
                    dl.deadline ||
                    dl.external_deadline ||
                    dl.decision_deadline ||
                    dl.work_deadline;
                  const days = daysUntil(date);
                  const urgent = days <= 2;
                  return (
                    <HoverRow
                      key={i}
                      onClick={() =>
                        dl.matter_id && navigate(`/matters/${dl.matter_id}`)
                      }
                    >
                      <td style={tdStyle}>
                        <div
                          style={{
                            fontSize: 13,
                            color: theme.text.secondary,
                          }}
                        >
                          {dl.matter_title || dl.title || "\u2014"}
                        </div>
                        {dl.type && (
                          <div
                            style={{
                              fontSize: 11,
                              color: theme.text.faint,
                            }}
                          >
                            {dl.type}
                          </div>
                        )}
                      </td>
                      <td
                        style={{
                          ...tdStyle,
                          color: urgent
                            ? theme.accent.red
                            : theme.text.muted,
                          fontWeight: urgent ? 600 : 400,
                        }}
                      >
                        {formatDate(date)}
                      </td>
                      <td
                        style={{
                          ...tdStyle,
                          fontSize: 11,
                          color: urgent
                            ? theme.accent.red
                            : theme.accent.yellow,
                          fontWeight: 500,
                        }}
                      >
                        {dueLabel(date)}
                      </td>
                    </HoverRow>
                  );
                })}
              </tbody>
            </table>
          )}
        </SectionCard>
      </div>

      {/* ── Row 5: General Counsel Brief ── */}
      <SectionCard
        title="General Counsel Brief"
        borderColor="#3b82f6"
        style={{ marginBottom: 24 }}
      >
        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}
        >
          {/* Left: priority summary + escalated */}
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: theme.text.muted,
                marginBottom: 10,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Portfolio Summary
            </div>
            <div
              style={{
                display: "flex",
                gap: 12,
                marginBottom: 16,
                flexWrap: "wrap",
              }}
            >
              {Object.entries(mattersByPriority).map(([key, val]) => {
                const pr = theme.priority[key.toLowerCase()] || {};
                return (
                  <div
                    key={key}
                    style={{
                      background: pr.bg || theme.bg.input,
                      padding: "8px 14px",
                      borderRadius: 6,
                      textAlign: "center",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 20,
                        fontWeight: 700,
                        color: pr.text || theme.text.secondary,
                      }}
                    >
                      {val}
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: theme.text.faint,
                        marginTop: 2,
                      }}
                    >
                      {pr.label || key}
                    </div>
                  </div>
                );
              })}
            </div>
            {(mattersByStatus["escalated"] || 0) > 0 && (
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: 6,
                  background: "rgba(239,68,68,0.08)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  fontSize: 13,
                  color: theme.accent.red,
                  fontWeight: 500,
                }}
              >
                {mattersByStatus["escalated"]} escalated matter
                {mattersByStatus["escalated"] !== 1 ? "s" : ""} require
                leadership attention
              </div>
            )}
            {pendingDecisions.length > 0 && (
              <div
                style={{
                  marginTop: 10,
                  padding: "8px 12px",
                  borderRadius: 6,
                  background: "rgba(167,139,250,0.08)",
                  border: "1px solid rgba(167,139,250,0.2)",
                  fontSize: 13,
                  color: theme.accent.purple,
                  fontWeight: 500,
                }}
              >
                {pendingDecisions.length} decision
                {pendingDecisions.length !== 1 ? "s" : ""} pending
                {overdueDecisions.length > 0 && (
                  <span style={{ color: theme.accent.red }}>
                    {" "}
                    ({overdueDecisions.length} overdue)
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Right: recent significant updates + upcoming deadlines */}
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: theme.text.muted,
                marginBottom: 10,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Recent Significant Updates
            </div>
            {recentUpdates.length === 0 ? (
              <EmptyState text="No recent updates" />
            ) : (
              recentUpdates.slice(0, 3).map((u, i) => (
                <div
                  key={i}
                  style={{
                    padding: "6px 0",
                    borderBottom: `1px solid ${theme.border.subtle}`,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 13,
                        color: theme.text.secondary,
                        fontWeight: 500,
                      }}
                    >
                      {u.matter_title || "Matter"}
                    </span>
                    {u.update_type && (
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          color: theme.accent.blue,
                          background: "rgba(59,130,246,0.12)",
                          padding: "2px 6px",
                          borderRadius: 3,
                          textTransform: "uppercase",
                        }}
                      >
                        {u.update_type}
                      </span>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: theme.text.muted,
                      marginTop: 2,
                      lineHeight: 1.4,
                    }}
                  >
                    {u.summary
                      ? u.summary.length > 100
                        ? u.summary.slice(0, 100) + "\u2026"
                        : u.summary
                      : "\u2014"}
                  </div>
                </div>
              ))
            )}
            {urgentDeadlineCount > 0 && (
              <div style={{ marginTop: 12 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: theme.accent.yellow,
                  }}
                >
                  {"\u26a0"} {urgentDeadlineCount} deadline
                  {urgentDeadlineCount !== 1 ? "s" : ""} within 3 days
                  requiring leadership awareness
                </div>
              </div>
            )}
          </div>
        </div>
      </SectionCard>

      {/* ── Row 6: Team Overview ── */}
      <SectionCard
        title="Team Overview"
        borderColor={theme.accent.teal}
        style={{ marginBottom: 24 }}
      >
        {loadPeople || loadTasks ? (
          <EmptyState text="Loading team data\u2026" />
        ) : teamRows.length === 0 ? (
          <EmptyState text="No team members with workload tracking enabled" />
        ) : (
          <>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Name", "Active Tasks", "Overdue"].map((h) => (
                    <th key={h} style={thStyle}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {teamRows.slice(0, 10).map((row, i) => (
                  <HoverRow
                    key={row.id || i}
                    onClick={() => navigate(`/people/${row.id}`)}
                  >
                    <td style={{ ...tdStyle, fontWeight: 500 }}>{row.name}</td>
                    <td style={tdStyle}>{row.active}</td>
                    <td
                      style={{
                        ...tdStyle,
                        color:
                          row.overdue > 0
                            ? theme.accent.red
                            : theme.text.muted,
                        fontWeight: row.overdue > 0 ? 700 : 400,
                      }}
                    >
                      {row.overdue}
                    </td>
                  </HoverRow>
                ))}
              </tbody>
            </table>
            <div
              onClick={() => navigate("/team-workload")}
              style={{
                marginTop: 12,
                fontSize: 12,
                color: theme.accent.blue,
                cursor: "pointer",
                fontWeight: 500,
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.textDecoration = "underline")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.textDecoration = "none")
              }
            >
              View full team workload &rarr;
            </div>
          </>
        )}
      </SectionCard>

      {/* ── Row 7: Recent Activity ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
        <div style={cardStyle}>
          <div style={sectionTitle}>Recent Matters</div>
          {recentMatters.length === 0 ? (
            <EmptyState text="No recent matters" />
          ) : (
            recentMatters.slice(0, 5).map((m, i) => {
              const st = theme.status[(m.status || "").toLowerCase()] || {
                bg: theme.bg.input,
                text: theme.text.faint,
                label: m.status,
              };
              return (
                <div
                  key={m.id || i}
                  onClick={() => m.id && navigate(`/matters/${m.id}`)}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = theme.bg.cardHover)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 0",
                    borderBottom: `1px solid ${theme.border.subtle}`,
                    cursor: "pointer",
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: 13,
                        color: theme.text.secondary,
                        fontWeight: 500,
                      }}
                    >
                      {m.title}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: theme.text.faint,
                        marginTop: 2,
                      }}
                    >
                      {m.matter_number || "\u2014"}
                    </div>
                  </div>
                  <Badge
                    bg={st.bg}
                    text={st.text}
                    label={st.label || m.status}
                  />
                </div>
              );
            })
          )}
        </div>

        <div style={cardStyle}>
          <div style={sectionTitle}>Recent Updates</div>
          {recentUpdates.length === 0 ? (
            <EmptyState text="No recent updates" />
          ) : (
            recentUpdates.slice(0, 5).map((u, i) => (
              <div
                key={i}
                style={{
                  padding: "10px 0",
                  borderBottom: `1px solid ${theme.border.subtle}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                      color: theme.text.secondary,
                      fontWeight: 500,
                    }}
                  >
                    {u.matter_title || "Matter"}
                  </span>
                  {u.update_type && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: theme.accent.blue,
                        background: "rgba(59,130,246,0.12)",
                        padding: "2px 7px",
                        borderRadius: 3,
                      }}
                    >
                      {u.update_type}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: theme.text.muted,
                    lineHeight: 1.4,
                  }}
                >
                  {u.summary
                    ? u.summary.length > 120
                      ? u.summary.slice(0, 120) + "\u2026"
                      : u.summary
                    : "\u2014"}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: theme.text.faint,
                    marginTop: 3,
                  }}
                >
                  {u.author_name ? `${u.author_name} \u00b7 ` : ""}
                  {formatDate(u.created_at)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
