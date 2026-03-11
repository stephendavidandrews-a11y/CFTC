import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';

function TierBadge({ tier }) {
  const cls = tier === 1 ? 'tier-1' : tier === 2 ? 'tier-2' : 'tier-3';
  return <span className={`${cls} text-xs font-semibold px-2.5 py-1 rounded-full border`}>Tier {tier}</span>;
}

function SentimentBadge({ sentiment }) {
  if (!sentiment) return null;
  const s = sentiment.toLowerCase();
  const cls = s === 'support' ? 'sentiment-support'
    : s === 'oppose' ? 'sentiment-oppose'
    : s === 'mixed' ? 'sentiment-mixed'
    : 'sentiment-neutral';
  return <span className={`${cls} text-xs font-semibold px-2.5 py-1 rounded-full`}>{sentiment}</span>;
}

function FormLetterBadge() {
  return <span className="bg-purple-100 text-purple-800 text-xs font-semibold px-2.5 py-1 rounded-full">Form Letter</span>;
}

export default function CommentList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [total, setTotal] = useState(0);

  // Filters from URL
  const docket = searchParams.get('docket') || 'CFTC-RELEASE-7512';
  const tier = searchParams.get('tier') || '';
  const sentiment = searchParams.get('sentiment') || '';
  const search = searchParams.get('search') || '';
  const page = parseInt(searchParams.get('page') || '1');
  const perPage = 25;

  const updateParam = (key, value) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    if (key !== 'page') params.set('page', '1');
    setSearchParams(params);
  };

  const fetchComments = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        docket_number: docket,
        skip: (page - 1) * perPage,
        limit: perPage,
      };
      if (tier) params.tier = tier;
      if (sentiment) params.sentiment = sentiment;
      if (search) params.search = search;

      const data = await api.getComments(params);
      setComments(data.comments || data || []);
      setTotal(data.total || (data.comments || data || []).length);
      setLoading(false);
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  }, [docket, tier, sentiment, search, page]);

  useEffect(() => { fetchComments(); }, [fetchComments]);

  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Comments</h1>
        <p className="text-gray-500 mt-1">{total} comments found</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search by commenter name or organization..."
              className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={search}
              onChange={e => updateParam('search', e.target.value)}
              onKeyDown={e => e.key === 'Enter' && fetchComments()}
            />
          </div>

          {/* Tier Filter */}
          <select
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            value={tier}
            onChange={e => updateParam('tier', e.target.value)}
          >
            <option value="">All Tiers</option>
            <option value="1">Tier 1</option>
            <option value="2">Tier 2</option>
            <option value="3">Tier 3</option>
          </select>

          {/* Sentiment Filter */}
          <select
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            value={sentiment}
            onChange={e => updateParam('sentiment', e.target.value)}
          >
            <option value="">All Sentiment</option>
            <option value="SUPPORT">Support</option>
            <option value="OPPOSE">Oppose</option>
            <option value="MIXED">Mixed</option>
            <option value="NEUTRAL">Neutral</option>
          </select>

          {/* Clear */}
          {(tier || sentiment || search) && (
            <button
              onClick={() => setSearchParams({ docket })}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && <div className="text-red-600 p-4 bg-red-50 rounded-lg mb-4">Error: {error}</div>}

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading comments...</div>
        ) : comments.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No comments found matching your filters.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Commenter</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tier</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sentiment</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pages</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Summary</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {comments.map(c => (
                <tr key={c.document_id} className="hover:bg-gray-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/comments/${c.document_id}`} className="text-blue-600 hover:text-blue-800 font-medium text-sm">
                      {c.commenter_name || c.commenter_organization || 'Anonymous'}
                    </Link>
                    {c.commenter_organization && c.commenter_name && (
                      <div className="text-xs text-gray-400">{c.commenter_organization}</div>
                    )}
                    <div className="text-xs text-gray-300">{c.document_id}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <TierBadge tier={c.tier} />
                      {c.is_form_letter && <FormLetterBadge />}
                    </div>
                  </td>
                  <td className="px-4 py-3"><SentimentBadge sentiment={c.sentiment} /></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{c.page_count || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{c.submission_date || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
                    {c.ai_summary ? c.ai_summary.substring(0, 120) + '...' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-gray-500">
            Page {page} of {totalPages} ({total} total)
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => updateParam('page', String(page - 1))}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            {[...Array(Math.min(totalPages, 5))].map((_, i) => {
              const p = page <= 3 ? i + 1 : page + i - 2;
              if (p < 1 || p > totalPages) return null;
              return (
                <button
                  key={p}
                  onClick={() => updateParam('page', String(p))}
                  className={`px-3 py-1.5 text-sm rounded-lg ${
                    p === page ? 'bg-cftc-500 text-white' : 'border border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {p}
                </button>
              );
            })}
            <button
              disabled={page >= totalPages}
              onClick={() => updateParam('page', String(page + 1))}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
