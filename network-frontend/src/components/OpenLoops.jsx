import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getOpenLoops, getGoingCold } from '../api';

function timeAgo(dateStr) {
  if (!dateStr) return 'Never';
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return `${Math.floor(diff / 30)} months ago`;
}

export default function OpenLoops() {
  const [loops, setLoops] = useState([]);
  const [coldContacts, setColdContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getOpenLoops(), getGoingCold()])
      .then(([l, c]) => {
        setLoops(l);
        setColdContacts(c);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="loading">Loading open loops...</div>;
  if (error) return <div className="error-msg">{error}</div>;

  const loopsByContact = loops.reduce((acc, loop) => {
    const name = loop.contact_name || `Contact #${loop.contact_id}`;
    const id = loop.contact_id;
    if (!acc[id]) acc[id] = { name, loops: [] };
    acc[id].loops.push(loop);
    return acc;
  }, {});

  const isOverdue = (dateStr) => {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
  };

  return (
    <div>
      <div className="page-header">
        <h2>Open Loops & Follow-ups</h2>
      </div>

      {/* Going Cold Section */}
      {coldContacts.length > 0 && (
        <div className="cold-section">
          <h3>Contacts Going Cold (2+ weeks)</h3>
          {coldContacts.map(c => (
            <div key={c.id} className="cold-contact">
              <div>
                <Link to={`/contacts/${c.id}`} style={{ fontWeight: 600 }}>{c.name}</Link>
                <span className="text-muted" style={{ marginLeft: 8, fontSize: '0.85rem' }}>
                  {c.current_role}
                </span>
                <span style={{ marginLeft: 8 }}>
                  <span className={`badge badge-${c.tier?.toLowerCase()}`}>{c.tier}</span>
                </span>
              </div>
              <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                Last: {timeAgo(c.last_contact_date)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Open Loops */}
      {loops.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#128203;</div>
          <p>No open loops yet.</p>
          <p style={{ fontSize: '0.85rem' }}>
            When you log interactions with open loops, they'll appear here for follow-up tracking.
          </p>
        </div>
      ) : (
        Object.entries(loopsByContact).map(([contactId, { name, loops: contactLoops }]) => (
          <div key={contactId} className="loop-group">
            <h4>
              <Link to={`/contacts/${contactId}`}>{name}</Link>
              <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: 400 }}>
                ({contactLoops.length} open)
              </span>
            </h4>
            {contactLoops.map(loop => (
              <div key={loop.id} className="loop-item" style={isOverdue(loop.follow_up_date) ? { borderColor: 'rgba(220, 38, 38, 0.4)' } : {}}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="loop-date">
                    {loop.type && (
                      <span className={`interaction-dot dot-${loop.type?.toLowerCase().replace(/[\s\/]/g, '-')}`}></span>
                    )}
                    {loop.type} &mdash; {timeAgo(loop.date)}
                  </span>
                  {loop.follow_up_date && (
                    <span className={isOverdue(loop.follow_up_date) ? 'text-danger' : 'loop-followup'} style={{ fontSize: '0.8rem' }}>
                      {isOverdue(loop.follow_up_date) ? 'OVERDUE: ' : 'Follow up: '}
                      {new Date(loop.follow_up_date).toLocaleDateString()}
                    </span>
                  )}
                </div>
                {loop.summary && (
                  <div className="text-muted mt-1" style={{ fontSize: '0.85rem' }}>{loop.summary}</div>
                )}
                <div className="loop-text mt-1">{loop.open_loops}</div>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
