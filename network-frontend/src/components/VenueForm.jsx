import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getVenues, createVenue, updateVenue } from '../api';

const VENUE_TYPES = [
  'Bar',
  'Restaurant',
  'Coffee Shop',
  'Rooftop',
  'Lounge',
  'Beer Garden',
  'Wine Bar',
  'Brewery',
  'Sports Bar',
  'Other',
];

const PRICE_RANGES = ['$', '$$', '$$$', '$$$$'];

const EMPTY_FORM = {
  name: '',
  type: '',
  neighborhood: '',
  vibe: '',
  best_for: '',
  price_range: '',
  address: '',
  website: '',
  notes: '',
};

export default function VenueForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isEdit) {
      loadVenue();
    }
  }, [id]);

  async function loadVenue() {
    setLoading(true);
    try {
      const data = await getVenues();
      const list = Array.isArray(data) ? data : (data.venues || data.items || []);
      const venue = list.find((v) => String(v.id) === String(id));
      if (venue) {
        setForm({
          name: venue.name || '',
          type: venue.type || '',
          neighborhood: venue.neighborhood || '',
          vibe: venue.vibe || '',
          best_for: venue.best_for || '',
          price_range: venue.price_range || '',
          address: venue.address || '',
          website: venue.website || '',
          notes: venue.notes || '',
        });
      } else {
        setError('Venue not found');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Venue name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isEdit) {
        await updateVenue(id, form);
      } else {
        await createVenue(form);
      }
      navigate('/venues');
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="form-container">
      <div className="page-header">
        <h2>{isEdit ? 'Edit Venue' : 'Add Venue'}</h2>
      </div>

      {error && <div className="error-msg">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name">Venue Name *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={form.name}
            onChange={handleChange}
            required
            autoFocus
            placeholder="e.g., The Smith"
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="type">Type</label>
            <select id="type" name="type" value={form.type} onChange={handleChange}>
              <option value="">Select type...</option>
              {VENUE_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="price_range">Price Range</label>
            <select id="price_range" name="price_range" value={form.price_range} onChange={handleChange}>
              <option value="">Select...</option>
              {PRICE_RANGES.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="neighborhood">Neighborhood</label>
            <input
              type="text"
              id="neighborhood"
              name="neighborhood"
              value={form.neighborhood}
              onChange={handleChange}
              placeholder="e.g., Capitol Hill, Penn Quarter"
            />
          </div>
          <div className="form-group">
            <label htmlFor="vibe">Vibe</label>
            <input
              type="text"
              id="vibe"
              name="vibe"
              value={form.vibe}
              onChange={handleChange}
              placeholder="e.g., Casual, Upscale, Trendy"
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="best_for">Best For</label>
          <input
            type="text"
            id="best_for"
            name="best_for"
            value={form.best_for}
            onChange={handleChange}
            placeholder="e.g., Happy hours, Date night, Group dinners"
          />
        </div>

        <div className="form-group">
          <label htmlFor="address">Address</label>
          <input
            type="text"
            id="address"
            name="address"
            value={form.address}
            onChange={handleChange}
            placeholder="Full address"
          />
        </div>

        <div className="form-group">
          <label htmlFor="website">Website</label>
          <input
            type="url"
            id="website"
            name="website"
            value={form.website}
            onChange={handleChange}
            placeholder="https://..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="notes">Notes</label>
          <textarea
            id="notes"
            name="notes"
            value={form.notes}
            onChange={handleChange}
            placeholder="Any additional notes about this venue..."
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : (isEdit ? 'Update Venue' : 'Create Venue')}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/venues')}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
