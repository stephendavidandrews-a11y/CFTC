import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api';

const STATUS_COLORS = {
  active: 'bg-emerald-100 text-emerald-700',
  paused: 'bg-amber-100 text-amber-700',
  completed: 'bg-blue-100 text-blue-700',
  withdrawn: 'bg-gray-100 text-gray-500',
};

const PRIORITY_COLORS = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-gray-100 text-gray-500',
};

export default function PipelineItemPage() {
  const { id } = useParams();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api.getPipelineItem(id)
      .then(data => { setItem(data); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [id]);

  if (loading) return <div className="text-gray-400 text-center py-16 animate-pulse">Loading item...</div>;
  if (error) return <div className="text-red-600 p-4 bg-red-50 rounded-lg">Error: {error}</div>;
  if (!item) return <div className="text-gray-400 text-center py-16">Item not found</div>;

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
        <Link to="/pipeline" className="hover:text-blue-600">Pipeline</Link>
        <span>/</span>
        <span className="text-gray-600">{item.short_title || item.title}</span>
      </div>

      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{item.title}</h1>
            {item.short_title && item.short_title !== item.title && (
              <p className="text-gray-500 mt-1">{item.short_title}</p>
            )}
            <div className="flex items-center gap-3 mt-3">
              {item.docket_number && (
                <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">{item.docket_number}</span>
              )}
              {item.rin && (
                <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">RIN: {item.rin}</span>
              )}
              {item.fr_citation && (
                <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">{item.fr_citation}</span>
              )}
            </div>
          </div>
          <a
            href={`/command-center/pipeline/${id}`}
            className="px-4 py-2 bg-cftc-500 text-white rounded-lg text-sm font-medium hover:bg-cftc-600 transition-colors"
          >
            Edit in Command Center
          </a>
        </div>
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs font-medium text-gray-400 mb-1">Status</div>
          <span className={`text-sm font-semibold px-2 py-0.5 rounded ${STATUS_COLORS[item.status] || 'bg-gray-100 text-gray-500'}`}>
            {item.status || '—'}
          </span>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs font-medium text-gray-400 mb-1">Priority</div>
          <span className={`text-sm font-semibold px-2 py-0.5 rounded ${PRIORITY_COLORS[item.priority_label] || 'bg-gray-100 text-gray-500'}`}>
            {item.priority_label || '—'}
          </span>
          {item.chairman_priority && (
            <span className="ml-2 text-xs text-amber-500 font-bold">CHAIRMAN PRIORITY</span>
          )}
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs font-medium text-gray-400 mb-1">Current Stage</div>
          <div className="text-sm font-semibold text-gray-900">{item.current_stage || '—'}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="text-xs font-medium text-gray-400 mb-1">Item Type</div>
          <div className="text-sm font-semibold text-gray-900">{item.item_type || '—'}</div>
        </div>
      </div>

      {/* Team & Description */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Team</h2>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Lead Attorney</span>
              <span className="font-medium text-gray-800">{item.lead_attorney_name || '—'}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Backup Attorney</span>
              <span className="font-medium text-gray-800">{item.backup_attorney_name || '—'}</span>
            </div>
          </div>
        </div>
        {item.description && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Description</h2>
            <p className="text-sm text-gray-600 leading-relaxed">{item.description}</p>
          </div>
        )}
      </div>

      {/* Deadlines */}
      {item.deadlines && item.deadlines.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mt-4">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Deadlines</h2>
          <div className="space-y-2">
            {item.deadlines.map((dl, i) => (
              <div key={i} className="flex items-center justify-between text-sm py-2 border-b border-gray-100 last:border-0">
                <span className="font-medium text-gray-800">{dl.title}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gray-500">{dl.due_date}</span>
                  {dl.is_hard_deadline && (
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded font-medium">Hard</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
