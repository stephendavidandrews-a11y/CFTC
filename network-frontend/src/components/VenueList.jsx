import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getVenues } from '../api';

export default function VenueList() {
  const [venues, setVenues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadVenues();
  }, []);

  async function loadVenues() {
    setLoading(true);
    setError(null);
    try {
      const data = await getVenues();
      setVenues(Array.isArray(data) ? data : (data.venues || data.items || []));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading venues...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Venues</h2>
        <Link to="/venues/new" className="btn btn-primary">+ Add Venue</Link>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {venues.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">{'\u{1F4CD}'}</div>
          <p>No venues yet</p>
          <Link to="/venues/new" className="btn btn-primary">Add your first venue</Link>
        </div>
      ) : (
        <div className="card-grid">
          {venues.map((venue) => (
            <div
              key={venue.id}
              className="card card-clickable"
              onClick={() => navigate(`/venues/${venue.id}/edit`)}
            >
              <div className="card-header">
                <span className="card-title">{venue.name}</span>
                {venue.price_range && (
                  <span className="text-muted">{venue.price_range}</span>
                )}
              </div>
              <div className="card-body">
                {venue.type && (
                  <div style={{ marginBottom: 6, color: 'var(--text-primary)' }}>
                    {venue.type}
                  </div>
                )}
                <div className="venue-meta">
                  {venue.neighborhood && (
                    <span className="venue-tag">{'\u{1F4CD}'} {venue.neighborhood}</span>
                  )}
                  {venue.vibe && (
                    <span className="venue-tag">{'\u2728'} {venue.vibe}</span>
                  )}
                  {venue.best_for && (
                    <span className="venue-tag">{'\u{1F44D}'} {venue.best_for}</span>
                  )}
                </div>
              </div>
              {venue.notes && (
                <div className="card-footer">
                  <span className="text-secondary">{venue.notes}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
