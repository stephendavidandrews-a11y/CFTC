import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { createInteraction, getContacts, analyzeInteraction } from '../api';

const INTERACTION_TYPES = [
  'Happy Hour',
  '1-on-1',
  'Dinner',
  'Coffee',
  'Text/Call',
  'Group Activity',
  'Intro Made',
  'Event',
];

const WHO_INITIATED = ['Me', 'Them', 'Mutual'];

function todayStr() {
  return new Date().toISOString().split('T')[0];
}

export default function InteractionForm({ contactId, contactName, onSave, onCancel }) {
  const [form, setForm] = useState({
    contact_id: contactId || '',
    date: todayStr(),
    type: '',
    who_initiated: 'Me',
    summary: '',
    open_loops: '',
    follow_up_date: '',
  });
  const [contacts, setContacts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [dismissedLoops, setDismissedLoops] = useState({});
  const [dismissedIntros, setDismissedIntros] = useState({});
  const [acceptedFollowUp, setAcceptedFollowUp] = useState(false);
  const needContactPicker = !contactId;

  useEffect(() => {
    if (needContactPicker) {
      loadContacts();
    }
  }, []);

  async function loadContacts() {
    try {
      const data = await getContacts();
      const list = Array.isArray(data) ? data : (data.contacts || data.items || []);
      setContacts(list);
    } catch (err) {
      console.error('Failed to load contacts:', err);
    }
  }

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.contact_id) {
      setError('Please select a contact');
      return;
    }
    if (!form.type) {
      setError('Please select an interaction type');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        contact_id: parseInt(form.contact_id),
      };
      if (!payload.follow_up_date) delete payload.follow_up_date;
      if (!payload.open_loops) delete payload.open_loops;
      const result = await createInteraction(payload);

      // Check if response includes AI analysis or if we should request it
      if (result && result.ai_analysis) {
        setAiAnalysis(result.ai_analysis);
        setSaving(false);
      } else if (result && result.id) {
        // Try to get AI analysis for this interaction
        setAnalyzing(true);
        setSaving(false);
        try {
          const analysis = await analyzeInteraction(result.id);
          if (analysis && (analysis.open_loops || analysis.follow_up_date || analysis.intro_suggestions)) {
            setAiAnalysis(analysis);
          } else {
            onSave();
          }
        } catch {
          // AI analysis is optional, proceed without it
          onSave();
        } finally {
          setAnalyzing(false);
        }
      } else {
        onSave();
      }
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  function handleDismissLoop(index) {
    setDismissedLoops(prev => ({ ...prev, [index]: true }));
  }

  function handleDismissIntro(index) {
    setDismissedIntros(prev => ({ ...prev, [index]: true }));
  }

  function handleAcceptFollowUp() {
    setAcceptedFollowUp(true);
  }

  function handleDone() {
    onSave();
  }

  // If AI analysis is showing, render the analysis view
  if (aiAnalysis) {
    const openLoopsList = aiAnalysis.open_loops || [];
    const introSuggestions = aiAnalysis.intro_suggestions || [];
    const followUpDate = aiAnalysis.follow_up_date || aiAnalysis.suggested_follow_up;

    const activeLoops = openLoopsList.filter((_, i) => !dismissedLoops[i]);
    const activeIntros = introSuggestions.filter((_, i) => !dismissedIntros[i]);

    return (
      <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) handleDone(); }}>
        <div className="modal" style={{ maxWidth: 600 }}>
          <div className="modal-header">
            <h3>AI Analysis</h3>
            <button className="modal-close" onClick={handleDone}>{'\u00D7'}</button>
          </div>

          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: 20 }}>
            Sonnet analyzed your interaction and found the following insights.
          </p>

          {/* Extracted Open Loops */}
          {openLoopsList.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#f59e0b',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}>
                Extracted Open Loops
              </h4>
              {openLoopsList.map((loop, i) => (
                <div
                  key={i}
                  style={{
                    display: dismissedLoops[i] ? 'none' : 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: 12,
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 8,
                    padding: '10px 14px',
                    marginBottom: 8,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                      {typeof loop === 'string' ? loop : loop.description || loop.text || JSON.stringify(loop)}
                    </p>
                  </div>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDismissLoop(i)}
                    style={{ flexShrink: 0, color: 'var(--text-muted)', fontSize: '0.75rem' }}
                  >
                    Dismiss
                  </button>
                </div>
              ))}
              {activeLoops.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                  All open loops dismissed.
                </p>
              )}
            </div>
          )}

          {/* Suggested Follow-up Date */}
          {followUpDate && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: 'var(--accent-blue-light)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}>
                Suggested Follow-up
              </h4>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(30, 64, 175, 0.1)',
                border: '1px solid rgba(30, 64, 175, 0.2)',
                borderRadius: 8,
                padding: '10px 14px',
              }}>
                <div>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                    {new Date(followUpDate).toLocaleDateString('en-US', {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </p>
                  {aiAnalysis.follow_up_reason && (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      {aiAnalysis.follow_up_reason}
                    </p>
                  )}
                </div>
                {!acceptedFollowUp ? (
                  <button
                    className="btn btn-success btn-sm"
                    onClick={handleAcceptFollowUp}
                  >
                    Accept
                  </button>
                ) : (
                  <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>
                    Accepted
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Intro Suggestions */}
          {introSuggestions.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: '#8b5cf6',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}>
                Intro Suggestions
              </h4>
              {introSuggestions.map((intro, i) => (
                <div
                  key={i}
                  style={{
                    display: dismissedIntros[i] ? 'none' : 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: 12,
                    background: 'rgba(139, 92, 246, 0.05)',
                    border: '1px solid rgba(139, 92, 246, 0.2)',
                    borderRadius: 8,
                    padding: '10px 14px',
                    marginBottom: 8,
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                      {intro.contact_a_name || intro.from_name || 'Someone'}
                      <span style={{ color: 'var(--accent-blue-light)', margin: '0 6px' }}>{'\u2194'}</span>
                      {intro.contact_b_name || intro.to_name || 'Someone'}
                    </p>
                    {(intro.reason || intro.rationale) && (
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        {intro.reason || intro.rationale}
                      </p>
                    )}
                  </div>
                  <div className="btn-group" style={{ flexShrink: 0 }}>
                    <Link
                      to="/intros/new"
                      className="btn btn-success btn-sm"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Create
                    </Link>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleDismissIntro(i)}
                      style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
              {activeIntros.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                  All intro suggestions dismissed.
                </p>
              )}
            </div>
          )}

          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleDone}>
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Analyzing spinner
  if (analyzing) {
    return (
      <div className="modal-overlay">
        <div className="modal" style={{ maxWidth: 400, textAlign: 'center', padding: '40px 24px' }}>
          <div style={{
            display: 'inline-block',
            width: 28,
            height: 28,
            border: '3px solid var(--border-color)',
            borderTopColor: 'var(--accent-blue-light)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            marginBottom: 16,
          }} />
          <p style={{ color: 'var(--accent-blue-light)', fontSize: '0.95rem', fontWeight: 600 }}>
            Analyzing interaction...
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: 6 }}>
            Looking for open loops, follow-up opportunities, and potential intros.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="modal">
        <div className="modal-header">
          <h3>Log Interaction{contactName ? ` with ${contactName}` : ''}</h3>
          <button className="modal-close" onClick={onCancel}>{'\u00D7'}</button>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {needContactPicker && (
            <div className="form-group">
              <label htmlFor="contact_id">Contact</label>
              <select
                id="contact_id"
                name="contact_id"
                value={form.contact_id}
                onChange={handleChange}
                required
              >
                <option value="">Select contact...</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="date">Date</label>
              <input
                type="date"
                id="date"
                name="date"
                value={form.date}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="type">Type</label>
              <select
                id="type"
                name="type"
                value={form.type}
                onChange={handleChange}
                required
              >
                <option value="">Select type...</option>
                {INTERACTION_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="who_initiated">Who Initiated</label>
            <select
              id="who_initiated"
              name="who_initiated"
              value={form.who_initiated}
              onChange={handleChange}
            >
              {WHO_INITIATED.map((w) => (
                <option key={w} value={w}>{w}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="summary">Summary</label>
            <textarea
              id="summary"
              name="summary"
              value={form.summary}
              onChange={handleChange}
              placeholder="What did you discuss? Key takeaways..."
              rows={4}
            />
          </div>

          <div className="form-group">
            <label htmlFor="open_loops">Open Loops</label>
            <textarea
              id="open_loops"
              name="open_loops"
              value={form.open_loops}
              onChange={handleChange}
              placeholder="Anything left unresolved or to follow up on..."
              rows={3}
            />
          </div>

          <div className="form-group">
            <label htmlFor="follow_up_date">Follow-up Date</label>
            <input
              type="date"
              id="follow_up_date"
              name="follow_up_date"
              value={form.follow_up_date}
              onChange={handleChange}
            />
            <div className="form-hint">Optional - when should you follow up?</div>
          </div>

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Log Interaction'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
