import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis } from 'recharts';
import { api } from '../api';

const COLORS_TIER = ['#3b82f6', '#a78bfa', '#64748b'];
const COLORS_SENTIMENT = ['#ef4444', '#22c55e', '#f59e0b', '#64748b'];
const TIER_LABELS = { 1: 'Tier 1 — Institutional', 2: 'Tier 2 — Substantive Individual', 3: 'Tier 3 — General Public' };
const SENT_COLOR = s => {
  const l = (s || '').toLowerCase();
  return l === 'oppose' ? '#ef4444' : l === 'support' ? '#22c55e' : l === 'mixed' ? '#f59e0b' : '#64748b';
};

export default function CommentsDashboard() {
  const [rules, setRules] = useState([]);
  const [selectedDocket, setSelectedDocket] = useState('');
  const [stats, setStats] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [narrativeSavedAt, setNarrativeSavedAt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tierBreakdown, setTierBreakdown] = useState(null);
  const [expandedTier, setExpandedTier] = useState(null);
  const [tierComments, setTierComments] = useState([]);
  const [tierCommentsLoading, setTierCommentsLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getRules().then(data => {
      const r = data.rules || data || [];
      r.sort((a, b) => (b.total_comments || 0) - (a.total_comments || 0));
      setRules(r);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedDocket) { setStats(null); setNarrative(null); setNarrativeSavedAt(null); setTierBreakdown(null); setExpandedTier(null); return; }
    setLoading(true);
    Promise.all([
      api.getStats(selectedDocket),
      api.getNarrative(selectedDocket).catch(() => ({ narrative: null })),
      api.getTierBreakdown(selectedDocket).catch(() => null),
    ]).then(([s, n, tb]) => {
      setStats(s);
      setNarrative(n.narrative);
      setNarrativeSavedAt(n.saved_at || null);
      setTierBreakdown(tb);
    }).finally(() => setLoading(false));
  }, [selectedDocket]);

  // Load comments when a tier is expanded
  useEffect(() => {
    if (!expandedTier || !selectedDocket) { setTierComments([]); return; }
    setTierCommentsLoading(true);
    api.getComments({ docket_number: selectedDocket, tier: expandedTier, page_size: 25 })
      .then(data => setTierComments(data.comments || []))
      .catch(() => setTierComments([]))
      .finally(() => setTierCommentsLoading(false));
  }, [expandedTier, selectedDocket]);

  const tierData = stats ? [
    { name: 'Tier 1', value: stats.tier_1_count || 0, tier: 1 },
    { name: 'Tier 2', value: stats.tier_2_count || 0, tier: 2 },
    { name: 'Tier 3', value: stats.tier_3_count || 0, tier: 3 },
  ] : [];

  const sentimentData = stats ? [
    { name: 'Oppose', value: stats.oppose_count || 0 },
    { name: 'Support', value: stats.support_count || 0 },
    { name: 'Mixed', value: stats.mixed_count || 0 },
    { name: 'Neutral', value: stats.neutral_count || 0 },
  ] : [];

  const handleTierClick = (tier) => {
    setExpandedTier(expandedTier === tier ? null : tier);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 className="page-title">Comment Analyzer</h2>
          <p className="page-desc">AI-powered public comment analysis system</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => navigate('/comments/processing')} style={{
            background: '#1f2937', color: '#94a3b8', border: '1px solid #374151',
            padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>AI Processing</button>
          <button onClick={() => navigate('/comments/new-docket')} style={{
            background: '#14532d', color: '#4ade80', border: '1px solid #166534',
            padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>+ New Docket</button>
        </div>
      </div>

      {/* Docket selector */}
      <div className="card" style={{ marginBottom: 20 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 8 }}>
          Select Docket
        </label>
        <select
          value={selectedDocket}
          onChange={e => setSelectedDocket(e.target.value)}
          style={{
            width: '100%', padding: '10px 14px', borderRadius: 8,
            background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
            fontSize: 13, fontFamily: 'var(--font-sans)', cursor: 'pointer',
          }}
        >
          <option value="">— Select a docket to view analysis —</option>
          {rules.map(r => (
            <option key={r.docket_number} value={r.docket_number}>
              {r.docket_number} — {r.title} ({r.total_comments || 0} comments)
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>Loading analysis...</div>
      )}

      {stats && !loading && (
        <>
          {/* Stats row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
            {[
              { v: stats.total_comments, l: 'Total Comments', c: 'blue' },
              { v: stats.tier_1_count || 0, l: 'Tier 1 (Institutional)', c: 'purple' },
              { v: stats.form_letter_count || 0, l: 'Form Letters', c: 'green' },
              { v: `${stats.oppose_count || 0}/${stats.support_count || 0}`, l: 'Oppose / Support', c: 'red' },
            ].map((s, i) => (
              <div key={i} className={`stat-card ${s.c}`}>
                <div className="stat-value">{s.v}</div>
                <div className="stat-label">{s.l}</div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid-2" style={{ marginBottom: 20 }}>
            <div className="card">
              <div className="card-title" style={{ marginBottom: 16 }}>Comment Tiers</div>
              <div style={{ fontSize: 11, color: '#475569', marginBottom: 8, marginTop: -8 }}>Click a tier to explore</div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={tierData} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                    dataKey="value" style={{ cursor: 'pointer' }}
                    label={({ name, value }) => `${name}: ${value}`}
                    onClick={(_, idx) => handleTierClick(idx + 1)}
                  >
                    {tierData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={COLORS_TIER[i]}
                        stroke={expandedTier === i + 1 ? '#e2e8f0' : 'none'}
                        strokeWidth={expandedTier === i + 1 ? 3 : 0}
                      />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <div className="card-title" style={{ marginBottom: 16 }}>Sentiment</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={sentimentData}>
                  <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {sentimentData.map((_, i) => <Cell key={i} fill={COLORS_SENTIMENT[i]} />)}
                  </Bar>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Tier Breakdown Cards */}
          {tierBreakdown && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 20 }}>
              {[1, 2, 3].map(t => {
                const key = `tier_${t}`;
                const td = tierBreakdown[key];
                if (!td) return null;
                const isExpanded = expandedTier === t;
                return (
                  <div
                    key={t}
                    className="card"
                    onClick={() => handleTierClick(t)}
                    style={{
                      cursor: 'pointer',
                      border: isExpanded ? `2px solid ${COLORS_TIER[t - 1]}` : '1px solid #1e293b',
                      transition: 'border-color 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <span style={{
                        fontSize: 12, fontWeight: 700, color: COLORS_TIER[t - 1],
                        textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>Tier {t}</span>
                      <span style={{ fontSize: 20, fontWeight: 700, color: '#e2e8f0' }}>{td.total}</span>
                    </div>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>{TIER_LABELS[t]}</div>
                    {/* Mini sentiment bars */}
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {[
                        { label: 'Oppose', val: td.oppose, color: '#ef4444' },
                        { label: 'Support', val: td.support, color: '#22c55e' },
                        { label: 'Mixed', val: td.mixed, color: '#f59e0b' },
                        { label: 'Neutral', val: td.neutral, color: '#64748b' },
                      ].filter(x => x.val > 0).map(x => (
                        <span key={x.label} style={{
                          fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                          background: `${x.color}18`, color: x.color,
                        }}>{x.label} {x.val}</span>
                      ))}
                    </div>
                    <div style={{
                      marginTop: 10, fontSize: 11, color: isExpanded ? COLORS_TIER[t - 1] : '#475569',
                      textAlign: 'center',
                    }}>
                      {isExpanded ? '▲ Click to collapse' : '▼ Click to view comments'}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Expanded Tier Comments */}
          {expandedTier && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <div className="card-title" style={{ color: COLORS_TIER[expandedTier - 1] }}>
                    Tier {expandedTier} Comments
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{TIER_LABELS[expandedTier]}</div>
                </div>
                <button
                  onClick={() => navigate(`/comments/browse?docket=${encodeURIComponent(selectedDocket)}&tier=${expandedTier}`)}
                  style={{
                    background: '#172554', color: '#60a5fa', border: '1px solid #1e3a5f',
                    padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  }}
                >View all Tier {expandedTier} →</button>
              </div>

              {tierCommentsLoading ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#64748b', fontSize: 12 }}>Loading comments...</div>
              ) : tierComments.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#475569', fontSize: 12 }}>No comments found</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {tierComments.map((c, i) => (
                    <div
                      key={i}
                      onClick={() => navigate(`/comments/detail/${encodeURIComponent(c.document_id || c.id)}`)}
                      style={{
                        padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
                        background: '#0f172a', border: '1px solid #1e293b',
                        transition: 'border-color 0.15s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.borderColor = '#334155'}
                      onMouseLeave={e => e.currentTarget.style.borderColor = '#1e293b'}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                        <div style={{ flex: 1 }}>
                          <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 13 }}>
                            {c.commenter_organization || c.commenter_name || 'Anonymous'}
                          </span>
                          {c.commenter_organization && c.commenter_name && (
                            <span style={{ color: '#64748b', fontSize: 11, marginLeft: 8 }}>({c.commenter_name})</span>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                          {c.sentiment && (
                            <span style={{
                              padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                              background: `${SENT_COLOR(c.sentiment)}18`, color: SENT_COLOR(c.sentiment),
                            }}>{c.sentiment}</span>
                          )}
                          {c.page_count && (
                            <span style={{ fontSize: 10, color: '#475569' }}>{c.page_count}p</span>
                          )}
                          <span style={{ fontSize: 10, color: '#475569', fontFamily: 'var(--font-mono)' }}>
                            {c.submission_date ? new Date(c.submission_date).toLocaleDateString() : ''}
                          </span>
                        </div>
                      </div>
                      {c.ai_summary && (
                        <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5, marginTop: 4 }}>
                          {c.ai_summary.length > 200 ? c.ai_summary.slice(0, 200) + '...' : c.ai_summary}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Narrative */}
          {narrative && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div className="card-title">AI Narrative Synthesis</div>
                {narrativeSavedAt && (
                  <span style={{ fontSize: 11, color: '#475569' }}>
                    Generated {new Date(narrativeSavedAt).toLocaleDateString()}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{narrative}</div>
            </div>
          )}

          {/* Export buttons */}
          <div className="card" style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <a href={api.exportBriefing(selectedDocket)} target="_blank" rel="noreferrer" style={{
              padding: '10px 20px', borderRadius: 6, background: '#172554', color: '#60a5fa',
              border: '1px solid #1e3a5f', textDecoration: 'none', fontSize: 12, fontWeight: 600,
            }}>Export Briefing Doc</a>
            <a href={api.exportPdfs(selectedDocket)} target="_blank" rel="noreferrer" style={{
              padding: '10px 20px', borderRadius: 6, background: '#1f2937', color: '#94a3b8',
              border: '1px solid #374151', textDecoration: 'none', fontSize: 12, fontWeight: 600,
            }}>Download PDFs</a>
          </div>

          {/* Bottom Navigation Bar */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
              borderTop: '1px solid #1e293b',
            }}>
              {[
                { label: 'All Comments', icon: '\u2261', onClick: () => navigate(`/comments/browse?docket=${encodeURIComponent(selectedDocket)}`) },
                { label: 'Tier 1', icon: '\u2605', count: stats.tier_1_count, color: COLORS_TIER[0],
                  onClick: () => navigate(`/comments/browse?docket=${encodeURIComponent(selectedDocket)}&tier=1`) },
                { label: 'Tier 2', icon: '\u25C6', count: stats.tier_2_count, color: COLORS_TIER[1],
                  onClick: () => navigate(`/comments/browse?docket=${encodeURIComponent(selectedDocket)}&tier=2`) },
                { label: 'Tier 3', icon: '\u25CF', count: stats.tier_3_count, color: COLORS_TIER[2],
                  onClick: () => navigate(`/comments/browse?docket=${encodeURIComponent(selectedDocket)}&tier=3`) },
              ].map((btn, i) => (
                <button
                  key={i}
                  onClick={btn.onClick}
                  style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                    padding: '14px 8px', background: 'transparent', border: 'none',
                    borderRight: i < 3 ? '1px solid #1e293b' : 'none',
                    color: btn.color || '#94a3b8', cursor: 'pointer', fontFamily: 'var(--font-sans)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#1e293b40'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <span style={{ fontSize: 18 }}>{btn.icon}</span>
                  <span style={{ fontSize: 11, fontWeight: 600 }}>{btn.label}</span>
                  {btn.count != null && (
                    <span style={{ fontSize: 10, color: '#475569' }}>{btn.count} comments</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
