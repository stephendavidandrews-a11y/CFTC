import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createIntro, getContacts } from '../api';

export default function IntroForm() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    person_a_id: '',
    person_b_id: '',
    date: new Date().toISOString().split('T')[0],
    context: '',
    outcome: '',
  });
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getContacts()
      .then(data => {
        setContacts(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.person_a_id || !form.person_b_id) {
      setError('Please select both contacts.');
      return;
    }
    if (form.person_a_id === form.person_b_id) {
      setError('Please select two different contacts.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await createIntro({
        person_a_id: parseInt(form.person_a_id),
        person_b_id: parseInt(form.person_b_id),
        date: form.date,
        context: form.context || null,
        outcome: form.outcome || null,
      });
      navigate('/intros');
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  if (loading) return <div className="loading">Loading contacts...</div>;

  const personA = contacts.find(c => c.id === parseInt(form.person_a_id));
  const personB = contacts.find(c => c.id === parseInt(form.person_b_id));

  return (
    <div className="form-container">
      <div className="page-header">
        <h2>Make an Introduction</h2>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Preview */}
      {personA && personB && (
        <div className="card mb-4" style={{ textAlign: 'center', padding: 24 }}>
          <div className="intro-parties" style={{ justifyContent: 'center', fontSize: '1.2rem' }}>
            <span>{personA.name}</span>
            <span className="intro-arrow" style={{ fontSize: '1.5rem' }}>&harr;</span>
            <span>{personB.name}</span>
          </div>
          <div className="text-muted mt-1" style={{ fontSize: '0.85rem' }}>
            {personA.domain || 'Unknown'} meets {personB.domain || 'Unknown'}
          </div>
          {personA.interests && personB.interests && (
            <div className="text-muted mt-1" style={{ fontSize: '0.8rem' }}>
              Shared interests check: {personA.interests} / {personB.interests}
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label>Person A *</label>
            <select name="person_a_id" value={form.person_a_id} onChange={handleChange} required>
              <option value="">Select contact...</option>
              {contacts.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.domain || 'No domain'})
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Person B *</label>
            <select name="person_b_id" value={form.person_b_id} onChange={handleChange} required>
              <option value="">Select contact...</option>
              {contacts
                .filter(c => c.id !== parseInt(form.person_a_id))
                .map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.domain || 'No domain'})
                  </option>
                ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Date</label>
          <input type="date" name="date" value={form.date} onChange={handleChange} />
        </div>

        <div className="form-group">
          <label>Why they should know each other</label>
          <textarea
            name="context"
            value={form.context}
            onChange={handleChange}
            placeholder="What do they have in common? Why would this intro be valuable for both?"
            rows={3}
          />
          <div className="form-hint">
            Think about complementary interests, professional synergies, or mutual needs.
          </div>
        </div>

        <div className="form-group">
          <label>Outcome (optional)</label>
          <input
            type="text"
            name="outcome"
            value={form.outcome}
            onChange={handleChange}
            placeholder="Leave blank — update later once they've connected"
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Creating...' : 'Log Introduction'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/intros')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
