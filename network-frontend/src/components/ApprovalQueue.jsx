import React, { useState, useEffect, useCallback } from 'react';
import { getCurrentOutreach, approveOutreach, skipOutreach, markOutreachSent } from '../api';

const STATUS_COLORS = {
  pending: '#f59e0b',
  approved: '#10b981',
  sent: '#3b82f6',
  skipped: '#6b7280',
};

const TYPE_LABELS = {
  social_thursday: 'Thursday',
  professional_pulse: 'Professional',
  happy_hour_invite: 'HH Invite',
  happy_hour_reminder: 'HH Reminder',
  ad_hoc_due: 'Due',
};

export default function ApprovalQueue() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmSent, setConfirmSent] = useState(null);
  const [actionPlan, setActionPlan] = useState(null);
  const [showCompleted, setShowCompleted] = useState(false);

  const loadPlans = useCallback(async () => {
    try {
      setError(null);
      const data = await getCurrentOutreach();
      // Show pending and approved first
      const sorted = data.sort((a, b) => {
        const order = { pending: 0, approved: 1, sent: 2, skipped: 3 };
        return (order[a.status] || 9) - (order[b.status] || 9);
      });
      setPlans(sorted);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlans();

    // Auto-refresh when tab gets focus (returning from Messages app)
    const handleFocus = () => loadPlans();
    window.addEventListener('focus', handleFocus);
    const handleVisibility = () => {
      if (!document.hidden) loadPlans();
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [loadPlans]);

  async function handleApprove(planId) {
    try {
      await approveOutreach(planId);
      setPlans(prev => prev.map(p => p.id === planId ? { ...p, status: 'approved' } : p));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleApproveAll() {
    const pendingPlans = plans.filter(p => p.status === 'pending');
    for (const plan of pendingPlans) {
      try {
        await approveOutreach(plan.id);
      } catch (err) {
        console.error(`Failed to approve plan ${plan.id}:`, err);
      }
    }
    loadPlans();
  }

  async function handleSkip(planId) {
    try {
      await skipOutreach(planId);
      setPlans(prev => prev.map(p => p.id === planId ? { ...p, status: 'skipped' } : p));
    } catch (err) {
      setError(err.message);
    }
  }

  function handleSend(plan) {
    const phone = plan.contact_phone;
    const message = plan.message_draft;

    if (phone) {
      const smsUrl = `sms:${phone}&body=${encodeURIComponent(message)}`;
      window.open(smsUrl, '_blank');
      setConfirmSent(plan.id);
    } else {
      // Copy to clipboard fallback
      navigator.clipboard.writeText(message).then(() => {
        setActionPlan({ ...plan, copied: true });
        setTimeout(() => setActionPlan(null), 3000);
      });
    }
  }

  async function handleConfirmSent(planId, didSend) {
    setConfirmSent(null);
    if (didSend) {
      try {
        await markOutreachSent(planId);
        setPlans(prev => prev.map(p => p.id === planId ? { ...p, status: 'sent' } : p));
      } catch (err) {
        setError(err.message);
      }
    }
  }

  const activePlans = plans.filter(p => p.status === 'pending' || p.status === 'approved');
  const completedPlans = plans.filter(p => p.status === 'sent' || p.status === 'skipped');
  const pendingCount = plans.filter(p => p.status === 'pending').length;
  const actionableCount = activePlans.length;

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loading}>Loading...</div>
      </div>
    );
  }

  const renderCard = (plan) => (
    <div key={plan.id} style={{
      ...styles.card,
      borderLeftColor: STATUS_COLORS[plan.status] || '#6b7280',
    }}>
      {/* Card header */}
      <div style={styles.cardHeader}>
        <div style={styles.contactName}>
          {plan.contact_name || `Contact #${plan.contact_id}`}
        </div>
        <div style={styles.badges}>
          {plan.plan_type && (
            <span style={{
              ...styles.badge,
              background: 'rgba(59, 130, 246, 0.15)',
              color: '#3b82f6',
            }}>
              {TYPE_LABELS[plan.plan_type] || plan.plan_type}
            </span>
          )}
        </div>
      </div>

      {/* Message */}
      <p style={styles.message}>{plan.message_draft}</p>

      {/* Phone number */}
      {plan.contact_phone && (
        <p style={styles.phone}>{plan.contact_phone}</p>
      )}

      {/* Actions */}
      <div style={styles.cardActions}>
        {plan.status === 'pending' && (
          <>
            <button
              style={{ ...styles.actionBtn, ...styles.approveBtn }}
              onClick={() => handleApprove(plan.id)}
            >
              Approve
            </button>
            <button
              style={{ ...styles.actionBtn, ...styles.skipBtn }}
              onClick={() => handleSkip(plan.id)}
            >
              Skip
            </button>
          </>
        )}
        {plan.status === 'approved' && (
          <>
            <button
              style={{ ...styles.actionBtn, ...styles.sendBtn }}
              onClick={() => handleSend(plan)}
            >
              {plan.contact_phone ? 'Send Text' : 'Copy Message'}
            </button>
            <button
              style={{ ...styles.actionBtn, ...styles.skipBtn }}
              onClick={() => handleSkip(plan.id)}
            >
              Skip
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Outreach Queue</h1>
          <p style={styles.subtitle}>
            {actionableCount > 0
              ? `${actionableCount} message${actionableCount !== 1 ? 's' : ''} to review`
              : 'All caught up!'}
          </p>
        </div>
        {pendingCount > 0 && (
          <button style={styles.approveAllBtn} onClick={handleApproveAll}>
            Approve All ({pendingCount})
          </button>
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Active Plans */}
      <div style={styles.planList}>
        {activePlans.length === 0 && completedPlans.length === 0 ? (
          <div style={styles.empty}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x2705;</div>
            <p>No outreach plans this week.</p>
            <p style={{ fontSize: 14, color: '#6b7280', marginTop: 8 }}>
              Plans will be generated automatically on schedule.
            </p>
          </div>
        ) : activePlans.length === 0 ? (
          <div style={styles.empty}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x2705;</div>
            <p>All caught up! No messages to review.</p>
          </div>
        ) : (
          activePlans.map(renderCard)
        )}
      </div>

      {/* Completed Plans — collapsible */}
      {completedPlans.length > 0 && (
        <div style={styles.completedSection}>
          <button
            style={styles.completedToggle}
            onClick={() => setShowCompleted(!showCompleted)}
          >
            <span>{showCompleted ? '&#x25BC;' : '&#x25B6;'} Completed ({completedPlans.length})</span>
          </button>
          {showCompleted && (
            <div style={styles.completedList}>
              {completedPlans.map(plan => (
                <div key={plan.id} style={styles.completedCard}>
                  <div style={styles.completedRow}>
                    <span style={styles.completedName}>
                      {plan.contact_name || `Contact #${plan.contact_id}`}
                    </span>
                    <span style={{
                      ...styles.badge,
                      background: `${STATUS_COLORS[plan.status]}22`,
                      color: STATUS_COLORS[plan.status],
                    }}>
                      {plan.status === 'sent' ? 'Sent \u2713' : 'Skipped'}
                    </span>
                  </div>
                  <p style={styles.completedMessage}>{plan.message_draft}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Confirm sent dialog */}
      {confirmSent && (
        <div style={styles.overlay} onClick={() => setConfirmSent(null)}>
          <div style={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 style={styles.modalTitle}>Did you send it?</h3>
            <p style={styles.modalText}>
              Confirm that you sent the message in your Messages app.
            </p>
            <div style={styles.modalActions}>
              <button
                style={{ ...styles.actionBtn, ...styles.sendBtn, flex: 1 }}
                onClick={() => handleConfirmSent(confirmSent, true)}
              >
                Yes, sent it
              </button>
              <button
                style={{ ...styles.actionBtn, ...styles.skipBtn, flex: 1 }}
                onClick={() => handleConfirmSent(confirmSent, false)}
              >
                Not yet
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Copy confirmation toast */}
      {actionPlan?.copied && (
        <div style={styles.toast}>
          Copied to clipboard!
        </div>
      )}
    </div>
  );
}


const styles = {
  container: {
    minHeight: '100vh',
    background: '#0a0f1a',
    color: '#e5e7eb',
    padding: '0 0 80px 0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    fontSize: 18,
    color: '#9ca3af',
  },
  header: {
    position: 'sticky',
    top: 0,
    zIndex: 10,
    background: '#0a0f1a',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
    padding: '16px 20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    margin: 0,
    color: '#f3f4f6',
  },
  subtitle: {
    fontSize: 13,
    color: '#9ca3af',
    margin: '4px 0 0 0',
  },
  approveAllBtn: {
    background: 'rgba(16, 185, 129, 0.15)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.3)',
    borderRadius: 10,
    padding: '10px 16px',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  error: {
    background: 'rgba(239, 68, 68, 0.15)',
    color: '#ef4444',
    padding: '12px 20px',
    fontSize: 14,
    borderBottom: '1px solid rgba(239, 68, 68, 0.2)',
  },
  planList: {
    padding: '12px 16px',
  },
  empty: {
    textAlign: 'center',
    padding: '60px 20px',
    color: '#9ca3af',
    fontSize: 16,
  },
  card: {
    background: '#111827',
    borderRadius: 14,
    padding: '16px 18px',
    marginBottom: 12,
    borderLeft: '4px solid',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  contactName: {
    fontSize: 16,
    fontWeight: 700,
    color: '#f3f4f6',
  },
  badges: {
    display: 'flex',
    gap: 6,
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    padding: '3px 8px',
    borderRadius: 6,
    textTransform: 'capitalize',
  },
  message: {
    fontSize: 15,
    lineHeight: 1.5,
    color: '#d1d5db',
    whiteSpace: 'pre-wrap',
    margin: '0 0 8px 0',
  },
  phone: {
    fontSize: 12,
    color: '#6b7280',
    margin: '0 0 12px 0',
  },
  cardActions: {
    display: 'flex',
    gap: 10,
    marginTop: 12,
  },
  actionBtn: {
    padding: '12px 20px',
    borderRadius: 10,
    border: 'none',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    minWidth: 80,
    textAlign: 'center',
  },
  approveBtn: {
    background: 'rgba(16, 185, 129, 0.15)',
    color: '#10b981',
    border: '1px solid rgba(16, 185, 129, 0.3)',
    flex: 1,
  },
  sendBtn: {
    background: 'rgba(59, 130, 246, 0.15)',
    color: '#3b82f6',
    border: '1px solid rgba(59, 130, 246, 0.3)',
    flex: 2,
  },
  skipBtn: {
    background: 'rgba(107, 114, 128, 0.15)',
    color: '#6b7280',
    border: '1px solid rgba(107, 114, 128, 0.3)',
    flex: 1,
  },
  // Completed section styles
  completedSection: {
    padding: '0 16px 20px',
  },
  completedToggle: {
    background: 'none',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    color: '#6b7280',
    fontSize: 14,
    fontWeight: 600,
    padding: '10px 16px',
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
  },
  completedList: {
    marginTop: 8,
  },
  completedCard: {
    background: 'rgba(17, 24, 39, 0.5)',
    borderRadius: 10,
    padding: '10px 14px',
    marginBottom: 6,
    borderLeft: '3px solid #374151',
  },
  completedRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  completedName: {
    fontSize: 14,
    fontWeight: 600,
    color: '#9ca3af',
  },
  completedMessage: {
    fontSize: 13,
    lineHeight: 1.4,
    color: '#6b7280',
    whiteSpace: 'pre-wrap',
    margin: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    padding: 20,
  },
  modal: {
    background: '#1f2937',
    borderRadius: 16,
    padding: '24px',
    width: '100%',
    maxWidth: 360,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#f3f4f6',
    margin: '0 0 8px 0',
  },
  modalText: {
    fontSize: 14,
    color: '#9ca3af',
    margin: '0 0 20px 0',
  },
  modalActions: {
    display: 'flex',
    gap: 10,
  },
  toast: {
    position: 'fixed',
    bottom: 30,
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#10b981',
    color: '#fff',
    padding: '12px 24px',
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    zIndex: 200,
  },
};
