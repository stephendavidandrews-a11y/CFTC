import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getHappyHour, updateAttendee } from '../api';
import { getDomainBadgeClass } from './ContactCard';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

const RSVP_OPTIONS = ['Invited', 'Confirmed', 'Declined', 'Attended', 'No-show'];

export default function HappyHourDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [happyHour, setHappyHour] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadHappyHour();
  }, [id]);

  async function loadHappyHour() {
    setLoading(true);
    setError(null);
    try {
      const data = await getHappyHour(id);
      setHappyHour(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRsvpChange(contactId, newRsvp) {
    try {
      await updateAttendee(id, contactId, { rsvp_status: newRsvp });
      loadHappyHour();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleBroughtGuestToggle(contactId, currentVal) {
    try {
      await updateAttendee(id, contactId, { brought_guest: !currentVal });
      loadHappyHour();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <div className="loading">Loading happy hour...</div>;
  if (error) return <div className="error-msg">{error}</div>;
  if (!happyHour) return <div className="error-msg">Happy hour not found</div>;

  const attendees = happyHour.attendees || [];

  return (
    <div className="detail-page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/happy-hours')}>
            {'\u2190'} Back
          </button>
          <h2>{happyHour.theme || 'Happy Hour'}</h2>
        </div>
        <Link to={`/happy-hours/${id}/edit`} className="btn btn-secondary btn-sm">Edit</Link>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="detail-grid">
          <div className="detail-field">
            <div className="field-label">Date</div>
            <div className="field-value">{formatDate(happyHour.date)}</div>
          </div>
          {happyHour.venue_name && (
            <div className="detail-field">
              <div className="field-label">Venue</div>
              <div className="field-value">{happyHour.venue_name}</div>
            </div>
          )}
          {happyHour.theme && (
            <div className="detail-field">
              <div className="field-label">Theme</div>
              <div className="field-value">{happyHour.theme}</div>
            </div>
          )}
          {happyHour.notes && (
            <div className="detail-field">
              <div className="field-label">Notes</div>
              <div className="field-value">{happyHour.notes}</div>
            </div>
          )}
        </div>
      </div>

      <div className="detail-section">
        <h3>Attendees ({attendees.length})</h3>

        {attendees.length === 0 ? (
          <div className="empty-state" style={{ padding: 24 }}>
            <p>No attendees added yet</p>
          </div>
        ) : (
          <div className="attendee-list">
            {attendees.map((att) => (
              <div key={att.contact_id || att.id} className="attendee-item">
                <div className="attendee-info">
                  <Link
                    to={`/contacts/${att.contact_id}`}
                    style={{ fontWeight: 600, fontSize: '0.95rem' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {att.contact_name || `${att.first_name || ''} ${att.last_name || ''}`.trim()}
                  </Link>
                  {att.domain && (
                    <span className={`badge ${getDomainBadgeClass(att.domain)}`} style={{ fontSize: '0.65rem' }}>
                      {att.domain}
                    </span>
                  )}
                  {att.brought_guest && (
                    <span
                      style={{ fontSize: '0.75rem', color: 'var(--tier-cornerstone)' }}
                      title="Brought a guest"
                    >
                      +1
                    </span>
                  )}
                </div>
                <div className="attendee-actions">
                  <select
                    className="rsvp-select"
                    value={att.rsvp_status || 'Invited'}
                    onChange={(e) => handleRsvpChange(att.contact_id, e.target.value)}
                  >
                    {RSVP_OPTIONS.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <button
                    className={`btn btn-sm ${att.brought_guest ? 'btn-success' : 'btn-secondary'}`}
                    onClick={() => handleBroughtGuestToggle(att.contact_id, att.brought_guest)}
                    title={att.brought_guest ? 'Brought a guest' : 'Mark as brought guest'}
                  >
                    +1
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
