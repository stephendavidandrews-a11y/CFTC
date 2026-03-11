import React, { useState } from 'react';
import { Link } from 'react-router-dom';

const MESSAGE_TYPE_COLORS = {
  weekend_checkin: '#3b82f6',
  happy_hour_invite: '#f59e0b',
  connector_invite: '#8b5cf6',
  life_event: '#ec4899',
  follow_up: '#10b981',
  open_loop: '#f97316',
  linkedin_congrats: '#6ee7b7',
  linkedin_content: '#93c5fd',
  intro: '#a78bfa',
};

const STATUS_STYLES = {
  pending: { background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.3)' },
  approved: { background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' },
  sent: { background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)' },
  skipped: { background: 'rgba(107, 114, 128, 0.15)', color: '#6b7280', border: '1px solid rgba(107, 114, 128, 0.3)' },
};

function formatMessageType(type) {
  if (!type) return '';
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function OutreachCard({ plan, onApprove, onSkip, onSend, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [editedMessage, setEditedMessage] = useState(plan.message_draft || '');
  const [showReasoning, setShowReasoning] = useState(false);
  const [showCopyModal, setShowCopyModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);

  const typeColor = MESSAGE_TYPE_COLORS[plan.message_type] || '#6b7280';
  const statusStyle = STATUS_STYLES[plan.status] || STATUS_STYLES.pending;

  function handleEditSave() {
    if (onEdit) {
      onEdit(plan.id, editedMessage);
    }
    setEditing(false);
  }

  function handleEditCancel() {
    setEditedMessage(plan.message_draft || '');
    setEditing(false);
  }

  function handleSend() {
    const phone = plan.contact_phone || plan.phone;
    const message = editedMessage || plan.message_draft;

    if (phone) {
      // Open SMS link (works on iPhone to open Messages)
      const smsUrl = `sms:${phone}&body=${encodeURIComponent(message)}`;
      window.open(smsUrl, '_blank');
      // Show confirmation dialog
      setConfirmSent(true);
    } else {
      // No phone number - show copy modal
      setShowCopyModal(true);
    }
  }

  function handleConfirmSent(didSend) {
    setConfirmSent(false);
    if (didSend && onSend) {
      onSend(plan.id);
    }
  }

  function handleCopyMessage() {
    const message = editedMessage || plan.message_draft;
    navigator.clipboard.writeText(message).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleCopyModalSent() {
    setShowCopyModal(false);
    if (onSend) {
      onSend(plan.id);
    }
  }

  return (
    <div className="card" style={{ position: 'relative' }}>
      {/* Header */}
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link
            to={`/contacts/${plan.contact_id}`}
            className="card-title"
            style={{ color: 'var(--text-primary)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {plan.contact_name || `Contact #${plan.contact_id}`}
          </Link>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {/* Message type badge */}
          <span
            className="badge"
            style={{
              background: `${typeColor}22`,
              color: typeColor,
              border: `1px solid ${typeColor}44`,
            }}
          >
            {formatMessageType(plan.message_type)}
          </span>
          {/* Status badge */}
          <span className="badge" style={statusStyle}>
            {plan.status === 'sent' ? 'Sent' : plan.status}
          </span>
        </div>
      </div>

      {/* Message body */}
      <div className="card-body">
        {editing ? (
          <div style={{ marginBottom: 12 }}>
            <textarea
              value={editedMessage}
              onChange={(e) => setEditedMessage(e.target.value)}
              style={{
                width: '100%',
                minHeight: 120,
                padding: '10px 14px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn btn-primary btn-sm" onClick={handleEditSave}>
                Save
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleEditCancel}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p style={{ whiteSpace: 'pre-wrap', marginBottom: 8 }}>
            {editedMessage || plan.message_draft}
          </p>
        )}

        {/* Reasoning (collapsible) */}
        {plan.reasoning && (
          <div style={{ marginTop: 8 }}>
            <button
              onClick={() => setShowReasoning(!showReasoning)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '0.8rem',
                cursor: 'pointer',
                padding: 0,
                fontStyle: 'italic',
              }}
            >
              {showReasoning ? 'Hide reasoning' : 'Show reasoning'}
            </button>
            {showReasoning && (
              <p style={{
                fontSize: '0.8rem',
                fontStyle: 'italic',
                color: 'var(--text-muted)',
                marginTop: 4,
                lineHeight: 1.5,
              }}>
                {plan.reasoning}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="card-footer" style={{ justifyContent: 'flex-end' }}>
        {plan.status === 'pending' && !editing && (
          <div className="btn-group">
            <button
              className="btn btn-success btn-sm"
              onClick={() => onApprove && onApprove(plan.id)}
            >
              Approve
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            <button
              className="btn btn-secondary btn-sm"
              style={{ color: 'var(--text-muted)' }}
              onClick={() => onSkip && onSkip(plan.id)}
            >
              Skip
            </button>
          </div>
        )}
        {plan.status === 'approved' && !editing && (
          <div className="btn-group">
            <button className="btn btn-primary btn-sm" onClick={handleSend}>
              Send
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            <button
              className="btn btn-secondary btn-sm"
              style={{ color: 'var(--text-muted)' }}
              onClick={() => onSkip && onSkip(plan.id)}
            >
              Skip
            </button>
          </div>
        )}
        {plan.status === 'sent' && (
          <span style={{ fontSize: '0.85rem', color: '#3b82f6', fontWeight: 600 }}>
            Sent
          </span>
        )}
        {plan.status === 'skipped' && (
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            Skipped
          </span>
        )}
      </div>

      {/* Confirm sent dialog */}
      {confirmSent && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setConfirmSent(false); }}>
          <div className="modal" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Did you send the message?</h3>
              <button className="modal-close" onClick={() => setConfirmSent(false)}>{'\u00D7'}</button>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 20 }}>
              Confirm that you sent the message to {plan.contact_name || 'this contact'}.
            </p>
            <div className="btn-group">
              <button className="btn btn-success" onClick={() => handleConfirmSent(true)}>
                Yes, I sent it
              </button>
              <button className="btn btn-secondary" onClick={() => handleConfirmSent(false)}>
                Not yet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Copy modal (no phone number) */}
      {showCopyModal && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowCopyModal(false); }}>
          <div className="modal" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <h3>Copy Message</h3>
              <button className="modal-close" onClick={() => setShowCopyModal(false)}>{'\u00D7'}</button>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: 12 }}>
              No phone number on file. Copy the message below and send it manually.
            </p>
            <div style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
              whiteSpace: 'pre-wrap',
              fontSize: '0.9rem',
              color: 'var(--text-primary)',
              maxHeight: 200,
              overflowY: 'auto',
            }}>
              {editedMessage || plan.message_draft}
            </div>
            <div className="btn-group">
              <button className="btn btn-primary" onClick={handleCopyMessage}>
                {copied ? 'Copied!' : 'Copy to Clipboard'}
              </button>
              <button className="btn btn-success" onClick={handleCopyModalSent}>
                Mark as Sent
              </button>
              <button className="btn btn-secondary" onClick={() => setShowCopyModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
