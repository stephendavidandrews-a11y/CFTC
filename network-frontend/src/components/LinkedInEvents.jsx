import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getLinkedInEvents, dismissLinkedInEvent, triggerLinkedInScan } from '../api';

const SIGNIFICANCE_ORDER = ['high', 'medium', 'low'];

const SIGNIFICANCE_STYLES = {
  high: {
    borderLeft: '4px solid #dc2626',
    label: { background: 'rgba(220, 38, 38, 0.15)', color: '#dc2626', border: '1px solid rgba(220, 38, 38, 0.3)' },
  },
  medium: {
    borderLeft: '4px solid #f59e0b',
    label: { background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.3)' },
  },
  low: {
    borderLeft: '4px solid #6b7280',
    label: { background: 'rgba(107, 114, 128, 0.15)', color: '#6b7280', border: '1px solid rgba(107, 114, 128, 0.3)' },
  },
};

const EVENT_TYPE_COLORS = {
  job_change: '#3b82f6',
  promotion: '#10b981',
  new_role: '#8b5cf6',
  anniversary: '#f59e0b',
  birthday: '#ec4899',
  post: '#93c5fd',
  article: '#6ee7b7',
  achievement: '#a78bfa',
  education: '#06b6d4',
  certification: '#f97316',
};

function formatEventType(type) {
  if (!type) return '';
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function LinkedInEvents() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [scanResult, setScanResult] = useState(null);

  useEffect(() => {
    loadEvents();
  }, []);

  async function loadEvents() {
    setLoading(true);
    setError(null);
    try {
      const data = await getLinkedInEvents();
      const eventList = Array.isArray(data) ? data : (data.events || data.items || []);
      setEvents(eventList);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleScan() {
    setScanning(true);
    setScanResult(null);
    setError(null);
    try {
      const result = await triggerLinkedInScan();
      setScanResult(result);
      await loadEvents();
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  }

  async function handleDismiss(eventId) {
    try {
      await dismissLinkedInEvent(eventId);
      setEvents(prev => prev.filter(e => e.id !== eventId));
    } catch (err) {
      setError(err.message);
    }
  }

  // Separate opportunities from regular events
  const opportunities = events.filter(e => e.is_opportunity || e.opportunity_flag);
  const regularEvents = events.filter(e => !e.is_opportunity && !e.opportunity_flag);

  // Group regular events by significance
  const grouped = {};
  for (const sig of SIGNIFICANCE_ORDER) {
    const items = regularEvents.filter(e =>
      (e.significance || 'low').toLowerCase() === sig
    );
    if (items.length > 0) {
      grouped[sig] = items;
    }
  }

  if (loading) return <div className="loading">Loading LinkedIn events...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>LinkedIn Events</h2>
        <button
          className="btn btn-primary"
          onClick={handleScan}
          disabled={scanning}
        >
          {scanning ? 'Scanning...' : 'Scan LinkedIn'}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {scanResult && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            background: 'rgba(16, 185, 129, 0.05)',
            border: '1px solid rgba(16, 185, 129, 0.2)',
          }}
        >
          <p style={{ color: '#10b981', fontSize: '0.9rem' }}>
            Scan complete. {scanResult.events_found != null
              ? `${scanResult.events_found} new events found.`
              : (scanResult.message || 'Done.')
            }
          </p>
        </div>
      )}

      {scanning && (
        <div className="loading">Scanning LinkedIn profiles for updates...</div>
      )}

      {/* Opportunities section */}
      {opportunities.length > 0 && (
        <div className="dashboard-section">
          <h3 style={{ color: '#f59e0b' }}>Opportunities</h3>
          <div className="card-grid">
            {opportunities.map(event => (
              <EventCard
                key={event.id}
                event={event}
                onDismiss={handleDismiss}
                isOpportunity
              />
            ))}
          </div>
        </div>
      )}

      {/* Grouped by significance */}
      {SIGNIFICANCE_ORDER.map(sig => {
        if (!grouped[sig]) return null;
        return (
          <div key={sig} className="dashboard-section">
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                className="badge"
                style={SIGNIFICANCE_STYLES[sig].label}
              >
                {sig.toUpperCase()}
              </span>
              <span>{sig === 'high' ? 'Priority' : sig === 'medium' ? 'Notable' : 'Informational'}</span>
            </h3>
            <div className="card-grid">
              {grouped[sig].map(event => (
                <EventCard
                  key={event.id}
                  event={event}
                  onDismiss={handleDismiss}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Empty state */}
      {events.length === 0 && !scanning && (
        <div className="card">
          <div className="empty-state" style={{ padding: 24 }}>
            <div className="empty-icon">{'\uD83D\uDD17'}</div>
            <p className="text-muted">No unprocessed LinkedIn events.</p>
            <p className="text-muted" style={{ fontSize: '0.85rem' }}>
              Click "Scan LinkedIn" to check for new updates from your contacts.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function EventCard({ event, onDismiss, isOpportunity = false }) {
  const significance = (event.significance || 'low').toLowerCase();
  const sigStyle = SIGNIFICANCE_STYLES[significance] || SIGNIFICANCE_STYLES.low;
  const typeColor = EVENT_TYPE_COLORS[event.event_type] || '#6b7280';

  return (
    <div
      className="card"
      style={{
        borderLeft: isOpportunity
          ? '4px solid #f59e0b'
          : sigStyle.borderLeft,
      }}
    >
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {event.contact_id ? (
            <Link
              to={`/contacts/${event.contact_id}`}
              className="card-title"
              style={{ color: 'var(--text-primary)' }}
            >
              {event.contact_name || `Contact #${event.contact_id}`}
            </Link>
          ) : (
            <span className="card-title">
              {event.contact_name || 'Unknown Contact'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span
            className="badge"
            style={{
              background: `${typeColor}22`,
              color: typeColor,
              border: `1px solid ${typeColor}44`,
            }}
          >
            {formatEventType(event.event_type)}
          </span>
          {isOpportunity && (
            <span
              className="badge"
              style={{
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#f59e0b',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              Opportunity
            </span>
          )}
        </div>
      </div>

      <div className="card-body">
        {event.description && (
          <p style={{ marginBottom: 8 }}>{event.description}</p>
        )}
        {event.outreach_hook && (
          <div style={{
            background: 'rgba(30, 64, 175, 0.1)',
            border: '1px solid rgba(30, 64, 175, 0.2)',
            borderRadius: 6,
            padding: '8px 12px',
            marginTop: 8,
          }}>
            <span style={{
              fontSize: '0.7rem',
              color: 'var(--accent-blue-light)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              Outreach Hook
            </span>
            <p style={{
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              marginTop: 2,
            }}>
              {event.outreach_hook}
            </p>
          </div>
        )}
      </div>

      <div className="card-footer">
        {event.detected_at && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {new Date(event.detected_at).toLocaleDateString()}
          </span>
        )}
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => onDismiss(event.id)}
          style={{ color: 'var(--text-muted)' }}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
