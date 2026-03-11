import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  createHappyHour, getHappyHour, updateHappyHour,
  getVenues, getContacts, addAttendee, removeAttendee, updateAttendee,
} from '../api';

export default function HappyHourForm() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);

  const [form, setForm] = useState({
    date: new Date().toISOString().split('T')[0],
    venue_id: '',
    theme: '',
    sonnet_reasoning: '',
  });
  const [attendees, setAttendees] = useState([]);
  const [venues, setVenues] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Track original attendees for edit mode diffing
  const originalAttendees = useRef([]);

  useEffect(() => {
    const promises = [getVenues(), getContacts()];
    if (isEdit) promises.push(getHappyHour(id));

    Promise.all(promises)
      .then(([v, c, hh]) => {
        setVenues(v);
        setContacts(c);
        if (hh) {
          setForm({
            date: hh.date || '',
            venue_id: hh.venue_id || '',
            theme: hh.theme || '',
            sonnet_reasoning: hh.sonnet_reasoning || '',
          });
          if (hh.attendees) {
            const mapped = hh.attendees.map(a => ({
              contact_id: a.contact_id,
              role: a.role || '',
              rsvp_status: a.rsvp_status || 'invited',
              _existing: true, // flag: this attendee already exists on server
            }));
            setAttendees(mapped);
            originalAttendees.current = mapped.map(a => a.contact_id);
          }
        }
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [id, isEdit]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const addAttendeeRow = () => {
    setAttendees(prev => [...prev, { contact_id: '', role: '', rsvp_status: 'invited', _existing: false }]);
  };

  const updateAttendeeRow = (index, field, value) => {
    setAttendees(prev => prev.map((a, i) => i === index ? { ...a, [field]: value } : a));
  };

  const removeAttendeeRow = (index) => {
    setAttendees(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      if (isEdit) {
        // 1. Update HH fields only (no attendees in the payload)
        const hhData = {
          date: form.date || null,
          venue_id: form.venue_id ? parseInt(form.venue_id) : null,
          theme: form.theme || null,
          sonnet_reasoning: form.sonnet_reasoning || null,
        };
        await updateHappyHour(id, hhData);

        // 2. Diff attendees: figure out adds, removes, updates
        const currentContactIds = attendees
          .filter(a => a.contact_id)
          .map(a => parseInt(a.contact_id));
        const originalIds = originalAttendees.current;

        // Remove attendees that were deleted from the list
        const toRemove = originalIds.filter(cid => !currentContactIds.includes(cid));
        for (const cid of toRemove) {
          await removeAttendee(id, cid);
        }

        // Add new attendees
        const toAdd = attendees.filter(
          a => a.contact_id && !originalIds.includes(parseInt(a.contact_id))
        );
        for (const att of toAdd) {
          await addAttendee(id, {
            contact_id: parseInt(att.contact_id),
            role: att.role || null,
            rsvp_status: att.rsvp_status || 'invited',
          });
        }

        // Update existing attendees that may have changed role/rsvp
        const toUpdate = attendees.filter(
          a => a.contact_id && a._existing && originalIds.includes(parseInt(a.contact_id))
        );
        for (const att of toUpdate) {
          await updateAttendee(id, parseInt(att.contact_id), {
            role: att.role || null,
            rsvp_status: att.rsvp_status || 'invited',
          });
        }
      } else {
        // Create: send everything together
        const data = {
          ...form,
          venue_id: form.venue_id ? parseInt(form.venue_id) : null,
          attendees: attendees
            .filter(a => a.contact_id)
            .map(a => ({
              contact_id: parseInt(a.contact_id),
              role: a.role || null,
              rsvp_status: a.rsvp_status || 'invited',
            })),
        };
        await createHappyHour(data);
      }
      navigate('/happy-hours');
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  if (loading) return <div className="loading">Loading...</div>;

  const usedContactIds = attendees.map(a => parseInt(a.contact_id)).filter(Boolean);

  const roles = [
    { value: '', label: 'No role' },
    { value: 'anchor', label: 'Anchor' },
    { value: 'new_edge', label: 'New Edge' },
    { value: 'wildcard', label: 'Wildcard' },
    { value: 'connector_plus_one', label: 'Connector +1' },
  ];

  return (
    <div className="form-container">
      <div className="page-header">
        <h2>{isEdit ? 'Edit Happy Hour' : 'Plan Happy Hour'}</h2>
      </div>

      {error && <div className="error-msg">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group">
            <label>Date *</label>
            <input type="date" name="date" value={form.date} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Venue</label>
            <select name="venue_id" value={form.venue_id} onChange={handleChange}>
              <option value="">No venue selected</option>
              {venues.map(v => (
                <option key={v.id} value={v.id}>{v.name} {v.neighborhood ? `(${v.neighborhood})` : ''}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Theme</label>
          <input
            type="text"
            name="theme"
            value={form.theme}
            onChange={handleChange}
            placeholder="Cigars/whiskey, casual drinks, sports watch, dinner..."
          />
        </div>

        {/* Attendees */}
        <div className="form-group">
          <label>Attendees</label>
          <div className="form-hint mb-2">
            Aim for 4-5 invitees to land 3-4 attendees. Assign roles for curated collisions.
          </div>
          {attendees.map((att, idx) => (
            <div key={idx} style={{
              display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8,
              background: 'var(--bg-input)', padding: '8px 12px', borderRadius: 8
            }}>
              <select
                value={att.contact_id}
                onChange={e => updateAttendeeRow(idx, 'contact_id', e.target.value)}
                style={{ flex: 2, padding: '6px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: 6, color: 'var(--text-primary)', fontSize: '0.85rem' }}
              >
                <option value="">Select contact...</option>
                {contacts
                  .filter(c => !usedContactIds.includes(c.id) || c.id === parseInt(att.contact_id))
                  .map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.is_super_connector ? '\u2605' : ''}
                    </option>
                  ))}
              </select>
              <select
                value={att.role}
                onChange={e => updateAttendeeRow(idx, 'role', e.target.value)}
                style={{ flex: 1, padding: '6px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: 6, color: 'var(--text-primary)', fontSize: '0.85rem' }}
              >
                {roles.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <select
                value={att.rsvp_status}
                onChange={e => updateAttendeeRow(idx, 'rsvp_status', e.target.value)}
                style={{ flex: 1, padding: '6px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: 6, color: 'var(--text-primary)', fontSize: '0.85rem' }}
              >
                <option value="invited">Invited</option>
                <option value="confirmed">Confirmed</option>
                <option value="declined">Declined</option>
                <option value="no_response">No Response</option>
              </select>
              <button
                type="button"
                onClick={() => removeAttendeeRow(idx)}
                style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: '1.2rem', padding: '4px' }}
              >
                &times;
              </button>
            </div>
          ))}
          <button type="button" className="btn btn-secondary btn-sm" onClick={addAttendeeRow}>
            + Add Attendee
          </button>
        </div>

        <div className="form-group">
          <label>Notes / Reasoning</label>
          <textarea
            name="sonnet_reasoning"
            value={form.sonnet_reasoning}
            onChange={handleChange}
            placeholder="Why this group works together, what connections might form..."
            rows={3}
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : (isEdit ? 'Update Happy Hour' : 'Create Happy Hour')}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/happy-hours')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
