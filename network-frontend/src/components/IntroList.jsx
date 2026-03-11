import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getIntros, updateIntro } from '../api';

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return `${Math.floor(diff / 30)} months ago`;
}

export default function IntroList() {
  const [intros, setIntros] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingOutcome, setEditingOutcome] = useState(null);
  const [outcomeText, setOutcomeText] = useState('');

  useEffect(() => {
    loadIntros();
  }, []);

  const loadIntros = () => {
    getIntros()
      .then(data => {
        setIntros(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  };

  const handleUpdateOutcome = async (introId) => {
    try {
      await updateIntro(introId, { outcome: outcomeText });
      setEditingOutcome(null);
      setOutcomeText('');
      loadIntros();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <div className="loading">Loading introductions...</div>;
  if (error) return <div className="error-msg">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Introductions</h2>
        <Link to="/intros/new" className="btn btn-primary">+ Make Intro</Link>
      </div>

      {intros.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#129309;</div>
          <p>No introductions made yet.</p>
          <p style={{ fontSize: '0.85rem' }}>
            Connecting people from different worlds is the super-connector play.
          </p>
          <Link to="/intros/new" className="btn btn-primary">Make Your First Intro</Link>
        </div>
      ) : (
        <div className="card-grid">
          {intros.map(intro => (
            <div key={intro.id} className="card intro-card">
              <div className="intro-parties">
                <Link to={`/contacts/${intro.person_a_id}`}>
                  {intro.person_a_name || `Contact #${intro.person_a_id}`}
                </Link>
                <span className="intro-arrow">&harr;</span>
                <Link to={`/contacts/${intro.person_b_id}`}>
                  {intro.person_b_name || `Contact #${intro.person_b_id}`}
                </Link>
              </div>

              {intro.context && (
                <div className="card-body mb-2">
                  <strong style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Why:</strong>
                  <p>{intro.context}</p>
                </div>
              )}

              <div className="card-footer" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                  <span>{timeAgo(intro.date)}</span>
                  {intro.outcome ? (
                    <span className="badge badge-new">{intro.outcome}</span>
                  ) : (
                    <span className="text-muted">No outcome yet</span>
                  )}
                </div>

                {editingOutcome === intro.id ? (
                  <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                    <input
                      type="text"
                      value={outcomeText}
                      onChange={e => setOutcomeText(e.target.value)}
                      placeholder="Did they connect? Still in touch?"
                      style={{
                        flex: 1,
                        padding: '6px 10px',
                        background: 'var(--bg-input)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 6,
                        color: 'var(--text-primary)',
                        fontSize: '0.85rem',
                      }}
                    />
                    <button className="btn btn-primary btn-sm" onClick={() => handleUpdateOutcome(intro.id)}>Save</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => { setEditingOutcome(null); setOutcomeText(''); }}>Cancel</button>
                  </div>
                ) : (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => { setEditingOutcome(intro.id); setOutcomeText(intro.outcome || ''); }}
                  >
                    {intro.outcome ? 'Update Outcome' : 'Add Outcome'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
