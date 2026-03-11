import React from 'react';
import { useNavigate } from 'react-router-dom';

function getDomainBadgeClass(domain) {
  if (!domain) return '';
  const d = domain.toLowerCase();
  if (d.includes('senate') || d.includes('hill')) return 'badge-senate';
  if (d.includes('friend')) return 'badge-friend';
  if (d.includes('industry') || d.includes('policy')) return 'badge-industry';
  if (d.includes('social')) return 'badge-social';
  if (d.includes('military')) return 'badge-military';
  if (d.includes('faith')) return 'badge-faith';
  if (d.includes('government') || d.includes('executive')) return 'badge-senate';
  if (d.includes('media') || d.includes('press')) return 'badge-industry';
  if (d.includes('law enforcement')) return 'badge-military';
  return 'badge-developing';
}

function getTierBadgeClass(tier) {
  if (!tier) return '';
  const t = tier.toLowerCase();
  if (t === 'cornerstone') return 'badge-cornerstone';
  if (t === 'developing') return 'badge-developing';
  if (t === 'new') return 'badge-new';
  if (t === 'dormant') return 'badge-dormant';
  return '';
}

function getProfessionalTierBadgeStyle(tier) {
  if (!tier) return {};
  if (tier === 'Tier 1') return { background: '#065f46', color: '#6ee7b7' };
  if (tier === 'Tier 2') return { background: '#1e3a5f', color: '#93c5fd' };
  if (tier === 'Tier 3') return { background: '#3b3520', color: '#fcd34d' };
  return {};
}

function timeAgo(dateStr) {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 14) return '1 week ago';
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 60) return '1 month ago';
  return `${Math.floor(diffDays / 30)} months ago`;
}

export default function ContactCard({ contact }) {
  const navigate = useNavigate();
  const isProfessional = contact.contact_type === 'professional';

  return (
    <div
      className="card card-clickable"
      onClick={() => navigate(`/contacts/${contact.id}`)}
    >
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="card-title">
            {contact.name}
          </span>
          {contact.is_super_connector && (
            <span className="super-connector-star" title="Super Connector">{'\u2605'}</span>
          )}
          {isProfessional && (
            <span
              style={{
                fontSize: '0.7rem',
                padding: '2px 6px',
                borderRadius: 4,
                background: '#1e3a5f',
                color: '#93c5fd',
              }}
              title="Professional Contact"
            >
              PRO
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {isProfessional && contact.professional_tier ? (
            <span
              className="badge"
              style={getProfessionalTierBadgeStyle(contact.professional_tier)}
            >
              {contact.professional_tier}
            </span>
          ) : (
            contact.tier && (
              <span className={`badge ${getTierBadgeClass(contact.tier)}`}>
                {contact.tier}
              </span>
            )
          )}
        </div>
      </div>
      <div className="card-body">
        {contact.current_role && (
          <div style={{ marginBottom: 6 }}>{contact.current_role}</div>
        )}
        {contact.domain && (
          <span className={`badge ${getDomainBadgeClass(contact.domain)}`}>
            {contact.domain}
          </span>
        )}
      </div>
      <div className="card-footer">
        <span>
          Last contact: {timeAgo(contact.last_contact_date)}
        </span>
      </div>
    </div>
  );
}

export { getDomainBadgeClass, getTierBadgeClass, getProfessionalTierBadgeStyle, timeAgo };
