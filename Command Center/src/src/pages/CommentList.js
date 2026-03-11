import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';

export default function CommentList() {
  const [comments, setComments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const docket = searchParams.get('docket') || '';
  const tier = searchParams.get('tier') || '';
  const sentiment = searchParams.get('sentiment') || '';
  const search = searchParams.get('q') || '';
  const page = parseInt(searchParams.get('page') || '1');

  useEffect(() => {
    setLoading(true);
    const params = { page, page_size: 50 };
    if (docket) params.docket_number = docket;
    if (tier) params.tier = tier;
    if (sentiment) params.sentiment = sentiment.toUpperCase();
    if (search) params.search = search;
    api.getComments(params).then(data => {
      setComments(data.comments || []);
      setTotal(data.total || 0);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [docket, tier, sentiment, search, page]);

  const setFilter = (key, val) => {
    const p = new URLSearchParams(searchParams);
    if (val) p.set(key, val); else p.delete(key);
    p.delete('page');
    setSearchParams(p);
  };

  const tierColor = t => t === 1 ? '#3b82f6' : t === 2 ? '#a78bfa' : '#64748b';
  const sentColor = s => {
    const lower = (s || '').toLowerCase();
    return lower === 'oppose' ? '#ef4444' : lower === 'support' ? '#22c55e' : lower === 'mixed' ? '#f59e0b' : '#64748b';
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 className="page-title">Browse Comments</h2>
          <p className="page-desc">{total} comments{docket ? ` in ${docket}` : ''}</p>
        </div>
        <button onClick={() => navigate('/comments')} style={{
          background: 'none', border: '1px solid #1e293b', color: '#64748b',
          padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)',
        }}>← Back to Dashboard</button>
      </div>

      {/* Filters */}
      <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, padding: 14 }}>
        <input
          type="text"
          placeholder="Search comments..."
          value={search}
          onChange={e => setFilter('q', e.target.value)}
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 6,
            background: '#0f172a', border: '1px solid #1e293b', color: '#e2e8f0',
            fontSize: 13, fontFamily: 'var(--font-sans)',
          }}
        />
        <select value={tier} onChange={e => setFilter('tier', e.target.value)} style={{
          padding: '8px 12px', borderRadius: 6, background: '#0f172a',
          border: '1px solid #1e293b', color: '#e2e8f0', fontSize: 12,
        }}>
          <option value="">All Tiers</option>
          <option value="1">Tier 1</option>
          <option value="2">Tier 2</option>
          <option value="3">Tier 3</option>
        </select>
        <select value={sentiment} onChange={e => setFilter('sentiment', e.target.value)} style={{
          padding: '8px 12px', borderRadius: 6, background: '#0f172a',
          border: '1px solid #1e293b', color: '#e2e8f0', fontSize: 12,
        }}>
          <option value="">All Sentiments</option>
          <option value="OPPOSE">Oppose</option>
          <option value="SUPPORT">Support</option>
          <option value="MIXED">Mixed</option>
          <option value="NEUTRAL">Neutral</option>
        </select>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Commenter</th>
                <th>Organization</th>
                <th>Tier</th>
                <th>Sentiment</th>
                <th>Pages</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {comments.map((c, i) => (
                <tr key={i} onClick={() => navigate(`/comments/detail/${encodeURIComponent(c.document_id || c.id)}`)}>
                  <td style={{ fontWeight: 500, color: '#e2e8f0', maxWidth: 200 }}>
                    {c.commenter_name || 'Anonymous'}
                  </td>
                  <td style={{ color: '#94a3b8', maxWidth: 200 }}>{c.commenter_organization || '—'}</td>
                  <td>
                    {c.tier && (
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: `${tierColor(c.tier)}20`, color: tierColor(c.tier),
                      }}>Tier {c.tier}</span>
                    )}
                  </td>
                  <td>
                    {c.sentiment && (
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: `${sentColor(c.sentiment)}20`, color: sentColor(c.sentiment),
                      }}>{c.sentiment}</span>
                    )}
                  </td>
                  <td style={{ color: '#64748b', fontSize: 12 }}>{c.page_count || '—'}</td>
                  <td style={{ color: '#64748b', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                    {c.submission_date ? new Date(c.submission_date).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          {page > 1 && (
            <button onClick={() => setFilter('page', page - 1)} style={{
              padding: '6px 14px', borderRadius: 6, background: '#1f2937', border: '1px solid #374151',
              color: '#94a3b8', fontSize: 12, cursor: 'pointer',
            }}>← Prev</button>
          )}
          <span style={{ padding: '6px 14px', color: '#64748b', fontSize: 12 }}>
            Page {page} of {Math.ceil(total / 50)}
          </span>
          {page < Math.ceil(total / 50) && (
            <button onClick={() => setFilter('page', page + 1)} style={{
              padding: '6px 14px', borderRadius: 6, background: '#1f2937', border: '1px solid #374151',
              color: '#94a3b8', fontSize: 12, cursor: 'pointer',
            }}>Next →</button>
          )}
        </div>
      )}
    </div>
  );
}
