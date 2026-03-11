import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getContacts, getProfessionalDue } from '../api';
import { getDomainBadgeClass, getProfessionalTierBadgeStyle, timeAgo } from './ContactCard';

export default function ProfessionalPulse() {
  const [contacts, setContacts] = useState([]);
  const [dueContacts, setDueContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [allData, dueData] = await Promise.all([
        getContacts({ contact_type: 'professional' }),
        getProfessionalDue().catch(() => []),
      ]);
      const allContacts = Array.isArray(allData) ? allData : (allData.contacts || allData.items || []);
      const proContacts = allContacts.filter(c => c.contact_type === 'professional');
      setContacts(proContacts);

      const dueList = Array.isArray(dueData) ? dueData : (dueData.contacts || dueData.items || []);
      setDueContacts(dueList);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading professional pulse...</div>;

  const tier1 = contacts.filter(c => c.professional_tier === 'Tier 1');
  const tier2 = contacts.filter(c => c.professional_tier === 'Tier 2');
  const tier3 = contacts.filter(c => c.professional_tier === 'Tier 3');

  return (
    <div>
      <div className="page-header">
        <h2>Professional Pulse</h2>
        <Link to="/contacts/new" className="btn btn-primary">+ Add Contact</Link>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Stats */}
      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-value">{contacts.length}</div>
          <div className="stat-label">Professional Contacts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#f59e0b' }}>{dueContacts.length}</div>
          <div className="stat-label">Due This Month</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#6ee7b7' }}>{tier1.length}</div>
          <div className="stat-label">Tier 1 - Active Strategic</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#93c5fd' }}>{tier2.length}</div>
          <div className="stat-label">Tier 2 - Warm Professional</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#fcd34d' }}>{tier3.length}</div>
          <div className="stat-label">Tier 3 - Light Touch</div>
        </div>
      </div>

      {/* Due for Outreach */}
      <div className="dashboard-section">
        <h3>Due for Outreach</h3>
        {dueContacts.length === 0 ? (
          <div className="card">
            <div className="empty-state" style={{ padding: '24px' }}>
              <p className="text-muted">No professional contacts due for outreach right now.</p>
            </div>
          </div>
        ) : (
          <div className="card-grid">
            {dueContacts.map(c => (
              <Link
                key={c.id}
                to={`/contacts/${c.id}`}
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="card card-clickable">
                  <div className="card-header">
                    <span className="card-title">{c.name}</span>
                    {c.professional_tier && (
                      <span
                        className="badge"
                        style={getProfessionalTierBadgeStyle(c.professional_tier)}
                      >
                        {c.professional_tier}
                      </span>
                    )}
                  </div>
                  <div className="card-body">
                    {c.current_role && (
                      <div style={{ marginBottom: 6, fontSize: '0.9rem' }}>{c.current_role}</div>
                    )}
                    {c.domain && (
                      <span className={`badge ${getDomainBadgeClass(c.domain)}`}>
                        {c.domain}
                      </span>
                    )}
                    {c.how_we_met && (
                      <div style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        Met: {c.how_we_met}
                      </div>
                    )}
                  </div>
                  <div className="card-footer">
                    <span>Last contact: {timeAgo(c.last_contact_date)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* All Professional Contacts by Tier */}
      {[
        { label: 'Tier 1: Active Strategic (Monthly)', items: tier1, tier: 'Tier 1' },
        { label: 'Tier 2: Warm Professional (6-8 Weeks)', items: tier2, tier: 'Tier 2' },
        { label: 'Tier 3: Light Touch (Quarterly)', items: tier3, tier: 'Tier 3' },
      ].map(group => (
        group.items.length > 0 && (
          <div key={group.tier} className="dashboard-section">
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {group.label}
              <span
                className="badge"
                style={getProfessionalTierBadgeStyle(group.tier)}
              >
                {group.items.length}
              </span>
            </h3>
            <div className="card-grid">
              {group.items.map(c => (
                <Link
                  key={c.id}
                  to={`/contacts/${c.id}`}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div className="card card-clickable">
                    <div className="card-header">
                      <span className="card-title">{c.name}</span>
                      {c.is_super_connector && (
                        <span className="super-connector-star" title="Super Connector">{'\u2605'}</span>
                      )}
                    </div>
                    <div className="card-body">
                      {c.current_role && (
                        <div style={{ marginBottom: 6, fontSize: '0.9rem' }}>{c.current_role}</div>
                      )}
                      {c.domain && (
                        <span className={`badge ${getDomainBadgeClass(c.domain)}`}>
                          {c.domain}
                        </span>
                      )}
                    </div>
                    <div className="card-footer">
                      <span>Last contact: {timeAgo(c.last_contact_date)}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )
      ))}

      {contacts.length === 0 && (
        <div className="empty-state" style={{ marginTop: 32 }}>
          <div className="empty-icon">{'\u{1F4BC}'}</div>
          <p>No professional contacts yet</p>
          <p className="text-muted" style={{ fontSize: '0.85rem' }}>
            Add professional contacts from the Contacts page or create a new contact with type "Professional".
          </p>
          <Link to="/contacts/new" className="btn btn-primary" style={{ marginTop: 12 }}>
            Add Professional Contact
          </Link>
        </div>
      )}
    </div>
  );
}
