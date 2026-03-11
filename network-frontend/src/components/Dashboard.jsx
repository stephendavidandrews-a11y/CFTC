import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  getContacts,
  getGoingCold,
  getOpenLoops,
  getCurrentOutreach,
  getProfessionalDue,
  generateOutreach,
  generateProfessionalPulse,
  approveOutreach,
  skipOutreach,
  markOutreachSent,
  getLinkedInEvents,
} from '../api';
import OutreachCard from './OutreachCard';

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

export default function Dashboard() {
  const [contacts, setContacts] = useState([]);
  const [coldContacts, setColdContacts] = useState([]);
  const [openLoops, setOpenLoops] = useState([]);
  const [outreach, setOutreach] = useState([]);
  const [professionalDue, setProfessionalDue] = useState([]);
  const [linkedInEvents, setLinkedInEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatingPulse, setGeneratingPulse] = useState(false);
  const [genError, setGenError] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  function loadAll() {
    setLoading(true);
    Promise.all([
      getContacts(),
      getGoingCold(),
      getOpenLoops(),
      getCurrentOutreach().catch(() => []),
      getProfessionalDue().catch(() => []),
      getLinkedInEvents().catch(() => []),
    ]).then(([c, cold, loops, out, proDue, liEvents]) => {
      setContacts(c);
      setColdContacts(cold);
      setOpenLoops(loops);
      const outList = Array.isArray(out) ? out : (out.plans || out.items || []);
      setOutreach(outList);
      const dueList = Array.isArray(proDue) ? proDue : (proDue.contacts || proDue.items || []);
      setProfessionalDue(dueList);
      const eventList = Array.isArray(liEvents) ? liEvents : (liEvents.events || liEvents.items || []);
      setLinkedInEvents(eventList);
      setLoading(false);
    }).catch(() => setLoading(false));
  }

  async function handleGenerate(force = false) {
    setGenerating(true);
    setGenError(null);
    try {
      const result = await generateOutreach(force);
      const newPlans = Array.isArray(result) ? result : (result.plans || result.items || []);
      setOutreach(newPlans);
    } catch (err) {
      setGenError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleGeneratePulse(force = false) {
    setGeneratingPulse(true);
    setGenError(null);
    try {
      await generateProfessionalPulse(force);
      // Refresh professional due list
      const proDue = await getProfessionalDue().catch(() => []);
      const dueList = Array.isArray(proDue) ? proDue : (proDue.contacts || proDue.items || []);
      setProfessionalDue(dueList);
    } catch (err) {
      setGenError(err.message);
    } finally {
      setGeneratingPulse(false);
    }
  }

  async function handleApprove(id) {
    try {
      await approveOutreach(id);
      setOutreach(prev => prev.map(o => o.id === id ? { ...o, status: 'approved' } : o));
    } catch (err) {
      setGenError(err.message);
    }
  }

  async function handleSkip(id) {
    try {
      await skipOutreach(id);
      setOutreach(prev => prev.map(o => o.id === id ? { ...o, status: 'skipped' } : o));
    } catch (err) {
      setGenError(err.message);
    }
  }

  async function handleSend(id) {
    try {
      await markOutreachSent(id);
      setOutreach(prev => prev.map(o => o.id === id ? { ...o, status: 'sent' } : o));
    } catch (err) {
      setGenError(err.message);
    }
  }

  function handleEdit(id, newMessage) {
    setOutreach(prev => prev.map(o =>
      o.id === id ? { ...o, message_draft: newMessage } : o
    ));
  }

  // Determine if professional pulse generation should show
  const today = new Date();
  const isStartOfMonth = today.getDate() <= 7;
  const showPulseGenerate = isStartOfMonth || professionalDue.length === 0;

  if (loading) return <div className="loading">Loading dashboard...</div>;

  const tierCounts = contacts.reduce((acc, c) => {
    acc[c.tier] = (acc[c.tier] || 0) + 1;
    return acc;
  }, {});

  const superConnectorCount = contacts.filter(c => c.is_super_connector).length;

  const loopsByContact = openLoops.reduce((acc, loop) => {
    const name = loop.contact_name || `Contact #${loop.contact_id}`;
    if (!acc[name]) acc[name] = [];
    acc[name].push(loop);
    return acc;
  }, {});

  // LinkedIn events: only show high-significance unprocessed ones on dashboard
  const highEvents = linkedInEvents.filter(e =>
    (e.significance || '').toLowerCase() === 'high'
  );
  const otherEvents = linkedInEvents.filter(e =>
    (e.significance || '').toLowerCase() !== 'high'
  );

  // Outreach stats
  const pendingCount = outreach.filter(o => o.status === 'pending').length;
  const approvedCount = outreach.filter(o => o.status === 'approved').length;
  const sentCount = outreach.filter(o => o.status === 'sent').length;

  return (
    <div>
      <div className="page-header">
        <h2>Thursday Dashboard</h2>
        <span className="text-muted" style={{ fontSize: '0.9rem' }}>
          {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </span>
      </div>

      {/* Stats */}
      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-value">{contacts.length}</div>
          <div className="stat-label">Total Contacts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--tier-cornerstone)' }}>{tierCounts['Cornerstone'] || 0}</div>
          <div className="stat-label">Cornerstone</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--tier-developing)' }}>{tierCounts['Developing'] || 0}</div>
          <div className="stat-label">Developing</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--tier-new)' }}>{tierCounts['New'] || 0}</div>
          <div className="stat-label">New</div>
        </div>
        <div className="stat-card stat-warning">
          <div className="stat-value">{coldContacts.length}</div>
          <div className="stat-label">Going Cold</div>
        </div>
        <div className="stat-card stat-danger">
          <div className="stat-value">{openLoops.length}</div>
          <div className="stat-label">Open Loops</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--tier-cornerstone)' }}>{superConnectorCount}</div>
          <div className="stat-label">Super-Connectors</div>
        </div>
      </div>

      {/* Going Cold */}
      {coldContacts.length > 0 && (
        <div className="cold-section">
          <h3>Contacts Going Cold</h3>
          {coldContacts.map(c => (
            <div key={c.id} className="cold-contact">
              <div>
                <Link to={`/contacts/${c.id}`} style={{ fontWeight: 600 }}>{c.name}</Link>
                <span className="text-muted" style={{ marginLeft: 8, fontSize: '0.85rem' }}>
                  {c.current_role}
                </span>
              </div>
              <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                Last contact: {timeAgo(c.last_contact_date)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* This Week's Outreach */}
      <div className="dashboard-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ marginBottom: 0 }}>This Week's Outreach</h3>
          <div className="btn-group">
            {outreach.length > 0 && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleGenerate(true)}
                disabled={generating}
                title="Regenerate outreach plan"
              >
                Regenerate
              </button>
            )}
            <button
              className="btn btn-primary btn-sm"
              onClick={() => handleGenerate(false)}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Generate Outreach'}
            </button>
          </div>
        </div>

        {genError && <div className="error-msg" style={{ marginBottom: 16 }}>{genError}</div>}

        {/* Generating spinner */}
        {generating && (
          <div
            className="card"
            style={{
              marginBottom: 16,
              textAlign: 'center',
              padding: '40px 24px',
            }}
          >
            <div style={{
              display: 'inline-block',
              width: 32,
              height: 32,
              border: '3px solid var(--border-color)',
              borderTopColor: 'var(--accent-blue-light)',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
              marginBottom: 16,
            }} />
            <p style={{ color: 'var(--accent-blue-light)', fontSize: '1rem', fontWeight: 600 }}>
              Sonnet is analyzing your network...
            </p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 8 }}>
              Reviewing interaction history, open loops, and relationship health to craft personalized messages.
            </p>
          </div>
        )}

        {/* Outreach stats bar */}
        {outreach.length > 0 && !generating && (
          <div style={{
            display: 'flex',
            gap: 16,
            marginBottom: 16,
            flexWrap: 'wrap',
          }}>
            <span style={{
              fontSize: '0.8rem',
              color: '#f59e0b',
              fontWeight: 600,
            }}>
              {pendingCount} Pending
            </span>
            <span style={{
              fontSize: '0.8rem',
              color: '#10b981',
              fontWeight: 600,
            }}>
              {approvedCount} Approved
            </span>
            <span style={{
              fontSize: '0.8rem',
              color: '#3b82f6',
              fontWeight: 600,
            }}>
              {sentCount} Sent
            </span>
          </div>
        )}

        {outreach.length === 0 && !generating ? (
          <div className="card">
            <div className="empty-state" style={{ padding: '24px' }}>
              <p className="text-muted">No outreach plan generated yet for this week.</p>
              <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                Click "Generate Outreach" to have Sonnet analyze your network and draft personalized messages.
              </p>
            </div>
          </div>
        ) : (
          !generating && (
            <div className="card-grid">
              {outreach.map(o => (
                <OutreachCard
                  key={o.id}
                  plan={o}
                  onApprove={handleApprove}
                  onSkip={handleSkip}
                  onSend={handleSend}
                  onEdit={handleEdit}
                />
              ))}
            </div>
          )
        )}
      </div>

      {/* LinkedIn Events */}
      {linkedInEvents.length > 0 && (
        <div className="dashboard-section">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <h3>LinkedIn Events</h3>
            <Link to="/linkedin" className="btn btn-secondary btn-sm">View All</Link>
          </div>

          {/* High significance events */}
          {highEvents.length > 0 && (
            <div className="card-grid" style={{ marginBottom: 16 }}>
              {highEvents.slice(0, 4).map(event => (
                <div
                  key={event.id}
                  className="card"
                  style={{ borderLeft: '4px solid #dc2626' }}
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
                          {event.contact_name || 'Unknown'}
                        </span>
                      )}
                    </div>
                    <span
                      className="badge"
                      style={{
                        background: 'rgba(220, 38, 38, 0.15)',
                        color: '#dc2626',
                        border: '1px solid rgba(220, 38, 38, 0.3)',
                      }}
                    >
                      HIGH
                    </span>
                  </div>
                  <div className="card-body">
                    {event.event_type && (
                      <span style={{
                        fontSize: '0.8rem',
                        color: 'var(--accent-blue-light)',
                        fontWeight: 600,
                        textTransform: 'capitalize',
                      }}>
                        {event.event_type.replace(/_/g, ' ')}
                      </span>
                    )}
                    {event.description && (
                      <p style={{ marginTop: 4 }}>{event.description}</p>
                    )}
                    {event.outreach_hook && (
                      <p style={{
                        fontSize: '0.8rem',
                        fontStyle: 'italic',
                        color: 'var(--text-muted)',
                        marginTop: 6,
                      }}>
                        Hook: {event.outreach_hook}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Summary of other events */}
          {otherEvents.length > 0 && (
            <div className="stat-card" style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 20px',
            }}>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-blue-light)' }}>
                {otherEvents.length}
              </span>
              <span className="stat-label" style={{ margin: 0 }}>
                more LinkedIn event{otherEvents.length !== 1 ? 's' : ''} to review
              </span>
            </div>
          )}
        </div>
      )}

      {/* Open Loops */}
      <div className="dashboard-section">
        <h3>Open Loops</h3>
        {openLoops.length === 0 ? (
          <div className="card">
            <div className="empty-state" style={{ padding: '24px' }}>
              <p className="text-muted">No open loops. Log interactions to track follow-ups.</p>
            </div>
          </div>
        ) : (
          Object.entries(loopsByContact).slice(0, 5).map(([name, loops]) => (
            <div key={name} className="loop-group">
              <h4>{name}</h4>
              {loops.map(loop => (
                <div key={loop.id} className="loop-item">
                  <div className="loop-date">{timeAgo(loop.date)}</div>
                  <div className="loop-text">{loop.open_loops}</div>
                  {loop.follow_up_date && (
                    <div className="loop-followup">Follow up by: {new Date(loop.follow_up_date).toLocaleDateString()}</div>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
        {openLoops.length > 0 && (
          <Link to="/open-loops" className="btn btn-secondary btn-sm mt-3">
            View All Open Loops
          </Link>
        )}
      </div>

      {/* Professional Pulse */}
      <div className="dashboard-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h3>Professional Pulse</h3>
          <div className="btn-group">
            {showPulseGenerate && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleGeneratePulse(false)}
                disabled={generatingPulse}
              >
                {generatingPulse ? 'Generating...' : 'Generate Pulse'}
              </button>
            )}
            <Link to="/professional" className="btn btn-secondary btn-sm">View All</Link>
          </div>
        </div>

        {generatingPulse && (
          <div
            className="card"
            style={{
              marginBottom: 16,
              textAlign: 'center',
              padding: '24px',
            }}
          >
            <div style={{
              display: 'inline-block',
              width: 24,
              height: 24,
              border: '3px solid var(--border-color)',
              borderTopColor: 'var(--accent-blue-light)',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
              marginBottom: 12,
            }} />
            <p style={{ color: 'var(--accent-blue-light)', fontSize: '0.9rem' }}>
              Generating professional pulse analysis...
            </p>
          </div>
        )}

        <div className="stat-card" style={{ display: 'inline-flex', alignItems: 'center', gap: 12, padding: '12px 20px' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 700, color: professionalDue.length > 0 ? '#f59e0b' : '#6ee7b7' }}>
            {professionalDue.length}
          </span>
          <span className="stat-label" style={{ margin: 0 }}>
            professional contact{professionalDue.length !== 1 ? 's' : ''} due for outreach
          </span>
        </div>
        {professionalDue.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {professionalDue.slice(0, 3).map(c => (
              <div key={c.id} className="cold-contact">
                <div>
                  <Link to={`/contacts/${c.id}`} style={{ fontWeight: 600 }}>{c.name}</Link>
                  {c.professional_tier && (
                    <span className="text-muted" style={{ marginLeft: 8, fontSize: '0.8rem' }}>
                      {c.professional_tier}
                    </span>
                  )}
                  {c.current_role && (
                    <span className="text-muted" style={{ marginLeft: 8, fontSize: '0.85rem' }}>
                      {c.current_role}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="dashboard-section">
        <h3>Quick Actions</h3>
        <div className="btn-group">
          <Link to="/contacts/new" className="btn btn-primary">+ Add Contact</Link>
          <Link to="/contacts" className="btn btn-secondary">View All Contacts</Link>
          <Link to="/professional" className="btn btn-secondary">Professional Pulse</Link>
          <Link to="/linkedin" className="btn btn-secondary">LinkedIn Events</Link>
          <Link to="/happy-hours/new" className="btn btn-secondary">Plan Happy Hour</Link>
          <Link to="/intros/new" className="btn btn-secondary">Make an Intro</Link>
        </div>
      </div>
    </div>
  );
}
