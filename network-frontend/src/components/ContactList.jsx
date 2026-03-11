import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { getContacts } from '../api';
import ContactCard from './ContactCard';

const TIERS = ['', 'Cornerstone', 'Developing', 'New', 'Dormant'];
const PROFESSIONAL_TIERS = ['', 'Tier 1', 'Tier 2', 'Tier 3'];
const DOMAINS = [
  '', 'Senate/Hill', 'Friend', 'Industry/Policy', 'Social', 'Military', 'Faith',
  'Government/Executive', 'Policy/Issue-Specific', 'Media/Press', 'Law Enforcement',
];

const TAB_STYLE = {
  padding: '8px 20px',
  border: 'none',
  borderRadius: '6px 6px 0 0',
  cursor: 'pointer',
  fontSize: '0.9rem',
  fontWeight: 600,
  transition: 'all 0.2s',
};

const ACTIVE_TAB = {
  ...TAB_STYLE,
  background: '#1e40af',
  color: '#fff',
};

const INACTIVE_TAB = {
  ...TAB_STYLE,
  background: '#1a2332',
  color: '#9ca3af',
};

export default function ContactList() {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [scFilter, setScFilter] = useState('');
  const [contactTypeTab, setContactTypeTab] = useState('social');

  useEffect(() => {
    loadContacts();
  }, []);

  async function loadContacts() {
    setLoading(true);
    setError(null);
    try {
      const data = await getContacts();
      setContacts(Array.isArray(data) ? data : (data.contacts || data.items || []));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const isProfessionalTab = contactTypeTab === 'professional';

  const filtered = useMemo(() => {
    return contacts.filter((c) => {
      // Contact type filter
      if (contactTypeTab !== 'all') {
        const cType = c.contact_type || 'social';
        if (cType !== contactTypeTab) return false;
      }
      if (search) {
        const s = search.toLowerCase();
        const name = (c.name || '').toLowerCase();
        if (!name.includes(s)) return false;
      }
      if (tierFilter) {
        if (isProfessionalTab) {
          if (c.professional_tier !== tierFilter) return false;
        } else {
          if (c.tier !== tierFilter) return false;
        }
      }
      if (domainFilter && c.domain !== domainFilter) return false;
      if (scFilter === 'yes' && !c.is_super_connector) return false;
      if (scFilter === 'no' && c.is_super_connector) return false;
      return true;
    });
  }, [contacts, search, tierFilter, domainFilter, scFilter, contactTypeTab, isProfessionalTab]);

  function handleTabChange(tab) {
    setContactTypeTab(tab);
    setTierFilter(''); // Reset tier filter when switching tabs
  }

  if (loading) return <div className="loading">Loading contacts...</div>;

  const tierOptions = isProfessionalTab ? PROFESSIONAL_TIERS : TIERS;

  return (
    <div>
      <div className="page-header">
        <h2>Contacts</h2>
        <Link to="/contacts/new" className="btn btn-primary">+ Add Contact</Link>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Contact Type Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 0 }}>
        <button
          style={contactTypeTab === 'social' ? ACTIVE_TAB : INACTIVE_TAB}
          onClick={() => handleTabChange('social')}
        >
          Social
        </button>
        <button
          style={contactTypeTab === 'professional' ? ACTIVE_TAB : INACTIVE_TAB}
          onClick={() => handleTabChange('professional')}
        >
          Professional
        </button>
        <button
          style={contactTypeTab === 'all' ? ACTIVE_TAB : INACTIVE_TAB}
          onClick={() => handleTabChange('all')}
        >
          All
        </button>
      </div>

      <div className="filters-bar">
        <input
          type="text"
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={tierFilter} onChange={(e) => setTierFilter(e.target.value)}>
          <option value="">{isProfessionalTab ? 'All Pro Tiers' : 'All Tiers'}</option>
          {tierOptions.filter(Boolean).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)}>
          <option value="">All Domains</option>
          {DOMAINS.filter(Boolean).map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select value={scFilter} onChange={(e) => setScFilter(e.target.value)}>
          <option value="">All Contacts</option>
          <option value="yes">Super Connectors</option>
          <option value="no">Non Super Connectors</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">{'\u{1F465}'}</div>
          <p>No contacts found</p>
          {contacts.length === 0 && (
            <Link to="/contacts/new" className="btn btn-primary">Add your first contact</Link>
          )}
        </div>
      ) : (
        <div className="card-grid">
          {filtered.map((contact) => (
            <ContactCard key={contact.id} contact={contact} />
          ))}
        </div>
      )}
    </div>
  );
}
