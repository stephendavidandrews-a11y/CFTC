import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import StatCard from "../components/shared/StatCard";
import LiveFeed from "../components/shared/LiveFeed";
import NotificationPanel from "../components/shared/NotificationPanel";
import theme from "../styles/theme";
import { useApi } from "../hooks/useApi";
import { getExecutiveSummary, getKanban, getMetrics, getUnreadCount, listItems } from "../api/pipeline";
import { getWorkDashboard, listProjects } from "../api/work";
import useMediaQuery from "../hooks/useMediaQuery";

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: "#1e293b", border: `1px solid ${theme.border.default}`,
    borderRadius: 6, fontSize: 12, color: theme.text.secondary,
  },
  itemStyle: { color: theme.text.secondary },
};

export default function SummaryPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [now, setNow] = useState(new Date());
  const [showNotifs, setShowNotifs] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const { data: summary, refetch: refetchSummary } = useApi(() => getExecutiveSummary(), []);
  const { data: kanban } = useApi(() => getKanban("rulemaking"), []);
  const { data: metrics, refetch: refetchMetrics } = useApi(() => getMetrics(), []);
  const { data: unreadData, refetch: refetchUnread } = useApi(() => getUnreadCount(), []);
  const { data: workDash, refetch: refetchWork } = useApi(() => getWorkDashboard().catch(() => null), []);
  const { data: workProjects } = useApi(() => listProjects({ status: "active" }).catch(() => []), []);
  const { data: withdrawnResp } = useApi(
    () => listItems({ module: "rulemaking", status: "withdrawn", page_size: 50 }),
    []
  );
  const withdrawnItems = (withdrawnResp?.items || withdrawnResp || []);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetchSummary();
      refetchMetrics();
      refetchUnread();
      refetchWork();
    }, 60000);
    return () => clearInterval(interval);
  }, [refetchSummary, refetchMetrics, refetchUnread, refetchWork]);

  const s = summary || {
    active_rulemakings: 0, active_reg_actions: 0,
    total_overdue_deadlines: 0, total_stalled_items: 0,
    upcoming_deadlines: [], team_workload: [], recent_activity: [],
    unread_notifications: 0,
  };

  const unreadCount = unreadData?.count ?? unreadData ?? s.unread_notifications ?? 0;

  const monthlyThroughput = metrics?.monthly_throughput || [];

  // Work management data
  const wd = workDash || { active_projects_by_type: {}, total_work_items_by_status: {}, overdue_items: 0, blocked_items: 0, upcoming_deadlines: [], task_summary: {} };
  const totalActiveProjects = Object.values(wd.active_projects_by_type).reduce((a, b) => a + b, 0);
  const totalWorkItems = Object.values(wd.total_work_items_by_status).reduce((a, b) => a + b, 0);
  const workInProgress = wd.total_work_items_by_status.in_progress || 0;
  const workCompleted = wd.total_work_items_by_status.completed || 0;
  const tasksTodo = (wd.task_summary.todo || 0) + (wd.task_summary.in_progress || 0);
  const tasksOverdue = wd.task_summary.overdue || 0;

  // Merge pipeline deadlines + work deadlines
  const workDeadlines = (wd.upcoming_deadlines || []).map((d) => ({
    due_date: d.due_date,
    title: d.title,
    item_title: d.project_title || "",
    item_id: d.project_id,
    module: "work",
    is_hard_deadline: false,
  }));
  const allDeadlines = [...(s.upcoming_deadlines || []), ...workDeadlines]
    .sort((a, b) => (a.due_date || "").localeCompare(b.due_date || ""));

  const handleCountChange = useCallback(() => {
    refetchUnread();
  }, [refetchUnread]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: theme.text.primary, margin: 0, letterSpacing: "-0.02em" }}>
            Executive Summary
          </h2>
          <p style={{ fontSize: 13, color: theme.text.faint, marginTop: 4 }}>
            Office of General Counsel — Regulation Division
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {/* Notification bell */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              style={{
                background: "transparent", border: `1px solid ${theme.border.default}`,
                borderRadius: 8, padding: "6px 10px", cursor: "pointer",
                color: theme.text.dim, fontSize: 16, position: "relative",
              }}
            >
              &#x1F514;
              {unreadCount > 0 && (
                <span style={{
                  position: "absolute", top: -4, right: -4,
                  background: theme.accent.red, color: "#fff",
                  borderRadius: 10, padding: "1px 5px", fontSize: 9, fontWeight: 700,
                  minWidth: 16, textAlign: "center",
                }}>{unreadCount}</span>
              )}
            </button>
            <NotificationPanel
              isOpen={showNotifs}
              onClose={() => setShowNotifs(false)}
              onCountChange={handleCountChange}
            />
          </div>

          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 13, color: theme.text.muted, fontFamily: theme.font.mono }}>
              {now.toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </div>
            <div style={{ fontSize: 20, color: theme.text.primary, fontFamily: theme.font.mono, fontWeight: 600, letterSpacing: "0.05em" }}>
              {now.toLocaleTimeString("en-US", { hour12: false })}
            </div>
          </div>
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "repeat(5, 1fr)", gap: 14, marginBottom: 28 }}>
        <StatCard value={s.active_rulemakings} label="Active Rulemakings" accent={theme.accent.purple} />
        <StatCard value={withdrawnItems.length} label="Rules Withdrawn" accent={theme.accent.red} pulse={withdrawnItems.length > 0} />
        <StatCard value={s.total_overdue_deadlines} label="Overdue Deadlines" accent={theme.accent.yellow} pulse={s.total_overdue_deadlines > 0} />
        <StatCard value={s.active_reg_actions} label="Regulatory Actions" accent={theme.accent.blue} />
        <StatCard value={s.team_workload.length} label="Active Attorneys" accent={theme.accent.green} />
      </div>

      {/* Work Management + Monthly Throughput row */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {/* Work Management — project list */}
        <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Active Projects</h3>
            <button
              onClick={() => navigate("/work")}
              style={{ background: "none", border: "none", color: theme.accent.blueLight, fontSize: 11, fontWeight: 600, cursor: "pointer", padding: 0 }}
            >View all &rarr;</button>
          </div>
          {/* Summary stats row */}
          <div style={{ display: "flex", gap: 16, marginBottom: 14, paddingBottom: 12, borderBottom: `1px solid ${theme.border.subtle}` }}>
            <div>
              <span style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary }}>{totalActiveProjects}</span>
              <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: 4 }}>projects</span>
            </div>
            <div>
              <span style={{ fontSize: 18, fontWeight: 700, color: theme.accent.blue }}>{workInProgress}</span>
              <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: 4 }}>in progress</span>
            </div>
            {wd.blocked_items > 0 && (
              <div>
                <span style={{ fontSize: 18, fontWeight: 700, color: theme.accent.red }}>{wd.blocked_items}</span>
                <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: 4 }}>blocked</span>
              </div>
            )}
            {tasksTodo > 0 && (
              <div>
                <span style={{ fontSize: 18, fontWeight: 700, color: theme.accent.yellow }}>{tasksTodo}</span>
                <span style={{ fontSize: 10, color: theme.text.faint, marginLeft: 4 }}>tasks</span>
              </div>
            )}
          </div>
          {/* Project rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {(workProjects || []).slice(0, 8).map((p) => {
              const pctDone = p.progress_total > 0 ? Math.round((p.progress_completed / p.progress_total) * 100) : 0;
              const dl = p.effective_deadline;
              const isOverdue = dl && new Date(dl) < new Date() && p.status !== "completed";
              const priorityColors = {
                critical: { bg: "#450a0a", text: "#f87171" },
                high: { bg: "#422006", text: "#fbbf24" },
                medium: { bg: "#172554", text: "#60a5fa" },
                low: { bg: "#1f2937", text: "#6b7280" },
              };
              const pc = priorityColors[p.priority_label] || priorityColors.medium;
              return (
                <div
                  key={p.id}
                  onClick={() => navigate(`/work/${p.id}`)}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 6px", borderRadius: 6, cursor: "pointer",
                    transition: "background 0.12s",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = theme.bg.cardHover; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  {/* Priority dot */}
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: pc.text, flexShrink: 0 }} />
                  {/* Title */}
                  <span style={{
                    flex: 1, fontSize: 12, fontWeight: 500, color: theme.text.secondary,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{p.short_title || p.title}</span>
                  {/* Progress bar */}
                  {p.progress_total > 0 && (
                    <div style={{ width: 50, height: 4, background: "#1f2937", borderRadius: 2, overflow: "hidden", flexShrink: 0 }}>
                      <div style={{ width: `${pctDone}%`, height: "100%", background: theme.accent.green, borderRadius: 2 }} />
                    </div>
                  )}
                  {/* Deadline */}
                  {dl && (
                    <span style={{
                      fontSize: 10, fontFamily: theme.font.mono,
                      color: isOverdue ? theme.accent.red : theme.text.faint,
                      fontWeight: isOverdue ? 600 : 400, whiteSpace: "nowrap",
                    }}>{dl}</span>
                  )}
                  {/* Priority badge */}
                  <span style={{
                    fontSize: 8, fontWeight: 600, padding: "1px 5px",
                    borderRadius: 3, background: pc.bg, color: pc.text,
                    whiteSpace: "nowrap",
                  }}>{p.priority_label.toUpperCase()}</span>
                </div>
              );
            })}
            {(!workProjects || workProjects.length === 0) && (
              <div style={{ fontSize: 12, color: theme.text.faint, padding: "8px 0", fontStyle: "italic" }}>
                No active projects
              </div>
            )}
          </div>
        </div>

        {/* Monthly throughput line chart */}
        {monthlyThroughput.length > 0 ? (
          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: "0 0 16px" }}>
              Monthly Throughput
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={monthlyThroughput}>
                <XAxis dataKey="month" tick={{ fill: theme.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: theme.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                <Tooltip {...CHART_TOOLTIP_STYLE} />
                <Line type="monotone" dataKey="completed" stroke={theme.accent.green} strokeWidth={2} dot={{ fill: theme.accent.green, r: 3 }} />
                <Line type="monotone" dataKey="created" stroke={theme.accent.blue} strokeWidth={2} dot={{ fill: theme.accent.blue, r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: "0 0 16px" }}>
              Work Items by Status
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(wd.total_work_items_by_status).map(([status, count]) => {
                const pct = totalWorkItems > 0 ? (count / totalWorkItems) * 100 : 0;
                const colors = {
                  not_started: "#6b7280", in_progress: "#3b82f6",
                  in_review: "#a78bfa", blocked: "#ef4444", completed: "#22c55e",
                };
                return (
                  <div key={status} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 11, color: theme.text.dim, width: 80, textTransform: "capitalize" }}>
                      {status.replace("_", " ")}
                    </span>
                    <div style={{ flex: 1, height: 8, background: "#1f2937", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: colors[status] || "#6b7280", borderRadius: 4 }} />
                    </div>
                    <span style={{ fontSize: 11, color: theme.text.faint, width: 28, textAlign: "right" }}>{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 380px", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Upcoming Deadlines — clickable */}
          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Upcoming Deadlines</h3>
              <span style={{ fontSize: 10, color: theme.text.faint }}>Next 14 days</span>
            </div>
            {allDeadlines.length === 0 && (
              <div style={{ fontSize: 12, color: theme.text.dim, fontStyle: "italic", padding: "10px 0" }}>
                No upcoming deadlines
              </div>
            )}
            {allDeadlines.map((d, i) => {
              const isWork = d.module === "work";
              const color = isWork ? theme.accent.blue : (d.is_hard_deadline ? theme.accent.red : theme.accent.yellow);
              return (
                <div
                  key={`${d.module}-${i}`}
                  onClick={() => {
                    if (isWork && d.item_id) {
                      navigate(`/work/${d.item_id}`);
                    } else if (d.item_id) {
                      const path = d.module === "regulatory_action" ? "regulatory" : "pipeline";
                      navigate(`/${path}/${d.item_id}`);
                    }
                  }}
                  style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                    borderBottom: `1px solid ${theme.border.default}`, fontSize: 13,
                    cursor: d.item_id ? "pointer" : "default",
                    transition: "background 0.1s",
                  }}
                >
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
                  <div style={{ width: 85, color: theme.text.dim, fontFamily: theme.font.mono, fontSize: 11 }}>{d.due_date}</div>
                  <div style={{ flex: 1, fontWeight: 500, color: theme.text.secondary }}>{d.title}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {isWork && (
                      <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "#172554", color: theme.accent.blueLight, fontWeight: 600 }}>WORK</span>
                    )}
                    <span style={{ fontSize: 11, color: theme.text.faint }}>{d.item_title}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Team Workload — clickable */}
          <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: "0 0 14px" }}>Team Workload</h3>
            {s.team_workload.map((t, i) => (
              <div
                key={i}
                onClick={() => navigate("/team")}
                style={{
                  display: "flex", alignItems: "center", gap: 12, padding: "9px 0",
                  borderBottom: `1px solid ${theme.border.default}`, fontSize: 13,
                  cursor: "pointer", transition: "background 0.1s",
                }}
              >
                <div style={{
                  width: 30, height: 30, borderRadius: "50%",
                  background: `hsl(${i * 40 + 200}, 50%, 25%)`,
                  color: `hsl(${i * 40 + 200}, 70%, 75%)`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 600, flexShrink: 0,
                }}>
                  {t.name.split(" ").map(n => n[0]).join("")}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: theme.text.secondary, fontSize: 13 }}>{t.name}</div>
                  <div style={{ fontSize: 10, color: theme.text.faint }}>{t.role}</div>
                </div>
                <span style={{
                  padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: "#172554", color: theme.accent.blueLight,
                }}>{t.active_items}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Feed — real data when available */}
        <LiveFeed items={s.recent_activity.length > 0 ? s.recent_activity : undefined} />
      </div>

      {/* Pipeline Summary Bar */}
      {kanban && kanban.columns && (
        <div style={{ background: theme.bg.card, borderRadius: 10, border: `1px solid ${theme.border.default}`, padding: "18px 20px", marginTop: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: theme.text.primary, margin: 0 }}>Rulemaking Pipeline</h3>
            <button
              onClick={() => navigate("/pipeline")}
              style={{
                background: "transparent", border: "none", color: theme.accent.blueLight,
                fontSize: 12, fontWeight: 600, cursor: "pointer", padding: 0,
              }}
            >View full &rarr;</button>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {kanban.columns.map((col) => {
              const total = kanban.total_items || 1;
              const pct = Math.max((col.count / total) * 100, col.count > 0 ? 8 : 3);
              return (
                <div
                  key={col.stage_key}
                  onClick={() => navigate("/pipeline")}
                  style={{
                    flex: `${pct} 0 0`, minWidth: 60,
                    background: theme.bg.cardHover, borderRadius: 8,
                    border: `1px solid ${theme.border.subtle}`,
                    padding: "10px 12px", cursor: "pointer",
                    borderTop: `3px solid ${col.stage_color || "#6b7280"}`,
                    transition: "border-color 0.15s",
                  }}
                >
                  <div style={{ fontSize: 10, fontWeight: 600, color: col.stage_color || theme.text.faint, marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {col.stage_label}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: theme.text.primary }}>
                    {col.count}
                  </div>
                  <div style={{ fontSize: 9, color: theme.text.faint }}>
                    {col.count === 1 ? "item" : "items"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
