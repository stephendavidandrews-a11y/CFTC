import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getContact, createContact, updateContact } from '../api';

const DOMAINS = [
  'Senate/Hill', 'Friend', 'Industry/Policy', 'Social', 'Military', 'Faith',
  'Government/Executive', 'Policy/Issue-Specific', 'Media/Press', 'Law Enforcement',
];
const SOCIAL_TIERS = ['Cornerstone', 'Developing', 'New', 'Dormant'];
const PROFESSIONAL_TIERS = [
  { value: 'Tier 1', label: 'Tier 1: Active Strategic (Monthly)' },
  { value: 'Tier 2', label: 'Tier 2: Warm Professional (6-8 Weeks)' },
  { value: 'Tier 3', label: 'Tier 3: Light Touch (Quarterly)' },
];

const EMPTY_FORM = {
  name: '',
  phone: '',
  email: '',
  current_role: '',
  domain: '',
  tier: 'New',
  is_super_connector: false,
  linkedin_url: '',
  relationship_status: '',
  what_i_offer: '',
  their_goals: '',
  interests: '',
  activity_prefs: '',
  how_we_met: '',
  next_action: '',
  next_action_date: '',
  notes: '',
  contact_type: 'social',
  professional_tier: null,
};

export default function ContactForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isEdit) {
      loadContact();
    }
  }, [id]);

  async function loadContact() {
    setLoading(true);
    try {
      const data = await getContact(id);
      setForm({
        name: data.name || '',
        phone: data.phone || '',
        email: data.email || '',
        current_role: data.current_role || '',
        domain: data.domain || '',
        tier: data.tier || 'New',
        is_super_connector: data.is_super_connector || false,
        linkedin_url: data.linkedin_url || '',
        relationship_status: data.relationship_status || '',
        what_i_offer: data.what_i_offer || '',
        their_goals: data.their_goals || '',
        interests: data.interests || '',
        activity_prefs: data.activity_prefs || '',
        how_we_met: data.how_we_met || '',
        next_action: data.next_action || '',
        next_action_date: data.next_action_date || '',
        notes: data.notes || '',
        contact_type: data.contact_type || 'social',
        professional_tier: data.professional_tier || null,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  }

  function handleContactTypeChange(e) {
    const newType = e.target.value;
    setForm((prev) => ({
      ...prev,
      contact_type: newType,
      // Reset tier fields when switching type
      tier: newType === 'social' ? 'New' : prev.tier,
      professional_tier: newType === 'professional' ? (prev.professional_tier || 'Tier 2') : null,
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    setSaving(true);
    setError(null);
    // Clean empty strings to null for optional enum fields
    const cleanedForm = { ...form };
    if (cleanedForm.professional_tier === '' || cleanedForm.professional_tier === undefined) {
      cleanedForm.professional_tier = null;
    }
    if (cleanedForm.domain === '') cleanedForm.domain = null;
    try {
      if (isEdit) {
        await updateContact(id, cleanedForm);
        navigate(`/contacts/${id}`);
      } else {
        const result = await createContact(cleanedForm);
        const newId = result.id || result.contact?.id;
        navigate(newId ? `/contacts/${newId}` : '/contacts');
      }
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  if (loading) return <div className="loading">Loading...</div>;

  const isProfessional = form.contact_type === 'professional';

  return (
    <div className="form-container">
      <div className="page-header">
        <h2>{isEdit ? 'Edit Contact' : 'Add Contact'}</h2>
      </div>

      {error && <div className="error-msg">{error}</div>}

      <form onSubmit={handleSubmit}>
        {/* Contact Type */}
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="contact_type">Contact Type</label>
            <select
              id="contact_type"
              name="contact_type"
              value={form.contact_type}
              onChange={handleContactTypeChange}
            >
              <option value="social">Social</option>
              <option value="professional">Professional</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="name">Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              autoFocus
              placeholder="Full name"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="phone">Phone</label>
            <input
              type="tel"
              id="phone"
              name="phone"
              value={form.phone}
              onChange={handleChange}
              placeholder="(202) 555-0100"
            />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={form.email}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="current_role">Current Role</label>
          <input
            type="text"
            id="current_role"
            name="current_role"
            value={form.current_role}
            onChange={handleChange}
            placeholder="e.g., Legislative Director, Senate Banking Committee"
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="domain">Domain</label>
            <select id="domain" name="domain" value={form.domain} onChange={handleChange}>
              <option value="">Select domain...</option>
              {DOMAINS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            {isProfessional ? (
              <>
                <label htmlFor="professional_tier">Professional Tier</label>
                <select
                  id="professional_tier"
                  name="professional_tier"
                  value={form.professional_tier || ''}
                  onChange={handleChange}
                >
                  <option value="">Select tier...</option>
                  {PROFESSIONAL_TIERS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </>
            ) : (
              <>
                <label htmlFor="tier">Tier</label>
                <select id="tier" name="tier" value={form.tier} onChange={handleChange}>
                  {SOCIAL_TIERS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              name="is_super_connector"
              checked={form.is_super_connector}
              onChange={handleChange}
            />
            {'\u2605'} Super Connector
          </label>
          <div className="form-hint">Someone who knows many people and makes frequent introductions</div>
        </div>

        <div className="form-group">
          <label htmlFor="linkedin_url">LinkedIn URL</label>
          <input
            type="url"
            id="linkedin_url"
            name="linkedin_url"
            value={form.linkedin_url}
            onChange={handleChange}
            placeholder="https://linkedin.com/in/..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="how_we_met">How We Met</label>
          <input
            type="text"
            id="how_we_met"
            name="how_we_met"
            value={form.how_we_met}
            onChange={handleChange}
            placeholder="e.g., Senate Banking Committee hearing, mutual friend intro..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="relationship_status">Relationship Status</label>
          <input
            type="text"
            id="relationship_status"
            name="relationship_status"
            value={form.relationship_status}
            onChange={handleChange}
            placeholder="e.g., Active, Reconnecting, New acquaintance"
          />
        </div>

        <div className="form-group">
          <label htmlFor="what_i_offer">What I Can Offer</label>
          <textarea
            id="what_i_offer"
            name="what_i_offer"
            value={form.what_i_offer}
            onChange={handleChange}
            placeholder="How I can help this person..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="their_goals">Their Goals</label>
          <textarea
            id="their_goals"
            name="their_goals"
            value={form.their_goals}
            onChange={handleChange}
            placeholder="What they are working toward..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="interests">Interests</label>
          <textarea
            id="interests"
            name="interests"
            value={form.interests}
            onChange={handleChange}
            placeholder="Hobbies, topics they care about..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="activity_prefs">Activity Preferences</label>
          <textarea
            id="activity_prefs"
            name="activity_prefs"
            value={form.activity_prefs}
            onChange={handleChange}
            placeholder="e.g., Happy hours, outdoor activities, coffee meetings..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="next_action">Next Action</label>
          <input
            type="text"
            id="next_action"
            name="next_action"
            value={form.next_action}
            onChange={handleChange}
            placeholder="e.g., Follow up on lunch invite"
          />
        </div>

        <div className="form-group">
          <label htmlFor="next_action_date">Next Action Date</label>
          <input
            type="date"
            id="next_action_date"
            name="next_action_date"
            value={form.next_action_date}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label htmlFor="notes">Notes</label>
          <textarea
            id="notes"
            name="notes"
            value={form.notes}
            onChange={handleChange}
            placeholder="Private notes - never shared..."
          />
          <div className="form-hint">{'\u{1F512}'} These notes are private and never shared</div>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : (isEdit ? 'Update Contact' : 'Create Contact')}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(isEdit ? `/contacts/${id}` : '/contacts')}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
