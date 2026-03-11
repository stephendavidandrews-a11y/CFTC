import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getContact, deleteContact, getInteractions } from '../api';
import { getDomainBadgeClass, getTierBadgeClass, getProfessionalTierBadgeStyle, timeAgo } from './ContactCard';
import InteractionList from './InteractionList';
import InteractionForm from './InteractionForm';
import QuickText from './QuickText';

export default function ContactDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contact, setContact] = useState(null);
  const [interactions, setInteractions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showInteractionForm, setShowInteractionForm] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [contactData, interactionsData] = await Promise.all([
        getContact(id),
        getInteractions({ contact_id: id }),
      ]);
      setContact(contactData);
      const interList = Array.isArray(interactionsData)
        ? interactionsData
        : (interactionsData.interactions || interactionsData.items || []);
      setInteractions(interList);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${contact.name}? This cannot be undone.`)) return;
    try {
      await deleteContact(id);
      navigate('/contacts');
    } catch (err) {
      setError(err.message);
    }
  }

  function handleInteractionSaved() {
    setShowInteractionForm(false);
    loadData();
  }

  if (loading) return <div className="loading">Loading contact...</div>;
  if (error) return <div className="error-msg">{error}</div>;
  if (!contact) return <div className="error-msg">Contact not found</div>;

  const isProfessional = contact.contact_type === 'professional';

  return (
    <div className="detail-page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/contacts')}>
            {'\u2190'} Back
          </button>
          <h2>{contact.name}</h2>
          {contact.is_super_connector && (
            <span className="super-connector-star" title="Super Connector">{'\u2605'}</span>
          )}
          {isProfessional && (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '3px 8px',
                borderRadius: 4,
                background: '#1e3a5f',
                color: '#93c5fd',
                fontWeight: 600,
              }}
            >
              Professional
            </span>
          )}
        </div>
        <div className="btn-group">
          <QuickText phone={contact.phone} name={contact.name} />
          <Link to={`/contacts/${id}/edit`} className="btn btn-secondary btn-sm">Edit</Link>
          <button className="btn btn-danger btn-sm" onClick={handleDelete}>Delete</button>
        </div>
      </div>

      {/* Info Card */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          {isProfessional && contact.professional_tier ? (
            <span
              className="badge"
              style={getProfessionalTierBadgeStyle(contact.professional_tier)}
            >
              {contact.professional_tier}
            </span>
          ) : (
            contact.tier && (
              <span className={`badge ${getTierBadgeClass(contact.tier)}`}>{contact.tier}</span>
            )
          )}
          {contact.domain && (
            <span className={`badge ${getDomainBadgeClass(contact.domain)}`}>{contact.domain}</span>
          )}
          {contact.relationship_status && (
            <span className="badge badge-developing">{contact.relationship_status}</span>
          )}
        </div>

        <div className="detail-grid">
          {contact.current_role && (
            <div className="detail-field">
              <div className="field-label">Role</div>
              <div className="field-value">{contact.current_role}</div>
            </div>
          )}
          {contact.phone && (
            <div className="detail-field">
              <div className="field-label">Phone</div>
              <div className="field-value">
                <a href={`tel:${contact.phone}`}>{contact.phone}</a>
              </div>
            </div>
          )}
          {contact.email && (
            <div className="detail-field">
              <div className="field-label">Email</div>
              <div className="field-value">
                <a href={`mailto:${contact.email}`}>{contact.email}</a>
              </div>
            </div>
          )}
          {contact.linkedin_url && (
            <div className="detail-field">
              <div className="field-label">LinkedIn</div>
              <div className="field-value">
                <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">
                  View Profile {'\u2197'}
                </a>
              </div>
            </div>
          )}
          {contact.how_we_met && (
            <div className="detail-field">
              <div className="field-label">How We Met</div>
              <div className="field-value">{contact.how_we_met}</div>
            </div>
          )}
        </div>
      </div>

      {/* What I Can Offer + Their Goals */}
      {(contact.what_i_offer || contact.their_goals) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          {contact.what_i_offer && (
            <div className="highlight-box">
              <h4>What I Can Offer</h4>
              <p style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                {contact.what_i_offer}
              </p>
            </div>
          )}
          {contact.their_goals && (
            <div className="highlight-box">
              <h4>Their Goals</h4>
              <p style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                {contact.their_goals}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Interests & Activity Preferences */}
      {(contact.interests || contact.activity_prefs) && (
        <div className="card" style={{ marginBottom: 20 }}>
          {contact.interests && (
            <div className="detail-field" style={{ marginBottom: 12 }}>
              <div className="field-label">Interests</div>
              <div className="field-value">{contact.interests}</div>
            </div>
          )}
          {contact.activity_prefs && (
            <div className="detail-field">
              <div className="field-label">Activity Preferences</div>
              <div className="field-value">{contact.activity_prefs}</div>
            </div>
          )}
        </div>
      )}

      {/* Next Action */}
      {contact.next_action && (
        <div className="next-action-box" style={{ marginBottom: 20 }}>
          <div className="action-label">Next Action</div>
          <div style={{ fontSize: '0.95rem' }}>{contact.next_action}</div>
          {contact.next_action_date && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Due: {contact.next_action_date}
            </div>
          )}
        </div>
      )}

      {/* Notes */}
      {contact.notes && (
        <div className="private-notes" style={{ marginBottom: 20 }}>
          <div className="private-label">
            {'\u{1F512}'} Private - Never Shared
          </div>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            {contact.notes}
          </p>
        </div>
      )}

      {/* Interaction Timeline */}
      <div className="detail-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3>Interaction Timeline</h3>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowInteractionForm(true)}
          >
            + Log Interaction
          </button>
        </div>
        <InteractionList interactions={interactions} />
      </div>

      {/* Interaction Form Modal */}
      {showInteractionForm && (
        <InteractionForm
          contactId={parseInt(id)}
          contactName={contact.name}
          onSave={handleInteractionSaved}
          onCancel={() => setShowInteractionForm(false)}
        />
      )}
    </div>
  );
}
