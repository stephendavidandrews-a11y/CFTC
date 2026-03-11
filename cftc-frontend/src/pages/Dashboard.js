import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { api } from '../api';

/* ─── Theme constants (from command-center-dark.jsx) ─── */
const T = {
  bg: { app: '#0a0f1a', card: '#111827', hover: '#0f172a' },
  border: { default: '#1f2937', subtle: '#1e293b' },
  text: { primary: '#f1f5f9', secondary: '#e2e8f0', muted: '#94a3b8', dim: '#64748b', faint: '#475569' },
  accent: { blue: '#3b82f6', blueLight: '#60a5fa', purple: '#a78bfa', green: '#22c55e', yellow: '#f59e0b', red: '#ef4444', redLight: '#f87171' },
  font: { mono: "ui-monospace, SFMono-Regular, 'Cascadia Code', Consolas, monospace" },
  feed: {
    tweet: { accent: '#1d9bf0', bg: 'rgba(29,155,240,0.08)' },
    news: { accent: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
    fr: { accent: '#a78bfa', bg: 'rgba(167,139,250,0.08)' },
    regulatory: { accent: '#34d399', bg: 'rgba(52,211,153,0.08)' },
    system: { accent: '#60a5fa', bg: 'rgba(59,130,246,0.08)' },
  },
};

const CHART_TOOLTIP = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 12, color: '#e2e8f0' },
  itemStyle: { color: '#e2e8f0' },
};

/* ─── Pulse ─── */
function Pulse({ color }) {
  return (
    <span style={{ position: 'relative', display: 'inline-flex', width: 8, height: 8 }}>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%', background: color,
        opacity: 0.4, animation: 'pulse-glow 2s ease-in-out infinite',
      }} />
      <span style={{ position: 'relative', width: 8, height: 8, borderRadius: '50%', background: color }} />
      <style>{`@keyframes pulse-glow { 0%, 100% { transform: scale(1); opacity: 0.4; } 50% { transform: scale(2.2); opacity: 0; } }`}</style>
    </span>
  );
}

/* ─── StatCard (dark, left accent bar) ─── */
function StatCard({ value, label, accent, pulse }) {
  return (
    <div style={{
      background: T.bg.card, borderRadius: 10, padding: '20px 24px',
      border: `1px solid ${T.border.default}`, position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: 3, height: '100%', background: accent || T.accent.blue }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: T.text.primary, letterSpacing: '-0.03em' }}>{value}</div>
        {pulse && <Pulse color={accent || T.accent.blue} />}
      </div>
      <div style={{ fontSize: 12, color: T.text.dim, marginTop: 4, fontWeight: 500 }}>{label}</div>
    </div>
  );
}

/* ─── LiveFeed (dark, type-colored) ─── */
function LiveFeed({ items }) {
  const [flash, setFlash] = useState(null);

  useEffect(() => {
    if (!items || items.length === 0) return;
    const interval = setInterval(() => {
      setFlash(0);
      setTimeout(() => setFlash(null), 2000);
    }, 12000);
    return () => clearInterval(interval);
  }, [items]);

  const feedItems = items || [];

  const getFeedColor = (item) => {
    const type = (item.type || item.notification_type || 'system').toLowerCase();
    if (type.includes('tweet') || type.includes('twitter')) return T.feed.tweet;
    if (type.includes('news')) return T.feed.news;
    if (type.includes('fr') || type.includes('federal')) return T.feed.fr;
    if (type.includes('regulatory') || type.includes('rule')) return T.feed.regulatory;
    return T.feed.system;
  };

  return (
    <div style={{
      background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`,
      padding: 20, height: '100%', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Pulse color={T.accent.green} />
        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: 0 }}>Live Intelligence Feed</h3>
        <span style={{ fontSize: 10, color: T.text.faint, marginLeft: 'auto' }}>Auto-updating</span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', maxHeight: 500 }}>
        {feedItems.length === 0 && (
          <div style={{ fontSize: 12, color: T.text.dim, fontStyle: 'italic', padding: '10px 0' }}>
            No recent activity
          </div>
        )}
        {feedItems.map((item, i) => {
          const fc = getFeedColor(item);
          const isFlash = flash === i;
          return (
            <div key={i} style={{
              padding: '12px 14px', marginBottom: 6, borderRadius: 8,
              background: isFlash ? fc.bg : 'transparent',
              borderLeft: `3px solid ${isFlash ? fc.accent : 'transparent'}`,
              transition: 'all 0.5s ease', cursor: 'pointer',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = fc.bg; e.currentTarget.style.borderLeftColor = fc.accent; }}
            onMouseLeave={e => { if (!isFlash) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderLeftColor = 'transparent'; } }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: fc.accent }}>
                  {item.type || item.notification_type || 'Update'}
                </span>
                <span style={{ fontSize: 10, color: T.text.faint, marginLeft: 'auto' }}>
                  {item.timestamp || item.created_at || ''}
                </span>
              </div>
              <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.5 }}>
                {item.description || item.message || item.title}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── NotificationBell ─── */
function NotificationBell({ count, onClick }) {
  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={onClick}
        style={{
          background: 'transparent', border: `1px solid ${T.border.default}`,
          borderRadius: 8, padding: '6px 10px', cursor: 'pointer',
          color: T.text.dim, fontSize: 16, position: 'relative',
        }}
      >
        &#x1F514;
        {count > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -4,
            background: T.accent.red, color: '#fff',
            borderRadius: 10, padding: '1px 5px', fontSize: 9, fontWeight: 700,
            minWidth: 16, textAlign: 'center',
          }}>{count}</span>
        )}
      </button>
    </div>
  );
}

/* ─── PipelineSummaryBar (dark) ─── */
function PipelineSummaryBar({ kanban }) {
  const navigate = useNavigate();
  if (!kanban || !kanban.columns) return null;

  return (
    <div style={{
      background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`,
      padding: '18px 20px', marginTop: 20,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: 0 }}>Rulemaking Pipeline</h3>
        <button
          onClick={() => navigate('/pipeline')}
          style={{
            background: 'transparent', border: 'none', color: T.accent.blueLight,
            fontSize: 12, fontWeight: 600, cursor: 'pointer', padding: 0,
          }}
        >View full &rarr;</button>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {kanban.columns.map((col) => {
          const total = kanban.total_items || 1;
          const pct = Math.max((col.count / total) * 100, col.count > 0 ? 8 : 3);
          return (
            <div
              key={col.stage_key}
              onClick={() => navigate('/pipeline')}
              style={{
                flex: `${pct} 0 0`, minWidth: 60,
                background: T.bg.hover, borderRadius: 8,
                border: `1px solid ${T.border.subtle}`,
                padding: '10px 12px', cursor: 'pointer',
                borderTop: `3px solid ${col.stage_color || '#6b7280'}`,
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = col.stage_color || '#6b7280'}
              onMouseLeave={e => e.currentTarget.style.borderColor = T.border.subtle}
            >
              <div style={{
                fontSize: 10, fontWeight: 600, color: col.stage_color || T.text.faint,
                marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {col.stage_label}
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: T.text.primary }}>{col.count}</div>
              <div style={{ fontSize: 9, color: T.text.faint }}>
                {col.count === 1 ? 'item' : 'items'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main Dashboard ─── */
export default function Dashboard() {
  const navigate = useNavigate();
  const [now, setNow] = useState(new Date());
  const [summary, setSummary] = useState(null);
  const [kanban, setKanban] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(() => {
    Promise.all([
      api.getExecutiveSummary().catch(() => null),
      api.getKanban('rulemaking').catch(() => null),
      api.getMetrics().catch(() => null),
      api.getUnreadCount().catch(() => null),
    ]).then(([s, k, m, u]) => {
      if (s) setSummary(s);
      if (k) setKanban(k);
      if (m) setMetrics(m);
      if (u) setUnreadCount(u?.count ?? u ?? 0);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const s = summary || {
    active_rulemakings: 0, active_reg_actions: 0,
    total_overdue_deadlines: 0, total_stalled_items: 0,
    upcoming_deadlines: [], team_workload: [], recent_activity: [],
  };

  const stageVelocity = metrics?.stage_velocity || [];
  const monthlyThroughput = metrics?.monthly_throughput || [];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', color: T.text.dim, padding: '80px 0' }}>
        <div style={{ fontSize: 18, animation: 'pulse-glow 2s ease-in-out infinite' }}>Loading executive summary...</div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: T.text.primary, margin: 0, letterSpacing: '-0.02em' }}>
            Executive Summary
          </h2>
          <p style={{ fontSize: 13, color: T.text.faint, marginTop: 4 }}>
            Office of General Counsel — Regulation Division
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <NotificationBell count={unreadCount} onClick={() => {}} />
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 13, color: T.text.muted, fontFamily: T.font.mono }}>
              {now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </div>
            <div style={{ fontSize: 20, color: T.text.primary, fontFamily: T.font.mono, fontWeight: 600, letterSpacing: '0.05em' }}>
              {now.toLocaleTimeString('en-US', { hour12: false })}
            </div>
          </div>
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 28 }}>
        <StatCard value={s.active_rulemakings} label="Active Rulemakings" accent={T.accent.purple} />
        <StatCard value={s.total_overdue_deadlines} label="Overdue Deadlines" accent={T.accent.red} pulse={s.total_overdue_deadlines > 0} />
        <StatCard value={s.active_reg_actions} label="Regulatory Actions" accent={T.accent.blue} />
        <StatCard value={s.team_workload?.length || 0} label="Active Attorneys" accent={T.accent.green} />
      </div>

      {/* Charts row */}
      {(stageVelocity.length > 0 || monthlyThroughput.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
          {stageVelocity.length > 0 && (
            <div style={{ background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`, padding: 20 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: '0 0 16px' }}>
                Stage Velocity (avg days)
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stageVelocity}>
                  <XAxis dataKey="stage" tick={{ fill: T.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: T.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <Bar dataKey="avg_days" fill={T.accent.purple} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {monthlyThroughput.length > 0 && (
            <div style={{ background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`, padding: 20 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: '0 0 16px' }}>
                Monthly Throughput
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={monthlyThroughput}>
                  <XAxis dataKey="month" tick={{ fill: T.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: T.text.faint, fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                  <Tooltip {...CHART_TOOLTIP} />
                  <Line type="monotone" dataKey="completed" stroke={T.accent.green} strokeWidth={2} dot={{ fill: T.accent.green, r: 3 }} />
                  <Line type="monotone" dataKey="created" stroke={T.accent.blue} strokeWidth={2} dot={{ fill: T.accent.blue, r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Two-column: Deadlines + Team | Live Feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Upcoming Deadlines */}
          <div style={{ background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: 0 }}>Upcoming Deadlines</h3>
              <span style={{ fontSize: 10, color: T.text.faint }}>Next 90 days</span>
            </div>
            {s.upcoming_deadlines.length === 0 && (
              <div style={{ fontSize: 12, color: T.text.dim, fontStyle: 'italic', padding: '10px 0' }}>
                No upcoming deadlines
              </div>
            )}
            {s.upcoming_deadlines.map((d, i) => {
              const color = d.is_hard_deadline ? T.accent.red : T.accent.yellow;
              return (
                <div
                  key={i}
                  onClick={() => {
                    if (d.item_id) {
                      const path = d.module === 'regulatory_action' ? 'regulatory' : 'pipeline';
                      navigate(`/${path}/${d.item_id}`);
                    }
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0',
                    borderBottom: `1px solid ${T.border.default}`, fontSize: 13,
                    cursor: d.item_id ? 'pointer' : 'default', transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => { if (d.item_id) e.currentTarget.style.background = T.bg.hover; }}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <div style={{ width: 85, color: T.text.dim, fontFamily: T.font.mono, fontSize: 11 }}>{d.due_date}</div>
                  <div style={{ flex: 1, fontWeight: 500, color: T.text.secondary }}>{d.title}</div>
                  <div style={{ fontSize: 11, color: T.text.faint }}>{d.item_title}</div>
                </div>
              );
            })}
          </div>

          {/* Team Workload */}
          <div style={{ background: T.bg.card, borderRadius: 10, border: `1px solid ${T.border.default}`, padding: 20 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, margin: '0 0 14px' }}>Team Workload</h3>
            {(s.team_workload || []).map((t, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '9px 0',
                  borderBottom: `1px solid ${T.border.default}`, fontSize: 13,
                  cursor: 'pointer', transition: 'background 0.1s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = T.bg.hover}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{
                  width: 30, height: 30, borderRadius: '50%',
                  background: `hsl(${i * 40 + 200}, 50%, 25%)`,
                  color: `hsl(${i * 40 + 200}, 70%, 75%)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600, flexShrink: 0,
                }}>
                  {t.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: T.text.secondary, fontSize: 13 }}>{t.name}</div>
                  <div style={{ fontSize: 10, color: T.text.faint }}>{t.role}</div>
                </div>
                <span style={{
                  padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: '#172554', color: T.accent.blueLight,
                }}>{t.active_items}</span>
              </div>
            ))}
            {(!s.team_workload || s.team_workload.length === 0) && (
              <div style={{ fontSize: 12, color: T.text.dim, fontStyle: 'italic', padding: '10px 0' }}>
                No team data available
              </div>
            )}
          </div>
        </div>

        {/* Live Feed */}
        <LiveFeed items={s.recent_activity.length > 0 ? s.recent_activity : undefined} />
      </div>

      {/* Pipeline Summary Bar */}
      <PipelineSummaryBar kanban={kanban} />
    </div>
  );
}
