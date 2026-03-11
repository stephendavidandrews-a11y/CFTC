import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

const ITEM_TYPES = [
  { value: 'NPRM', label: 'NPRM' },
  { value: 'IFR', label: 'Interim Final Rule' },
  { value: 'ANPRM', label: 'Advance NPRM' },
  { value: 'DFR', label: 'Direct Final Rule' },
  { value: 'final_rule', label: 'Final Rule' },
];

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
  { value: 'withdrawn', label: 'Withdrawn' },
];

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

const DEADLINE_COLORS = {
  overdue: 'text-red-600 font-semibold',
  critical: 'text-red-500 font-medium',
  warning: 'text-amber-500',
  normal: 'text-gray-500',
};

function KanbanCard({ item, accentColor }) {
  const severity = item.deadline_severity;
  return (
    <Link
      to={`/pipeline/${item.id}`}
      className="block bg-white rounded-lg border border-gray-200 p-3.5 mb-2 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer"
    >
      <div className="font-semibold text-sm text-gray-800 mb-1">
        {item.short_title || item.title}
      </div>
      {item.docket_number && (
        <div className="text-xs text-gray-400 font-mono">{item.docket_number}</div>
      )}
      <div className="flex gap-1.5 mt-2 flex-wrap">
        {item.priority_label && item.priority_label !== 'medium' && (
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${PRIORITY_COLORS[item.priority_label] || 'bg-gray-100 text-gray-500'}`}>
            {item.priority_label}
          </span>
        )}
        {item.lead_attorney_name && (
          <span className="text-xs text-gray-400">
            {item.lead_attorney_name.split(' ').map(n => n[0]).join('')}
          </span>
        )}
        {item.chairman_priority && (
          <span className="text-xs text-amber-500 font-semibold">CHAIR</span>
        )}
      </div>
      {item.next_deadline_date && (
        <div className={`text-xs mt-1.5 ${DEADLINE_COLORS[severity] || 'text-gray-400'}`}>
          {severity === 'overdue' ? 'OVERDUE' : `Due ${item.next_deadline_date}`}
        </div>
      )}
    </Link>
  );
}

function KanbanView({ kanban }) {
  if (!kanban || !kanban.columns) return null;
  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {kanban.columns.map((col) => (
        <div key={col.stage_key} className="flex-1 min-w-[220px]">
          <div className="flex items-center gap-2 mb-3 pb-2.5" style={{ borderBottom: `2px solid ${col.stage_color || '#6b7280'}` }}>
            <span className="font-bold text-xs" style={{ color: col.stage_color || '#9ca3af' }}>
              {col.stage_label}
            </span>
            <span
              className="rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold"
              style={{
                background: `${col.stage_color || '#6b7280'}20`,
                color: col.stage_color || '#9ca3af',
              }}
            >
              {col.count}
            </span>
          </div>
          {col.items.map((item) => (
            <KanbanCard key={item.id} item={item} accentColor={col.stage_color} />
          ))}
          {col.count === 0 && (
            <div className="p-5 text-center text-xs text-gray-300 italic">No items</div>
          )}
        </div>
      ))}
    </div>
  );
}

function TableView({ items }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Title</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Docket</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Type</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Status</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Priority</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Stage</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs">Lead</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const typeLabel = ITEM_TYPES.find(t => t.value === item.item_type)?.label || item.item_type || '—';
            return (
              <tr key={item.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <Link to={`/pipeline/${item.id}`} className="text-gray-800 font-medium hover:text-blue-600">
                    {item.title}
                  </Link>
                  {item.chairman_priority && (
                    <span className="ml-2 text-xs text-amber-500 font-semibold">CHAIR</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{item.docket_number || '—'}</td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">{typeLabel}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLORS[item.status] || 'bg-gray-100 text-gray-500'}`}>
                    {item.status || '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${PRIORITY_COLORS[item.priority_label] || 'bg-gray-100 text-gray-500'}`}>
                    {item.priority_label || '—'}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">{item.current_stage || '—'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{item.lead_attorney_name || '—'}</td>
              </tr>
            );
          })}
          {items.length === 0 && (
            <tr>
              <td colSpan="7" className="px-4 py-12 text-center text-gray-400">No items found</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function PipelinePage() {
  const [kanban, setKanban] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('kanban');
  const [itemType, setItemType] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getKanban('rulemaking', itemType || null),
      api.listPipelineItems({ module: 'rulemaking', status: statusFilter || undefined, page_size: 500 }),
    ]).then(([kanbanData, itemsData]) => {
      setKanban(kanbanData);
      setItems(itemsData?.items || itemsData || []);
      setLoading(false);
    }).catch(e => {
      setError(e.message);
      setLoading(false);
    });
  }, [itemType, statusFilter]);

  const filteredItems = useMemo(() => {
    let result = items;
    if (itemType) {
      result = result.filter(it => it.item_type === itemType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(it =>
        (it.title || '').toLowerCase().includes(q) ||
        (it.docket_number || '').toLowerCase().includes(q) ||
        (it.short_title || '').toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, itemType, searchQuery]);

  if (error) {
    return (
      <div className="text-red-600 p-4 bg-red-50 rounded-lg">
        Error loading pipeline: {error}
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rulemaking Pipeline</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {viewMode === 'kanban'
              ? kanban ? `${kanban.total_items} active items` : 'Loading...'
              : `${filteredItems.length} items`}
          </p>
        </div>
        <Link
          to="/command-center/pipeline"
          className="px-4 py-2 bg-cftc-500 text-white rounded-lg text-sm font-medium hover:bg-cftc-600 transition-colors"
        >
          Open in Command Center
        </Link>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search items..."
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:ring-2 focus:ring-blue-500 focus:border-blue-300 outline-none"
        />
        <select
          value={itemType}
          onChange={(e) => setItemType(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm cursor-pointer"
        >
          <option value="">All Types</option>
          {ITEM_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm cursor-pointer"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <div className="ml-auto flex rounded-lg overflow-hidden border border-gray-300">
          {['kanban', 'table'].map((v) => (
            <button
              key={v}
              onClick={() => setViewMode(v)}
              className={`px-4 py-2 text-xs font-semibold capitalize ${
                viewMode === v
                  ? 'bg-cftc-500 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center text-gray-400 py-16">
          <div className="animate-pulse">Loading pipeline...</div>
        </div>
      ) : viewMode === 'kanban' ? (
        <KanbanView kanban={kanban} />
      ) : (
        <TableView items={filteredItems} />
      )}
    </div>
  );
}
