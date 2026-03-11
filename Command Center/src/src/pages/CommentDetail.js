import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function CommentDetail() {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const [comment, setComment] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getComment(documentId).then(setComment).catch(() => {}).finally(() => setLoading(false));
  }, [documentId]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading...</div>;
  if (!comment) return <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Comment not found</div>;

  const tierColor = t => t === 1 ? '#3b82f6' : t === 2 ? '#a78bfa' : '#64748b';
  const sentColor = s => {
    const lower = (s || '').toLowerCase();
    return lower === 'oppose' ? '#ef4444' : lower === 'support' ? '#22c55e' : lower === 'mixed' ? '#f59e0b' : '#64748b';
  };

  return (
    <div>
      <button onClick={() => navigate(-1)} style={{
        background: 'none', border: '1px solid #1e293b', color: '#64748b',
        padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
        fontFamily: 'var(--font-sans)', marginBottom: 20,
      }}>← Back</button>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
              {comment.commenter_name || 'Anonymous'}
            </h2>
            {comment.commenter_organization && (
              <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 4 }}>{comment.commenter_organization}</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {comment.tier && (
              <span style={{
                padding: '4px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: `${tierColor(comment.tier)}20`, color: tierColor(comment.tier),
              }}>Tier {comment.tier}</span>
            )}
            {comment.sentiment && (
              <span style={{
                padding: '4px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                background: `${sentColor(comment.sentiment)}20`, color: sentColor(comment.sentiment),
              }}>{comment.sentiment}</span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 24, fontSize: 12, color: '#64748b' }}>
          <span>Posted: {comment.submission_date ? new Date(comment.submission_date).toLocaleDateString() : '—'}</span>
          <span>Pages: {comment.page_count || '—'}</span>
          <span style={{ fontFamily: 'var(--font-mono)' }}>{comment.document_id}</span>
        </div>
      </div>

      {/* AI Summary */}
      {comment.ai_summary && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>AI Summary</div>
          <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {typeof comment.ai_summary === 'string' ? comment.ai_summary : JSON.stringify(comment.ai_summary, null, 2)}
          </div>
        </div>
      )}

      {/* Tags */}
      {comment.tags && comment.tags.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Topics & Tags</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {comment.tags.map((tag, i) => (
              <span key={i} style={{
                padding: '3px 10px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                background: '#172554', color: '#60a5fa', border: '1px solid #1e3a5f',
              }}>{tag.value || tag.tag_value || tag}</span>
            ))}
          </div>
        </div>
      )}

      {/* Raw text */}
      {comment.comment_text && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Full Comment Text</div>
          <div style={{
            fontSize: 12, color: '#94a3b8', lineHeight: 1.7, whiteSpace: 'pre-wrap',
            maxHeight: 500, overflowY: 'auto', fontFamily: 'var(--font-mono)',
          }}>
            {comment.comment_text}
          </div>
        </div>
      )}
    </div>
  );
}
