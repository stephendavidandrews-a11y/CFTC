import React from 'react';

function getInteractionDotClass(type) {
  if (!type) return '';
  const t = type.toLowerCase();
  if (t.includes('happy hour')) return 'dot-happy-hour';
  if (t.includes('1-on-1') || t.includes('one-on-one')) return 'dot-1-on-1';
  if (t.includes('dinner')) return 'dot-dinner';
  if (t.includes('coffee')) return 'dot-coffee';
  if (t.includes('text') || t.includes('call')) return 'dot-text-call';
  if (t.includes('group')) return 'dot-group-activity';
  if (t.includes('intro')) return 'dot-intro-made';
  if (t.includes('event')) return 'dot-event';
  return 'dot-1-on-1';
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
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

export default function InteractionList({ interactions }) {
  if (!interactions || interactions.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">{'\u{1F4AC}'}</div>
        <p>No interactions yet</p>
      </div>
    );
  }

  const sorted = [...interactions].sort(
    (a, b) => new Date(b.date || b.created_at) - new Date(a.date || a.created_at)
  );

  return (
    <div className="timeline">
      {sorted.map((interaction, idx) => (
        <div key={interaction.id || idx} className="timeline-item">
          <div
            className="timeline-dot"
            style={{
              borderColor: getInteractionDotColor(interaction.type),
            }}
          />
          <div className="timeline-date">
            {formatDate(interaction.date)} ({timeAgo(interaction.date)})
            {interaction.who_initiated && (
              <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>
                - {interaction.who_initiated === 'Me' ? 'I initiated' :
                   interaction.who_initiated === 'Them' ? 'They initiated' : 'Mutual'}
              </span>
            )}
          </div>
          <div className="timeline-content">
            <div className="timeline-type">
              <span className={`interaction-dot ${getInteractionDotClass(interaction.type)}`} />
              {interaction.type || 'Interaction'}
              {interaction.contact_name && (
                <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>
                  with {interaction.contact_name}
                </span>
              )}
            </div>
            {interaction.summary && (
              <div className="timeline-summary">{interaction.summary}</div>
            )}
            {interaction.open_loops && (
              <div className="timeline-loops">
                {'\u{1F504}'} Open Loop: {interaction.open_loops}
              </div>
            )}
            {interaction.follow_up_date && (
              <div style={{ fontSize: '0.8rem', color: 'var(--accent-blue-light)', marginTop: 4 }}>
                Follow-up: {formatDate(interaction.follow_up_date)}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function getInteractionDotColor(type) {
  if (!type) return 'var(--accent-blue-light)';
  const t = type.toLowerCase();
  if (t.includes('happy hour')) return 'var(--tier-cornerstone)';
  if (t.includes('1-on-1')) return 'var(--accent-blue-light)';
  if (t.includes('dinner')) return 'var(--domain-friend)';
  if (t.includes('coffee')) return '#92400e';
  if (t.includes('text') || t.includes('call')) return 'var(--tier-new)';
  if (t.includes('group')) return 'var(--domain-social)';
  if (t.includes('intro')) return 'var(--domain-senate)';
  if (t.includes('event')) return 'var(--domain-industry)';
  return 'var(--accent-blue-light)';
}
