import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getHappyHours } from '../api';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    const futureDays = Math.abs(diffDays);
    if (futureDays === 0) return 'Today';
    if (futureDays === 1) return 'Tomorrow';
    if (futureDays < 7) return `In ${futureDays} days`;
    return `In ${Math.ceil(futureDays / 7)} weeks`;
  }
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return `${Math.floor(diffDays / 30)} months ago`;
}

export default function HappyHourList() {
  const [happyHours, setHappyHours] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadHappyHours();
  }, []);

  async function loadHappyHours() {
    setLoading(true);
    setError(null);
    try {
      const data = await getHappyHours();
      setHappyHours(Array.isArray(data) ? data : (data.happy_hours || data.items || []));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading happy hours...</div>;

  const sorted = [...happyHours].sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );

  return (
    <div>
      <div className="page-header">
        <h2>Happy Hours</h2>
        <Link to="/happy-hours/new" className="btn btn-primary">+ New Happy Hour</Link>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {sorted.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">{'\u{1F37B}'}</div>
          <p>No happy hours yet</p>
          <Link to="/happy-hours/new" className="btn btn-primary">Create your first happy hour</Link>
        </div>
      ) : (
        <div className="card-grid">
          {sorted.map((hh) => (
            <div
              key={hh.id}
              className="card card-clickable"
              onClick={() => navigate(`/happy-hours/${hh.id}`)}
            >
              <div className="card-header">
                <span className="card-title">
                  {hh.theme || 'Happy Hour'}
                </span>
                <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                  {timeAgo(hh.date)}
                </span>
              </div>
              <div className="card-body">
                <div style={{ marginBottom: 6 }}>
                  {'\u{1F4C5}'} {formatDate(hh.date)}
                </div>
                {hh.venue_name && (
                  <div style={{ marginBottom: 6 }}>
                    {'\u{1F4CD}'} {hh.venue_name}
                  </div>
                )}
                {hh.attendee_count != null && (
                  <div className="text-muted">
                    {'\u{1F465}'} {hh.attendee_count} attendee{hh.attendee_count !== 1 ? 's' : ''}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
