import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api';

function PipelineSummaryBar() {
  const [kanban, setKanban] = useState(null);

  useEffect(() => {
    api.getKanban('rulemaking').then(setKanban).catch(() => {});
  }, []);

  if (!kanban || !kanban.columns) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mt-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Rulemaking Pipeline</h2>
        <Link to="/pipeline" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
          View full →
        </Link>
      </div>
      <div className="flex gap-2">
        {kanban.columns.map((col) => {
          const total = kanban.total_items || 1;
          const pct = Math.max((col.count / total) * 100, col.count > 0 ? 8 : 3);
          return (
            <Link
              key={col.stage_key}
              to="/pipeline"
              className="rounded-lg border border-gray-100 hover:border-gray-300 p-3 transition-all hover:shadow-sm"
              style={{
                flex: `${pct} 0 0`,
                minWidth: 70,
                borderTop: `3px solid ${col.stage_color || '#6b7280'}`,
              }}
            >
              <div
                className="text-xs font-semibold mb-1 truncate"
                style={{ color: col.stage_color || '#6b7280' }}
              >
                {col.stage_label}
              </div>
              <div className="text-xl font-bold text-gray-900">{col.count}</div>
              <div className="text-xs text-gray-400">
                {col.count === 1 ? 'item' : 'items'}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

const TIER_COLORS = { 1: '#ef4444', 2: '#f59e0b', 3: '#22c55e' };
const SENTIMENT_COLORS = { support: '#22c55e', oppose: '#ef4444', mixed: '#f59e0b', neutral: '#94a3b8' };

function StatCard({ label, value, sub, color, onClick, active }) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl shadow-sm border p-6 ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''} ${active ? 'ring-2 ring-blue-500 border-blue-300' : 'border-gray-200'}`}
    >
      <div className="text-sm font-medium text-gray-500">{label}</div>
      <div className={`text-3xl font-bold mt-1 ${color || 'text-gray-900'}`}>{value}</div>
      {sub && <div className="text-sm text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

function RiskBadge({ risk }) {
  const upper = (risk || '').toUpperCase();
  let cls = 'bg-gray-100 text-gray-600';
  if (upper.includes('HIGH')) cls = 'bg-red-100 text-red-700';
  else if (upper.includes('MEDIUM')) cls = 'bg-amber-100 text-amber-700';
  else if (upper.includes('LOW')) cls = 'bg-green-100 text-green-700';
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded ${cls}`}>{risk}</span>;
}

function TierDetailPanel({ tier, data, docket, onClose }) {
  if (!data) return null;
  const sentimentData = [
    { name: 'Support', value: data.support || 0, color: SENTIMENT_COLORS.support },
    { name: 'Oppose', value: data.oppose || 0, color: SENTIMENT_COLORS.oppose },
    { name: 'Mixed', value: data.mixed || 0, color: SENTIMENT_COLORS.mixed },
    { name: 'Neutral', value: data.neutral || 0, color: SENTIMENT_COLORS.neutral },
  ].filter(s => s.value > 0);

  const tierLabels = { 1: 'Tier 1 (Critical)', 2: 'Tier 2 (Substantive)', 3: 'Tier 3 (Standard)' };
  const borderColors = { 1: 'border-red-200', 2: 'border-amber-200', 3: 'border-green-200' };
  const textColors = { 1: 'text-red-700', 2: 'text-amber-700', 3: 'text-green-700' };
  const linkColors = { 1: 'text-red-600 hover:text-red-800', 2: 'text-amber-600 hover:text-amber-800', 3: 'text-green-600 hover:text-green-800' };

  return (
    <div className={`bg-white rounded-xl shadow-sm border ${borderColors[tier]} p-6 mb-6`}>
      <div className="flex items-center justify-between mb-4">
        <h2 className={`text-lg font-semibold ${textColors[tier]}`}>{tierLabels[tier]} — Breakdown</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-sm">✕ Close</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-2">Sentiment Distribution ({data.total} comments)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={sentimentData} cx="50%" cy="50%" outerRadius={75} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {sentimentData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2 mt-2">
            {sentimentData.map(s => (
              <div key={s.name} className="text-xs">
                <span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ backgroundColor: s.color }} />
                {s.name}: {s.value} ({data.total > 0 ? ((s.value / data.total) * 100).toFixed(1) : 0}%)
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-2">Top Commenters (by length)</h3>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {(data.top_commenters || []).map((c, i) => (
              <Link
                key={i}
                to={`/comments/${c.document_id}`}
                className="flex items-center justify-between text-sm p-2 rounded hover:bg-gray-50"
              >
                <span className="text-gray-800 truncate mr-2">{c.name}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                  c.sentiment === 'OPPOSE' ? 'bg-red-100 text-red-700' :
                  c.sentiment === 'SUPPORT' ? 'bg-green-100 text-green-700' :
                  c.sentiment === 'MIXED' ? 'bg-amber-100 text-amber-700' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  {c.sentiment || '?'}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-gray-100">
        <Link to={`/comments?docket=${docket}&tier=${tier}`} className={`text-sm ${linkColors[tier]} font-medium`}>
          View all {data.total} Tier {tier} comments →
        </Link>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [rules, setRules] = useState([]);
  const [selectedDocket, setSelectedDocket] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tierBreakdown, setTierBreakdown] = useState(null);
  const [activeTier, setActiveTier] = useState(null);
  const [statutory, setStatutory] = useState(null);
  const [statutoryLoading, setStatutoryLoading] = useState(false);
  const [narrative, setNarrative] = useState(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);

  useEffect(() => {
    api.getRules()
      .then(data => {
        const ruleList = data.rules || data || [];
        // Sort by total_comments desc, then by most recent
        ruleList.sort((a, b) => {
          const commentsA = a.total_comments || 0;
          const commentsB = b.total_comments || 0;
          if (commentsB !== commentsA) return commentsB - commentsA;
          const dateA = a.updated_at || a.created_at || '';
          const dateB = b.updated_at || b.created_at || '';
          return dateB.localeCompare(dateA);
        });
        setRules(ruleList);
        // Default to blank — don't auto-select
      })
      .catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedDocket) return;
    setLoading(true);
    setActiveTier(null);
    setStatutory(null);
    setNarrative(null);

    Promise.all([
      api.getStats(selectedDocket),
      api.getTierBreakdown(selectedDocket).catch(() => null),
    ]).then(([statsData, breakdownData]) => {
      setStats(statsData);
      setTierBreakdown(breakdownData);
      setLoading(false);
    }).catch(e => { setError(e.message); setLoading(false); });

    setStatutoryLoading(true);
    api.getStatutoryAnalysis(selectedDocket)
      .then(data => { setStatutory(data); setStatutoryLoading(false); })
      .catch(() => setStatutoryLoading(false));

    setNarrativeLoading(true);
    api.getCommentNarrative(selectedDocket)
      .then(data => { setNarrative(data.narrative); setNarrativeLoading(false); })
      .catch(() => setNarrativeLoading(false));
  }, [selectedDocket]);

  if (error) return <div className="text-red-600 p-4 bg-red-50 rounded-lg">Error: {error}</div>;

  const docketSelector = (
    <div className="mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Comment Analysis Dashboard</h1>
          <p className="text-gray-500 mt-1">Overview of public comment analysis</p>
        </div>
        <div className="flex items-center gap-3">
          {stats && stats.tier1_summarized && (
          <a
            href={`${process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1'}/export/briefing/${selectedDocket}`}
            className="px-4 py-2 bg-cftc-500 text-white rounded-lg text-sm font-medium hover:bg-cftc-600 transition-colors"
            download
          >
            📄 Export Briefing Doc
          </a>
          )}
          {stats && stats.total_comments > 0 && (
          <a
            href={`${process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1'}/export/pdfs/${selectedDocket}`}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg text-sm font-medium hover:bg-gray-700 transition-colors"
            download
          >
            📦 Download All Comments
          </a>
          )}
          <select
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm max-w-md"
            value={selectedDocket}
            onChange={e => setSelectedDocket(e.target.value)}
          >
            <option value="">— Select a docket —</option>
            {rules.map(r => (
              <option key={r.docket_number} value={r.docket_number}>
                {r.docket_number} — {r.title?.substring(0, 50)} ({r.total_comments || 0} comments)
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );

  if (!selectedDocket) return (
    <div>
      {docketSelector}
      <div className="p-8 text-center text-gray-500">
        <p>Choose a docket from the dropdown above to view the analysis dashboard.</p>
      </div>
      <PipelineSummaryBar />
    </div>
  );
  if (loading || !stats) return (
    <div>
      {docketSelector}
      <div className="text-gray-500 p-8 text-center">Loading dashboard...</div>
    </div>
  );

  const tierData = [
    { name: 'Tier 1', value: stats.tier_1_count, color: TIER_COLORS[1] },
    { name: 'Tier 2', value: stats.tier_2_count, color: TIER_COLORS[2] },
    { name: 'Tier 3', value: stats.tier_3_count, color: TIER_COLORS[3] },
  ];

  const sentimentData = [
    { name: 'Support', value: stats.support_count, color: SENTIMENT_COLORS.support },
    { name: 'Oppose', value: stats.oppose_count, color: SENTIMENT_COLORS.oppose },
    { name: 'Mixed', value: stats.mixed_count, color: SENTIMENT_COLORS.mixed },
    { name: 'Neutral', value: stats.neutral_count, color: SENTIMENT_COLORS.neutral },
  ];

  const currentRule = rules.find(r => r.docket_number === selectedDocket);

  return (
    <div>
      {docketSelector}

      {/* Rule title bar */}
      <div className="mb-6 text-sm text-gray-600 bg-white rounded-lg border border-gray-200 px-4 py-3">
        <span className="font-semibold">{selectedDocket}</span>
        {currentRule?.title && (
          <span className="ml-2 text-gray-500">— {currentRule.title}</span>
        )}
      </div>

      {/* Stat Cards — clickable tiers */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <StatCard label="Total Comments" value={stats.total_comments} />
        <StatCard label="Tier 1 (Critical)" value={stats.tier_1_count} color="text-red-600"
          onClick={() => setActiveTier(activeTier === 1 ? null : 1)} active={activeTier === 1} />
        <StatCard label="Tier 2 (Substantive)" value={stats.tier_2_count} color="text-amber-600"
          onClick={() => setActiveTier(activeTier === 2 ? null : 2)} active={activeTier === 2} />
        <StatCard label="Tier 3 (Standard)" value={stats.tier_3_count} color="text-green-600"
          onClick={() => setActiveTier(activeTier === 3 ? null : 3)} active={activeTier === 3} />
        <StatCard label="Form Letters" value={stats.form_letter_count} color="text-purple-600" />
        <StatCard label="Avg Pages" value={stats.avg_page_count?.toFixed(1) || '—'} />
      </div>

      {/* Tier Detail Panel */}
      {activeTier && tierBreakdown && (
        <TierDetailPanel
          tier={activeTier}
          data={tierBreakdown[`tier_${activeTier}`]}
          docket={selectedDocket}
          onClose={() => setActiveTier(null)}
        />
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Tier Distribution</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={tierData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {tierData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Sentiment Breakdown</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={sentimentData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {sentimentData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sentiment Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Sentiment Overview</h2>
        <div className="flex items-center space-x-1 h-10 rounded-lg overflow-hidden">
          {sentimentData.filter(s => s.value > 0).map(s => (
            <div key={s.name} className="h-full flex items-center justify-center text-white text-xs font-semibold"
              style={{ backgroundColor: s.color, width: `${stats.total_comments > 0 ? (s.value / stats.total_comments) * 100 : 0}%` }}>
              {s.value > 20 && `${s.name} ${s.value}`}
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>Oppose: {stats.total_comments > 0 ? ((stats.oppose_count / stats.total_comments) * 100).toFixed(1) : 0}%</span>
          <span>Support: {stats.total_comments > 0 ? ((stats.support_count / stats.total_comments) * 100).toFixed(1) : 0}%</span>
        </div>
      </div>

      {/* Synthesis of Major Comments */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Synthesis of Major Comments</h2>
        <p className="text-xs text-gray-400 mb-4">AI-generated narrative of what the major commenters said</p>

        {narrativeLoading && (
          <div className="text-gray-400 text-sm py-8 text-center">
            <div className="animate-pulse">Generating comment synthesis (this may take a minute)...</div>
          </div>
        )}

        {narrative && (
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed">
            {narrative.split('\n\n').map((para, i) => (
              <p key={i} className="mb-3">{para}</p>
            ))}
          </div>
        )}

        {!narrativeLoading && !narrative && (
          <p className="text-gray-400 text-sm">No narrative available. Requires Tier 1 summaries.</p>
        )}
      </div>

      {/* Statutory Interpretation Disputes */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Statutory Interpretation Disputes</h2>
        <p className="text-xs text-gray-400 mb-4">AI-synthesized from Tier 1 comment analysis</p>

        {statutoryLoading && (
          <div className="text-gray-400 text-sm py-8 text-center">
            <div className="animate-pulse">Generating statutory analysis (this may take a minute on first load)...</div>
          </div>
        )}

        {!statutoryLoading && statutory && statutory.disputes && (
          <>
            {statutory.overview && (
              <div className="mb-6 text-sm text-gray-700 leading-relaxed whitespace-pre-line bg-gray-50 rounded-lg p-4 border border-gray-100">
                {statutory.overview}
              </div>
            )}

            {statutory.disputes.length > 0 && (
              <div className="space-y-4">
                {statutory.disputes.map((d, i) => (
                  <div key={i} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <span className="font-semibold text-gray-900">"{d.disputed_term}"</span>
                        {d.statutory_provision && (
                          <span className="text-xs text-gray-400 ml-2">{d.statutory_provision}</span>
                        )}
                      </div>
                      <RiskBadge risk={d.risk_assessment} />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm mt-3">
                      <div className="bg-blue-50 rounded p-3">
                        <div className="text-xs font-semibold text-blue-700 mb-1">Commission's Position</div>
                        <div className="text-gray-700">{d.commission_position}</div>
                      </div>
                      <div className="bg-red-50 rounded p-3">
                        <div className="text-xs font-semibold text-red-700 mb-1">Challenger's Position</div>
                        <div className="text-gray-700">{d.challenger_position}</div>
                      </div>
                    </div>

                    {d.legal_basis_for_challenge && (
                      <div className="mt-2 text-xs text-gray-600">
                        <span className="font-semibold">Legal basis for challenge:</span> {d.legal_basis_for_challenge}
                      </div>
                    )}
                    {d.legal_basis_for_commission && (
                      <div className="mt-1 text-xs text-gray-600">
                        <span className="font-semibold">Legal basis for Commission:</span> {d.legal_basis_for_commission}
                      </div>
                    )}

                    <div className="mt-2 flex flex-wrap gap-1">
                      {(d.key_commenters_challenging || []).map((name, j) => (
                        <span key={`c-${j}`} className="text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded">{name}</span>
                      ))}
                      {(d.key_commenters_supporting || []).map((name, j) => (
                        <span key={`s-${j}`} className="text-xs bg-green-50 text-green-600 px-1.5 py-0.5 rounded">{name}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {statutory.loper_bright_implications && (
              <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="text-xs font-semibold text-amber-700 mb-1">Post-Chevron / Loper Bright Implications</div>
                <div className="text-sm text-gray-700">{statutory.loper_bright_implications}</div>
              </div>
            )}
          </>
        )}

        {!statutoryLoading && (!statutory || !statutory.disputes) && (
          <div className="text-gray-400 text-sm py-4 text-center">
            No statutory analysis available. Run Tier 1 summarization first.
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">Comments by Tier</h2>
        <Link
          to={`/comments?docket=${selectedDocket}`}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          Browse all {stats.total_comments} comments →
        </Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link to={`/comments?docket=${selectedDocket}&tier=1`}
          className="bg-white rounded-xl shadow-sm border border-red-200 p-6 hover:shadow-md transition-shadow">
          <div className="text-red-600 font-semibold text-lg">{stats.tier_1_count} Tier 1 Comments</div>
          <p className="text-gray-500 text-sm mt-1">Critical comments requiring deep analysis — major orgs, extensive legal arguments</p>
          <span className="text-red-500 text-sm mt-3 inline-block">View Tier 1 →</span>
        </Link>
        <Link to={`/comments?docket=${selectedDocket}&tier=2`}
          className="bg-white rounded-xl shadow-sm border border-amber-200 p-6 hover:shadow-md transition-shadow">
          <div className="text-amber-600 font-semibold text-lg">{stats.tier_2_count} Tier 2 Comments</div>
          <p className="text-gray-500 text-sm mt-1">Substantive comments with technical detail from smaller orgs and individuals</p>
          <span className="text-amber-500 text-sm mt-3 inline-block">View Tier 2 →</span>
        </Link>
        <Link to={`/comments?docket=${selectedDocket}&tier=3`}
          className="bg-white rounded-xl shadow-sm border border-green-200 p-6 hover:shadow-md transition-shadow">
          <div className="text-green-600 font-semibold text-lg">{stats.tier_3_count} Tier 3 Comments</div>
          <p className="text-gray-500 text-sm mt-1">Standard comments — form letters, brief support/oppose statements</p>
          <span className="text-green-500 text-sm mt-3 inline-block">View Tier 3 →</span>
        </Link>
      </div>

      <PipelineSummaryBar />
    </div>
  );
}
